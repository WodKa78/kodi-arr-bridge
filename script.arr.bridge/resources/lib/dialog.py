"""Remote-friendly single-screen add form, backed by live server choices."""
import xbmcgui


class AddDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None

    def configure(self, kind, candidate, profiles, roots, tags, defaults):
        self.kind, self.candidate = kind, candidate
        self.profiles, self.roots, self.tags = profiles, roots, tags
        profile = next((p for p in profiles if str(p['id']) == defaults.get('profile')), profiles[0])
        root = next((p for p in roots if p['path'] == defaults.get('root')), roots[0])
        self.options = dict(qualityProfileId=profile['id'], rootFolderPath=root['path'],
                            tags=[], search=defaults.get('search', False), monitored=True,
                            monitor='all', seasonFolder=True, seriesType='standard', availability='released')
        self.options['seasons'] = [s['seasonNumber'] for s in candidate.get('seasons', []) if s['seasonNumber'] > 0]

    def onInit(self):
        self.getControl(20).setLabel('Add to ' + self.kind.title())
        c = self.candidate
        ident = 'TMDb {}'.format(c.get('tmdbId')) if self.kind == 'radarr' else 'TVDb {}'.format(c.get('tvdbId'))
        self.getControl(21).setLabel('{} ({})  |  {}'.format(c.get('title', ''), c.get('year') or '?', ident))
        self.refresh()
        self.setFocusId(100)

    def refresh(self):
        o = self.options
        profile = next(p for p in self.profiles if p['id'] == o['qualityProfileId'])
        tag_names = [t['label'] for t in self.tags if t['id'] in o['tags']]
        yes = lambda b: 'Yes' if b else 'No'
        rows = [('profile', 'Quality profile: ' + profile['name']),
                ('root', 'Root folder: ' + o['rootFolderPath'])]
        if self.kind == 'radarr':
            rows += [('monitored', 'Monitor movie: ' + yes(o['monitored'])),
                     ('availability', 'Minimum availability: ' + o['availability'])]
        else:
            rows += [('monitor', 'Monitor episodes: ' + o['monitor']),
                     ('seasons', 'Selected seasons: ' + ', '.join(map(str, o['seasons']))),
                     ('seriesType', 'Series type: ' + o['seriesType']),
                     ('seasonFolder', 'Use season folders: ' + yes(o['seasonFolder']))]
        rows += [('tags', 'Tags: ' + (', '.join(tag_names) or 'None')),
                 ('search', 'Search after adding: ' + yes(o['search']))]
        self.rows = rows
        for i in range(8):
            control = self.getControl(100 + i)
            control.setVisible(i < len(rows))
            if i < len(rows):
                control.setLabel(rows[i][1])
        allowed = []
        def collect(items):
            for item in items:
                if item.get('allowed'):
                    if item.get('quality'):
                        allowed.append(item['quality']['name'])
                    elif item.get('items'):
                        collect(item['items'])
        collect(profile.get('items', []))
        self.getControl(22).setText('Allowed qualities: ' + (', '.join(allowed) or 'Defined by this server profile') +
                                  '\nQuality, language and upgrade rules follow the selected server profile.')

    def select(self, heading, values, labels=None, current=None):
        preselect = values.index(current) if current in values else -1
        index = xbmcgui.Dialog().select(heading, labels or values, preselect=preselect)
        return values[index] if index >= 0 else current

    def onClick(self, control_id):
        if control_id == 201:
            self.close()
            return
        if control_id == 200:
            if self.kind == 'sonarr' and self.options['monitor'] == 'selected' and not self.options['seasons']:
                xbmcgui.Dialog().ok('Choose seasons', 'Select at least one season or set monitoring to None.')
                return
            self.result = dict(self.options)
            self.close()
            return
        index = control_id - 100
        if not 0 <= index < len(self.rows):
            return
        key = self.rows[index][0]
        o = self.options
        if key == 'profile':
            o['qualityProfileId'] = self.select('Quality profile', [p['id'] for p in self.profiles],
                                               [p['name'] for p in self.profiles], o['qualityProfileId'])
        elif key == 'root':
            o['rootFolderPath'] = self.select('Root folder on the server', [r['path'] for r in self.roots],
                                              current=o['rootFolderPath'])
        elif key in ('monitored', 'seasonFolder', 'search'):
            o[key] = not o[key]
        elif key == 'availability':
            o[key] = self.select('Minimum availability', ['announced', 'inCinemas', 'released'], current=o[key])
        elif key == 'monitor':
            o[key] = self.select('Monitor episodes', ['all', 'future', 'missing', 'firstSeason', 'lastSeason', 'none', 'selected'],
                                 ['All episodes', 'Future episodes', 'Missing episodes', 'First season', 'Last season', 'None', 'Selected seasons'], o[key])
        elif key == 'seriesType':
            o[key] = self.select('Series type', ['standard', 'daily', 'anime'], current=o[key])
        elif key == 'seasons':
            seasons = [s['seasonNumber'] for s in self.candidate.get('seasons', [])]
            chosen = xbmcgui.Dialog().multiselect('Seasons to monitor',
                        ['Specials' if s == 0 else 'Season {}'.format(s) for s in seasons],
                        preselect=[i for i, s in enumerate(seasons) if s in o['seasons']])
            if chosen is not None:
                o['seasons'] = [seasons[i] for i in chosen]
                o['monitor'] = 'selected'
        elif key == 'tags':
            if not self.tags:
                xbmcgui.Dialog().ok('Tags', 'No tags are configured on this server.')
            else:
                chosen = xbmcgui.Dialog().multiselect('Tags', [t['label'] for t in self.tags],
                            preselect=[i for i, t in enumerate(self.tags) if t['id'] in o['tags']])
                if chosen is not None:
                    o['tags'] = [self.tags[i]['id'] for i in chosen]
        self.refresh()

    def onAction(self, action):
        if action.getId() in (9, 10, 92):
            self.close()
