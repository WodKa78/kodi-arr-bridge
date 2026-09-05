"""Exercise the add workflow with Kodi UI doubles; no media is added remotely."""
import importlib
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_app():
    modules = {name: ModuleType(name) for name in ('xbmc', 'xbmcgui', 'xbmcaddon', 'xbmcvfs')}
    modules['xbmcgui'].WindowXMLDialog = type('WindowXMLDialog', (), {})
    modules['xbmcgui'].Dialog = Mock()
    modules['xbmcgui'].ListItem = Mock()
    modules['xbmcgui'].NOTIFICATION_INFO = 'info'
    modules['xbmcaddon'].Addon = Mock()
    with patch.dict(sys.modules, modules):
        return importlib.import_module('resources.lib.app')


app_module = load_app()
from resources.lib.api import ArrError, AlreadyExists
AddDialog = app_module.AddDialog


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = app_module.App()
        self.app.dialog = Mock()
        self.app.addon = Mock()
        self.app.addon.getSettingBool.return_value = False
        self.app.busy = lambda msg, fn: fn()
        self.app.defaults = lambda client: {}
        self.client = Mock(kind='radarr', id_key='tmdbId')
        self.app.client = lambda kind: self.client
        self.candidate = dict(title='Example', year=2025, tmdbId=123, images=[])
        self.client.lookup.return_value = [self.candidate]
        self.client.existing.return_value = None
        self.client.request.side_effect = [[{'id': 7, 'name': 'HD'}], [{'path': '/movies'}], []]
        self.client.add.return_value = {'id': 10}
        self.raw = dict(dbtype='movie', title='Example', tmdb='123')

    def test_cancel_form_never_calls_add(self):
        with patch.object(app_module, 'AddDialog') as dialog:
            dialog.return_value.result = None
            with self.assertRaises(app_module.Cancelled):
                self.app.add(self.raw, {})
        self.client.add.assert_not_called()

    def test_confirmed_options_reach_api_unchanged(self):
        options = {'qualityProfileId': 7, 'rootFolderPath': '/movies', 'monitored': True, 'search': False}
        with patch.object(app_module, 'AddDialog') as dialog:
            dialog.return_value.result = options
            self.app.add(self.raw, {})
        self.client.add.assert_called_once_with(self.candidate, options)

    def test_already_added_does_not_open_form(self):
        self.client.existing.return_value = {'id': 10}
        with patch.object(app_module, 'AddDialog') as dialog:
            with self.assertRaises(AlreadyExists):
                self.app.add(self.raw, {})
            dialog.assert_not_called()
        self.client.add.assert_not_called()

    def test_missing_profiles_blocks_add(self):
        self.client.request.side_effect = [[], [{'path': '/movies'}], []]
        with self.assertRaisesRegex(ArrError, 'quality profile'):
            self.app.add(self.raw, {})
        self.client.add.assert_not_called()

    def test_id_conflict_blocks_add(self):
        self.client.lookup.return_value = [dict(self.candidate, tmdbId=999)]
        with self.assertRaisesRegex(ArrError, 'conflicting'):
            self.app.add(self.raw, {})
        self.client.add.assert_not_called()

    def test_title_only_match_requires_selection_even_if_single(self):
        self.app.dialog.select.return_value = -1
        with self.assertRaises(app_module.Cancelled):
            self.app.add(dict(dbtype='movie', title='Example'), {})
        self.app.dialog.select.assert_called_once()
        self.client.add.assert_not_called()

    def test_sonarr_tmdb_without_tvdb_requires_confirm_when_response_has_no_tmdb(self):
        self.client.kind, self.client.id_key = 'sonarr', 'tvdbId'
        self.client.lookup.return_value = [dict(title='Series', tvdbId=456, year=2025)]
        self.app.dialog.select.return_value = 0
        c = self.app.choose_candidate(self.client, {'title': 'Series', 'ids': {'tmdbId': '123'}})
        self.client.lookup.assert_called_once_with('Series')
        self.app.dialog.select.assert_called_once()
        self.assertEqual(c['tvdbId'], 456)

    def test_failed_add_does_not_notify_success(self):
        self.client.add.side_effect = ArrError('Server error')
        with patch.object(app_module, 'AddDialog') as dialog:
            dialog.return_value.result = {'monitored': True, 'search': False}
            with self.assertRaises(ArrError):
                self.app.add(self.raw, {})
        self.app.dialog.notification.assert_not_called()

    def test_escape_closes_form_without_result(self):
        form = AddDialog()
        form.close = Mock()
        action = Mock()
        action.getId.return_value = 92
        form.onAction(action)
        form.close.assert_called_once()
        self.assertIsNone(form.result)

    def test_control_ids_exist(self):
        root = Path(__file__).resolve().parents[1]
        xml = ET.parse(root / 'resources/skins/Default/1080i/ArrBridge.xml')
        ids = [int(c.attrib['id']) for c in xml.iter('control') if 'id' in c.attrib]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set([20, 21, 22, 200, 201] + list(range(100, 108))).issubset(ids))

    def test_settings_cancel_does_not_write(self):
        with patch.object(app_module, 'SettingsDialog') as form:
            form.return_value.result = None
            self.app.settings()
        self.app.addon.setSetting.assert_not_called()

    def test_settings_save_persists_and_confirms(self):
        store = {'radarr_url': '', 'sonarr_url': '', 'radarr_key': '', 'sonarr_key': '', 'timeout': '20'}
        self.app.addon.getSetting.side_effect = lambda key: store.get(key, '')
        self.app.addon.setSetting.side_effect = lambda key, value: store.update({key: value})
        values = dict(store, radarr_url='http://localhost:7878', radarr_key='new-key', timeout='30')
        with patch.object(app_module, 'SettingsDialog') as form:
            form.return_value.result = values
            self.app.settings()
        self.assertEqual(store, values)
        self.app.dialog.notification.assert_called_once()

    def test_invalid_settings_never_write(self):
        with self.assertRaises(ArrError):
            app_module.save_settings(self.app.addon, {'radarr_url': '', 'sonarr_url': '',
                'radarr_key': '', 'sonarr_key': '', 'timeout': '0'})
        self.app.addon.setSetting.assert_not_called()

    def test_failed_settings_write_restores_previous_values(self):
        store = {'radarr_url': '', 'sonarr_url': '', 'radarr_key': 'old', 'sonarr_key': '', 'timeout': '20'}
        before = dict(store)
        addon = Mock()
        addon.getSetting.side_effect = lambda key: store[key]
        def write(key, value):
            if value == 'fail':
                return False
            store[key] = value
        addon.setSetting.side_effect = write
        with self.assertRaises(ArrError):
            app_module.save_settings(addon, dict(store, radarr_url='http://localhost:7878', radarr_key='fail'))
        self.assertEqual(store, before)


if __name__ == '__main__':
    unittest.main()
