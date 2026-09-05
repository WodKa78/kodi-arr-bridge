import copy
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resources.lib.api import ArrClient, ArrError, AlreadyExists, api_base, build_payload, exact_match
from resources.lib.media import normalize, snapshot
from resources.lib.integration import patch_af2, START

MOVIE = dict(title='Example Film', titleSlug='example-film', year=2025, tmdbId=123, images=[])
SHOW = dict(title='Example Show', titleSlug='example-show', year=2024, tvdbId=456, images=[],
            seasons=[{'seasonNumber': 0}, {'seasonNumber': 1}, {'seasonNumber': 2}])
OPTIONS = dict(qualityProfileId=7, rootFolderPath='/media/movies', tags=[2], search=True)


class MediaTests(unittest.TestCase):
    def test_tmdbhelper_movie_path(self):
        m = normalize({'path': 'plugin://plugin.video.themoviedb.helper/?info=play&tmdb_type=movie&tmdb_id=123', 'title': 'Example'})
        self.assertEqual((m['kind'], m['ids']['tmdbId']), ('movie', '123'))

    def test_tmdbhelper_episode_uses_parent_url_not_episode_uid(self):
        m = normalize(dict(dbtype='episode', tmdb='999', tvdb='888', imdb='tt999',
            path='plugin://plugin.video.themoviedb.helper/?tmdb_type=tv&tmdb_id=123&season=1&episode=2',
            title='Episode title', showtitle='Parent show'))
        self.assertEqual(m['ids'], {'tmdbId': '123', 'tvdbId': '', 'imdbId': ''})
        self.assertEqual(m['title'], 'Parent show')

    def test_other_addon_episode_ids_never_become_show_ids(self):
        m = normalize(dict(dbtype='episode', tmdb='999', tvdb='888', imdb='tt999', title='Pilot', showtitle='Parent'))
        self.assertFalse(any(m['ids'].values()))

    def test_parent_ids_take_priority(self):
        m = normalize(dict(dbtype='episode', tmdb='999', parent_tmdb='123', parent_tvdb='456', showtitle='Parent'))
        self.assertEqual(m['ids']['tmdbId'], '123')
        self.assertEqual(m['ids']['tvdbId'], '456')

    def test_explicit_call_does_not_mix_focused_item(self):
        m = normalize(dict(dbtype='tvshow', tvdb='900', title='Wrong'), {'type': 'movie', 'tmdb_id': '123'})
        self.assertEqual(m['kind'], 'movie')
        self.assertEqual(m['ids']['tvdbId'], '')
        self.assertEqual(m['title'], '')

    def test_invalid_ids_filtered(self):
        m = normalize(dict(dbtype='movie', tmdb='-1', tvdb='junk', imdb='1234'))
        self.assertFalse(any(m['ids'].values()))

    def test_unknown_type_never_inferred_from_generic_id(self):
        self.assertEqual(normalize({'tmdb': '123'})['kind'], '')

    def test_context_snapshot_does_not_mix_focused_labels(self):
        from unittest.mock import Mock
        kodi = Mock()
        item = Mock()
        item.getLabel.return_value = 'Selected'
        item.getPath.return_value = ''
        item.getArt.return_value = ''
        item.getProperty.return_value = ''
        tag = item.getVideoInfoTag.return_value
        tag.getMediaType.return_value = 'movie'
        tag.getTitle.return_value = 'Selected'
        tag.getTVShowTitle.return_value = ''
        tag.getYear.return_value = 2025
        tag.getDbId.return_value = 0
        tag.getTvShowId.return_value = -1
        tag.getUniqueID.side_effect = lambda name: '123' if name == 'tmdb' else ''
        m = normalize(snapshot(kodi, item))
        self.assertEqual(m['ids']['tmdbId'], '123')
        kodi.getInfoLabel.assert_not_called()

    def test_local_episode_fetches_parent_library_record(self):
        from unittest.mock import Mock
        kodi = Mock()
        labels = {'ListItem.DBTYPE': 'episode', 'ListItem.DBID': '11', 'ListItem.Title': 'Pilot',
                  'ListItem.UniqueID(tmdb)': '999'}
        kodi.getInfoLabel.side_effect = lambda key: labels.get(key, '')
        kodi.executeJSONRPC.side_effect = [json.dumps({'result': {'episodedetails': {'tvshowid': 22}}}),
            json.dumps({'result': {'tvshowdetails': {'title': 'Parent', 'year': 2020, 'uniqueid': {'tvdb': '456'}}}})]
        m = normalize(snapshot(kodi))
        self.assertEqual(m['ids']['tvdbId'], '456')
        self.assertEqual(m['ids']['tmdbId'], '')
        self.assertEqual(m['title'], 'Parent')


