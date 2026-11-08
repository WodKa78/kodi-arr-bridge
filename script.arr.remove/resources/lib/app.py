"""Kodi context-menu removal with an explicit, safe Arr scope selection."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcaddon
import xbmcgui

ADDON_ID = 'script.arr.remove'
BRIDGE_ID = 'script.arr.bridge'
TIMEOUT = 20


class ArrError(Exception):
    pass


def rpc(method, params):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    response = json.loads(raw)
    if response.get('error'):
        raise ArrError(response['error'].get('message', 'Kodi did not remove the library entry.'))
    return response.get('result', {})


def kodi_media(listitem):
    """Capture the selected library entity before opening dialogs."""
    tag = listitem.getVideoInfoTag()
    media_type = tag.getMediaType()
    dbid = tag.getDbId()
    if media_type not in ('movie', 'tvshow') or dbid < 0:
        raise ArrError('Select a movie or TV show from the Kodi library.')
    method = 'VideoLibrary.GetMovieDetails' if media_type == 'movie' else 'VideoLibrary.GetTVShowDetails'
    key = 'movieid' if media_type == 'movie' else 'tvshowid'
    result_key = 'moviedetails' if media_type == 'movie' else 'tvshowdetails'
    details = rpc(method, {key: dbid, 'properties': ['title', 'year', 'uniqueid']})[result_key]
    return {'kind': media_type, 'dbid': dbid, 'title': details.get('title') or listitem.getLabel(),
            'year': details.get('year'), 'ids': details.get('uniqueid') or {}}


class ArrClient:
    def __init__(self, kind):
        bridge = xbmcaddon.Addon(BRIDGE_ID)
        self.kind = kind
        self.base = bridge.getSetting(kind + '_url').strip().rstrip('/')
        self.key = bridge.getSetting(kind + '_key').strip()
        try:
            self.timeout = int(bridge.getSetting('timeout') or TIMEOUT)
        except ValueError:
            self.timeout = TIMEOUT
        if not self.base or not self.key:
            raise ArrError('Configure the {} URL and API key in Arr Bridge first.'.format(kind.title()))

    def request(self, path, query=None):
        url = self.base + '/api/v3/' + path.lstrip('/')
        if query:
            url += '?' + urlencode(query)
        request = Request(url, headers={'X-Api-Key': self.key, 'Accept': 'application/json'}, method='GET')
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise ArrError('{} returned HTTP {} while finding this title.'.format(self.kind.title(), exc.code))
        except (URLError, OSError):
            raise ArrError('Could not reach {}. Check Arr Bridge server settings.'.format(self.kind.title()))

    def delete(self, item_id, delete_files, exclude_lists):
        query = {'deleteFiles': 'true' if delete_files else 'false'}
        # These are the documented deletion query keys for Radarr v3 and Sonarr v4.
        query['addImportExclusion' if self.kind == 'radarr' else 'addImportListExclusion'] = 'true' if exclude_lists else 'false'
        url = self.base + '/api/v3/' + ('movie/' if self.kind == 'radarr' else 'series/') + str(item_id)
        url += '?' + urlencode(query)
        request = Request(url, headers={'X-Api-Key': self.key}, method='DELETE')
        try:
            with urlopen(request, timeout=self.timeout):
                return
        except HTTPError as exc:
            raise ArrError('{} returned HTTP {} while removing this title.'.format(self.kind.title(), exc.code))
        except (URLError, OSError):
            raise ArrError('Could not reach {}. Kodi has not been changed.'.format(self.kind.title()))

    def find(self, media):
        """Return only a confidently matched library record; never delete a title guess."""
        records = self.request('movie' if self.kind == 'radarr' else 'series')
        wanted_ids = media['ids']
        id_names = ('tmdb', 'imdb') if self.kind == 'radarr' else ('tvdb', 'tmdb', 'imdb')
        for record in records:
            for name in id_names:
                wanted = str(wanted_ids.get(name, '')).strip()
                actual = str(record.get(name + 'Id', '')).strip()
                if wanted and actual and wanted == actual:
                    return record
        title = (media['title'] or '').casefold().strip()
        year = media.get('year')
        matches = [row for row in records if (row.get('title') or '').casefold().strip() == title
                   and (not year or not row.get('year') or row.get('year') == year)]
        if len(matches) == 1:
            return matches[0]
        return None


def choice(dialog, media):
    target = 'Radarr' if media['kind'] == 'movie' else 'Sonarr'
    options = [
        'Kodi library only',
        'Kodi + {} record (keep files)'.format(target),
        'Kodi + {} record + files'.format(target),
        'Kodi + {} record + files + block import lists'.format(target),
    ]
    return dialog.select('Remove “{}”'.format(media['title']), options)


def remove_kodi(media):
    if media['kind'] == 'movie':
        rpc('VideoLibrary.RemoveMovie', {'movieid': media['dbid']})
    else:
        rpc('VideoLibrary.RemoveTVShow', {'tvshowid': media['dbid']})


def main(listitem=None):
    dialog = xbmcgui.Dialog()
    try:
        if listitem is None:
            dialog.ok('Arr Remove', 'Open this from a movie or TV show context menu.')
            return
        media = kodi_media(listitem)
        selected = choice(dialog, media)
        if selected < 0:
            return
        scopes = ('Kodi library only; files remain.',
                  'Kodi and Arr entry; files remain.',
                  'Kodi and Arr entry; Arr will delete managed files.',
                  'Kodi and Arr entry; Arr will delete managed files and exclude import lists.')
        if not dialog.yesno('Confirm removal',
                            'Remove “{}”?\n{}'.format(media['title'], scopes[selected]),
                            nolabel='Cancel', yeslabel='Remove'):
            return
        if selected:
            client = ArrClient('radarr' if media['kind'] == 'movie' else 'sonarr')
            progress = xbmcgui.DialogProgressBG()
            progress.create('Arr Remove', 'Finding the matching {} title…'.format(client.kind.title()))
            try:
                record = client.find(media)
                if record is None:
                    raise ArrError('No unique {} match was found. Nothing was removed.'.format(client.kind.title()))
                progress.update(50, 'Removing from {}…'.format(client.kind.title()))
                client.delete(record['id'], delete_files=selected >= 2, exclude_lists=selected == 3)
            finally:
                progress.close()
        remove_kodi(media)
        message = 'Removed from Kodi'
        if selected == 1:
            message += ' and Arr (files kept)'
        elif selected == 2:
            message += ', Arr and disk'
        elif selected == 3:
            message += ', Arr and disk; import lists blocked'
        dialog.notification('Arr Remove', message, xbmcgui.NOTIFICATION_INFO, 5000)
    except ArrError as exc:
        dialog.ok('Arr Remove', str(exc))
    except Exception as exc:
        xbmc.log('Arr Remove: unexpected {}'.format(type(exc).__name__), xbmc.LOGERROR)
        dialog.ok('Arr Remove', 'The removal was not completed. No automatic retry was made.')
