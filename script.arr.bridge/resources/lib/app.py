import hashlib
import json
import os
from urllib.parse import parse_qsl, urlencode
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from resources.lib.api import ArrClient, ArrError, AlreadyExists, exact_match
from resources.lib.media import HELPER, normalize, snapshot
from resources.lib.dialog import AddDialog
from resources.lib.settings_dialog import SettingsDialog, save_settings
from resources.lib.integration import skin_action, shortcut_action, atomic_write

ADDON_ID = 'script.arr.bridge'


class Cancelled(Exception):
    pass


def parse_args(args):
    result = {}
    for arg in args:
        result.update(parse_qsl(arg.lstrip('?'), keep_blank_values=True))
    return result


class App:
    def __init__(self):
        self.addon = xbmcaddon.Addon(ADDON_ID)
        self.dialog = xbmcgui.Dialog()

    def client(self, kind):
        return ArrClient(self.addon.getSetting(kind + '_url'), self.addon.getSetting(kind + '_key'), kind,
                         self.addon.getSetting('timeout') or 20)

    def busy(self, message, fn):
        progress = xbmcgui.DialogProgressBG()
        progress.create('Arr Bridge', message)
        try:
            return fn()
        finally:
            progress.close()

    def preferences_path(self, client):
        root = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        os.makedirs(root, exist_ok=True)
        ident = hashlib.sha256(client.base.encode('utf-8')).hexdigest()[:20]
        return os.path.join(root, 'choices-' + client.kind + '-' + ident + '.json')

    def defaults(self, client):
        data = {}
        if self.addon.getSettingBool('remember_choices'):
            try:
                with open(self.preferences_path(client), encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, ValueError):
                pass
        data['search'] = self.addon.getSettingBool('search_after_add')
        return data

    def choose_candidate(self, client, media):
        ids = media['ids']
        if client.kind == 'radarr' and ids.get('tmdbId'):
            term = 'tmdb:' + ids['tmdbId']
        elif client.kind == 'sonarr' and ids.get('tvdbId'):
            term = 'tvdb:' + ids['tvdbId']
        elif client.kind == 'radarr' and ids.get('imdbId'):
            term = 'imdb:' + ids['imdbId']
        else:
            term = media['title'] or self.dialog.input('Series title for Sonarr matching' if client.kind == 'sonarr' else 'Movie title')
        if not term:
            raise Cancelled()
        rows = self.busy('Matching title in ' + client.kind.title(), lambda: client.lookup(term))
        if not rows:
            raise ArrError('No match found in {}. Try another title from TMDb Helper.'.format(client.kind.title()))
        candidate = exact_match(rows, ids)
        if candidate is not None:
            return candidate
        # A known-ID mismatch must not silently add a different title.
        comparable_rows = []
        for row in rows:
            conflicts = any(str(row[k]) != str(v) for k, v in ids.items() if v and row.get(k))
            if not conflicts:
                comparable_rows.append(row)
        if not comparable_rows:
            raise ArrError('Server matches have conflicting media IDs. No title was added.')
        labels = []
        for row in comparable_rows:
            li = xbmcgui.ListItem(label='{} ({})'.format(row.get('title', ''), row.get('year') or '?'),
                                 label2='{} {} | {}'.format(client.id_key, row.get(client.id_key, ''),
                                                           (row.get('overview') or '')[:180]))
            poster = next((x.get('remoteUrl') or x.get('url') for x in row.get('images', []) if x.get('coverType') == 'poster'), '')
            if poster:
                li.setArt({'thumb': poster})
            labels.append(li)
        index = self.dialog.select('Confirm {} match: {}'.format(client.kind.title(), media['title'] or term), labels, useDetails=True)
        if index < 0:
            raise Cancelled()
        return comparable_rows[index]

    def add(self, raw, args):
        media = normalize(raw, args)
        if not media['kind']:
            index = self.dialog.select('Add selected media as', ['Movie → Radarr', 'TV series → Sonarr'])
            if index < 0:
                raise Cancelled()
            media['kind'] = ('movie', 'tv')[index]
            # Ambiguous ID namespaces are unsafe. Match the title explicitly.
            media['ids'] = {}
        client = self.client('radarr' if media['kind'] == 'movie' else 'sonarr')
        candidate = self.choose_candidate(client, media)
        external_id = candidate.get(client.id_key)
        if not external_id:
            raise ArrError('Server lookup did not return a valid external media ID.')
        if self.busy('Checking existing library', lambda: client.existing(external_id)):
            raise AlreadyExists('This title is already in {}. Its settings were not changed.'.format(client.kind.title()))
        def load_choices():
            return (client.request('qualityprofile'), client.request('rootfolder'), client.request('tag'))
        profiles, roots, tags = self.busy('Loading profiles and folders', load_choices)
        if not profiles or not roots:
            raise ArrError('Configure at least one quality profile and root folder in {} first.'.format(client.kind.title()))
        form = AddDialog('ArrBridge.xml', self.addon.getAddonInfo('path'), 'Default', '1080i')
        form.configure(client.kind, candidate, profiles, roots, tags or [], self.defaults(client))
        form.doModal()
        options = form.result
        del form
        if options is None:
            raise Cancelled()
        # An explicit Add button is the only path to POST. No automatic retries.
        result = self.busy('Adding to ' + client.kind.title(), lambda: client.add(candidate, options))
        if not isinstance(result, dict) or not result.get('id'):
            raise ArrError('The server did not confirm an added ID. Check its library before retrying.')
        if self.addon.getSettingBool('remember_choices'):
            try:
                atomic_write(self.preferences_path(client), json.dumps({
                    'profile': str(options['qualityProfileId']), 'root': options['rootFolderPath']}))
            except OSError:
                pass  # Successful additions remain successful if local preferences cannot be saved.
        searched = options['search'] and (options['monitored'] if client.kind == 'radarr' else options['monitor'] != 'none')
        self.dialog.notification('Added to ' + client.kind.title(), candidate['title'] + (' — search requested' if searched else ''),
                                 xbmcgui.NOTIFICATION_INFO, 5000)

    def search(self, kind):
        if not xbmc.getCondVisibility('System.HasAddon({})'.format(HELPER)):
            self.dialog.ok('TMDb Helper required', 'Install and enable TMDb Helper from the Kodi or Jurialmunkey repository first.')
            return
        query = self.dialog.input('Search TMDb Helper: ' + ('movies' if kind == 'movie' else 'TV series'))
        if not query:
            return
        url = 'plugin://{}/?{}'.format(HELPER, urlencode({'info': 'search', 'tmdb_type': kind, 'query': query}))
        xbmc.executebuiltin('ActivateWindow(Videos,"{}",return)'.format(url))

    def test(self):
        messages = []
        for kind in ('radarr', 'sonarr'):
            try:
                client = self.client(kind)
                status = self.busy('Testing ' + kind.title(), lambda: client.request('system/status'))
                profiles = client.request('qualityprofile')
                roots = client.request('rootfolder')
                messages.append('{} {}: connected; {} profiles, {} folders'.format(kind.title(), status.get('version', ''), len(profiles), len(roots)))
            except ArrError as exc:
                messages.append('{}: {}'.format(kind.title(), exc))
        self.dialog.ok('Connection tests (read only)', '\n\n'.join(messages))

    def settings(self):
        form = SettingsDialog('ArrBridge.xml', self.addon.getAddonInfo('path'), 'Default', '1080i')
        form.configure(self.addon)
        form.doModal()
        values = form.result
        del form
        if values is None:
            return
        save_settings(self.addon, values)
        self.dialog.notification('Arr Bridge', 'Settings saved', xbmcgui.NOTIFICATION_INFO, 3000)

    def home(self):
        while True:
            choice = self.dialog.select('Arr Bridge', ['Search movies in TMDb Helper', 'Search TV series in TMDb Helper',
                'Server settings', 'Test server connections', 'Enable Arctic Fuse 2 info button',
                'Remove Arctic Fuse 2 info button', 'Install Ctrl+Shift+A shortcut', 'Remove Ctrl+Shift+A shortcut'])
            if choice < 0:
                return
            if choice in (0, 1):
                self.search(('movie', 'tv')[choice])
                return
            if choice == 2:
                self.settings()
            elif choice == 3:
                self.test()
            elif choice in (4, 5):
                skin_action(remove=choice == 5)
                return
            elif choice in (6, 7):
                shortcut_action(remove=choice == 7)


def main(argv=None, listitem=None):
    app = App()
    try:
        args = parse_args(argv or [])
        if args.get('action') == 'add' or listitem is not None:
            raw = snapshot(xbmc, listitem)  # Capture before a dialog can change focus.
            app.add(raw, args)
        elif args.get('action') == 'settings':
            app.settings()
        elif args.get('action') == 'test':
            app.test()
        else:
            app.home()
    except Cancelled:
        return
    except AlreadyExists as exc:
        app.dialog.ok('Already added', str(exc))
    except (ArrError, ValueError, OSError) as exc:
        # OSError may contain filesystem paths; never dump raw network exceptions.
        app.dialog.ok('Arr Bridge', str(exc) if isinstance(exc, (ArrError, ValueError)) else 'Could not save or read local files. Check Kodi file permissions.')
    except Exception as exc:
        xbmc.log('Arr Bridge: unexpected {}'.format(type(exc).__name__), xbmc.LOGERROR)
        app.dialog.ok('Arr Bridge', 'An unexpected {} occurred. No automatic retry was made. Check the server if you pressed Add.'.format(type(exc).__name__))