class PayloadTests(unittest.TestCase):
    def test_movie_payload_uses_live_profile_and_root(self):
        p = build_payload('radarr', dict(MOVIE, id=22, path='/old', statistics={}), OPTIONS)
        self.assertEqual(p['qualityProfileId'], 7)
        self.assertEqual(p['rootFolderPath'], '/media/movies')
        self.assertTrue(p['addOptions']['searchForMovie'])
        self.assertNotIn('id', p)
        self.assertNotIn('path', p)

    def test_unmonitored_movie_does_not_search(self):
        p = build_payload('radarr', MOVIE, dict(OPTIONS, monitored=False))
        self.assertFalse(p['addOptions']['searchForMovie'])

    def test_selected_seasons_include_specials_only_if_selected(self):
        before = copy.deepcopy(SHOW)
        p = build_payload('sonarr', SHOW, dict(OPTIONS, monitor='selected', seasons=[2], seriesType='anime'))
        self.assertEqual(p['addOptions']['monitor'], 'skip')
        self.assertEqual([s['monitored'] for s in p['seasons']], [False, False, True])
        self.assertEqual(p['seriesType'], 'anime')
        self.assertEqual(SHOW, before)

    def test_no_selected_seasons_rejected(self):
        with self.assertRaises(ArrError):
            build_payload('sonarr', SHOW, dict(OPTIONS, monitor='selected', seasons=[]))

    def test_none_monitor_suppresses_search(self):
        p = build_payload('sonarr', SHOW, dict(OPTIONS, monitor='none'))
        self.assertFalse(p['monitored'])
        self.assertFalse(p['addOptions']['searchForMissingEpisodes'])

    def test_future_monitor(self):
        p = build_payload('sonarr', SHOW, dict(OPTIONS, monitor='future'))
        self.assertEqual(p['addOptions']['monitor'], 'future')

    def test_exact_match_conflict_and_ambiguity(self):
        self.assertIsNone(exact_match([dict(MOVIE, imdbId='tt111')], {'tmdbId': '123', 'imdbId': 'tt222'}))
        self.assertIsNone(exact_match([MOVIE, MOVIE], {'tmdbId': '123'}))
        self.assertEqual(exact_match([MOVIE], {'tmdbId': '123'}), MOVIE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.calls.append(('GET', self.path, dict(self.headers)))
        if self.server.mode == 'redirect':
            self.send_response(302)
            self.send_header('Location', '/credential-trap')
            self.end_headers()
            return
        if self.server.mode == 'auth':
            self.send_response(401)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        if self.server.mode == 'badjson':
            self.wfile.write(b'<html>login</html>')
            return
        if '/lookup?' in self.path:
            payload = [MOVIE]
        elif self.server.mode == 'existing':
            payload = [dict(MOVIE, id=11)]
        else:
            payload = []
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append(('POST', self.path, data))
        if self.server.mode == 'duplicate-race':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'[{"errorCode":"MovieExistsValidator"}]')
            return
        self.send_response(201)
        self.end_headers()
        self.wfile.write(json.dumps(dict(data, id=99)).encode())


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.mode, self.server.calls = 'ok', []
        self.client = ArrClient('http://127.0.0.1:{}/radarr'.format(self.server.server_port), 'secret-key', 'radarr')

    def test_real_http_lookup_header_and_urlbase(self):
        self.assertEqual(self.client.lookup('tmdb:123')[0]['tmdbId'], 123)
        method, path, headers = self.server.calls[0]
        self.assertEqual(path, '/radarr/api/v3/movie/lookup?term=tmdb%3A123')
        self.assertEqual(headers['X-Api-Key'], 'secret-key')
        self.assertNotIn('secret-key', path)

    def test_real_http_add(self):
        self.assertEqual(self.client.add(MOVIE, OPTIONS)['id'], 99)
        self.assertEqual([c[0] for c in self.server.calls], ['GET', 'POST'])
        self.assertEqual(self.server.calls[-1][2]['qualityProfileId'], 7)

    def test_duplicate_prevents_post(self):
        self.server.mode = 'existing'
        with self.assertRaises(AlreadyExists):
            self.client.add(MOVIE, OPTIONS)
        self.assertEqual([c[0] for c in self.server.calls], ['GET'])

    def test_duplicate_race_returns_clear_error(self):
        self.server.mode = 'duplicate-race'
        with self.assertRaises(AlreadyExists):
            self.client.add(MOVIE, OPTIONS)

    def test_redirect_does_not_forward_key(self):
        self.server.mode = 'redirect'
        with self.assertRaisesRegex(ArrError, 'redirected'):
            self.client.lookup('test')
        self.assertEqual(len(self.server.calls), 1)

    def test_auth_error(self):
        self.server.mode = 'auth'
        with self.assertRaisesRegex(ArrError, 'Authentication'):
            self.client.lookup('test')

    def test_bad_json(self):
        self.server.mode = 'badjson'
        with self.assertRaisesRegex(ArrError, 'invalid JSON'):
            self.client.lookup('test')

    def test_uncertain_post_not_retried(self):
        with patch.object(self.client.opener, 'open', side_effect=URLError('timeout')) as call:
            with self.assertRaisesRegex(ArrError, 'may have completed'):
                self.client.request('movie', payload=MOVIE)
            self.assertEqual(call.call_count, 1)

    def test_url_validation(self):
        self.assertEqual(api_base('https://example.test/radarr/'), 'https://example.test/radarr/api/v3')
        self.assertEqual(api_base('https://example.test/radarr/api/v3/'), 'https://example.test/radarr/api/v3')
        for url in ('example.test', 'https://user:pass@example.test', 'https://example.test/?apikey=foo'):
            with self.assertRaises(ArrError):
                api_base(url)


class SkinTests(unittest.TestCase):
    SOURCE = '<includes><include name="Items_DialogVideoInfo_MenuBar"><definition><control type="button" id="4002"/></definition></include></includes>'

    def test_roundtrip_and_idempotence(self):
        changed = patch_af2(self.SOURCE)
        self.assertIn(START, changed)
        self.assertEqual(patch_af2(changed), changed)
        self.assertEqual(patch_af2(changed, remove=True), self.SOURCE)

    def test_unknown_layout_refused(self):
        with self.assertRaises(ValueError):
            patch_af2('<includes/>')

    def test_id_collision_refused(self):
        with self.assertRaises(ValueError):
            patch_af2(self.SOURCE.replace('4002', '4098'))


if __name__ == '__main__':
    unittest.main()
