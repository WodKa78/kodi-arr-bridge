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

    def test_search_choice_survives_new_app_instance_for_on_and_off(self):
        for selected in (True, False):
            with self.subTest(selected=selected):
                self.setUp()
                saved = {'search_after_add': 'false', 'remember_choices': 'false'}
                self.app.addon.setSetting.side_effect = lambda k, v: saved.update({k: v})
                self.app.addon.getSetting.side_effect = lambda k: saved.get(k, '')
                self.app.addon.getSettingBool.side_effect = lambda k: saved.get(k) == 'true'
                options = dict(qualityProfileId=7, rootFolderPath='/movies', monitored=True, search=selected)
                with patch.object(app_module, 'AddDialog') as dialog:
                    dialog.return_value.result = options
                    self.app.add(self.raw, {})
                reopened = app_module.App()
                reopened.addon = self.app.addon
                self.assertEqual(reopened.defaults(self.client)['search'], selected)
                # The same default is used for Sonarr as for Radarr.
                self.assertEqual(reopened.defaults(Mock(kind='sonarr'))['search'], selected)
                self.app.dialog.ok.assert_not_called()

    def test_failed_or_cancelled_add_does_not_change_search_default(self):
        for cancelled in (True, False):
            with self.subTest(cancelled=cancelled):
                self.setUp()
                self.client.add.side_effect = ArrError('Server unavailable')
                with patch.object(app_module, 'AddDialog') as dialog:
                    dialog.return_value.result = None if cancelled else {'search': True}
                    with self.assertRaises((app_module.Cancelled, ArrError)):
                        self.app.add(self.raw, {})
                self.app.addon.setSetting.assert_not_called()

    def test_search_save_failure_does_not_retry_successful_add(self):
        self.app.addon.setSetting.return_value = False
        with patch.object(app_module, 'AddDialog') as dialog:
            dialog.return_value.result = dict(search=True, monitored=True)
            self.app.add(self.raw, {})
        self.client.add.assert_called_once()
        self.app.dialog.ok.assert_called_once()
        self.app.dialog.notification.assert_called_once()

    def test_unmonitored_title_keeps_search_preference(self):
        self.app.addon.setSetting.return_value = True
        self.app.addon.getSetting.return_value = 'true'
        with patch.object(app_module, 'AddDialog') as dialog:
            dialog.return_value.result = dict(search=True, monitored=False)
            self.app.add(self.raw, {})
        self.app.addon.setSetting.assert_called_once_with('search_after_add', 'true')
        self.assertNotIn('search requested', self.app.dialog.notification.call_args.args[1])

    def test_navigation_skips_hidden_rows(self):
        for count in (6, 7, 8):
            form = AddDialog()
            controls = {i: Mock() for i in list(range(100, 108)) + [200, 201]}
            form.getControl = controls.__getitem__
            form.wire_navigation(count)
            self.assertIs(controls[99 + count].setNavigation.call_args.args[1], controls[200])
            self.assertIs(controls[200].setNavigation.call_args.args[0], controls[99 + count])
            for hidden in range(100 + count, 108):
                controls[hidden].setNavigation.assert_not_called()

    def test_settings_default_overrides_previous_search_choice(self):
        saved = dict(radarr_url='', sonarr_url='', radarr_key='', sonarr_key='',
                     timeout='20', search_after_add='true', remember_choices='false')
        addon = Mock()
        addon.getSetting.side_effect = lambda k: saved.get(k, '')
        addon.getSettingBool.side_effect = lambda k: saved.get(k) == 'true'
        addon.setSetting.side_effect = lambda k, v: saved.update({k: v})
        app_module.save_settings(addon, dict(saved, search_after_add='false'))
        reopened = app_module.App()
        reopened.addon = addon
        self.assertIs(reopened.defaults(self.client)['search'], False)

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
