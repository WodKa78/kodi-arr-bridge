"""Explicit Save/Cancel settings form independent of the active skin's settings UI."""
import xbmc
import xbmcgui
from resources.lib.api import api_base, ArrError
from resources.lib.dialog import AddDialog

FIELDS = [
    ('radarr_url', 'Radarr server URL', 'text'),
    ('radarr_key', 'Radarr API key', 'secret'),
    ('sonarr_url', 'Sonarr server URL', 'text'),
    ('sonarr_key', 'Sonarr API key', 'secret'),
    ('search_after_add', 'Search after adding', 'bool'),
    ('remember_choices', 'Remember profile and folder', 'bool'),
    ('timeout', 'API timeout (seconds)', 'number'),
]


def validate(values):
    for name in ('radarr_url', 'sonarr_url'):
        values[name] = values[name].strip()
        if values[name]:
            api_base(values[name])
    for name in ('radarr_key', 'sonarr_key'):
        values[name] = values[name].strip()
    try:
        timeout = int(values['timeout'])
    except ValueError:
        raise ArrError('Enter an API timeout between 3 and 120 seconds.') from None
    if not 3 <= timeout <= 120:
        raise ArrError('Enter an API timeout between 3 and 120 seconds.')
    values['timeout'] = str(timeout)
    return values


def save_settings(addon, values):
    values = validate(dict(values))
    old = {key: addon.getSetting(key) for key in values}
    try:
        for key, value in values.items():
            if addon.setSetting(key, value) is False:
                raise ArrError('Kodi could not save settings. Check profile write permissions.')
        if any(addon.getSetting(key) != value for key, value in values.items()):
            raise ArrError('Kodi did not retain the settings. Check profile write permissions.')
    except Exception:
        for key, value in old.items():
            try:
                addon.setSetting(key, value)
            except Exception:
                pass
        raise


class SettingsDialog(AddDialog):
    def configure(self, addon):
        self.values = {key: addon.getSetting(key) for key, _, _ in FIELDS}
        self.values['timeout'] = self.values['timeout'] or '20'

    def onInit(self):
        self.getControl(20).setLabel('Arr Bridge settings')
        self.getControl(21).setLabel('Server connections and defaults')
        self.getControl(22).setText('Select a row to edit it. Choose Save settings to apply your changes.\nCancel or Back discards changes. API keys are hidden.')
        self.getControl(200).setLabel('Save settings')
        self.refresh()
        self.setFocusId(100)

    def refresh(self):
        for index, (key, label, kind) in enumerate(FIELDS):
            value = self.values[key]
            if kind == 'secret':
                value = '******** (set)' if value else 'Not set'
            elif kind == 'bool':
                value = 'Yes' if value == 'true' else 'No'
            self.getControl(100 + index).setLabel(label + ': ' + (value or 'Not set'))
        self.getControl(107).setVisible(False)

    def onClick(self, control_id):
        if control_id == 201:
            self.close()
            return
        if control_id == 200:
            try:
                self.result = validate(dict(self.values))
            except ArrError as exc:
                xbmcgui.Dialog().ok('Settings', str(exc))
                return
            self.close()
            return
        index = control_id - 100
        if not 0 <= index < len(FIELDS):
            return
        key, label, kind = FIELDS[index]
        if kind == 'bool':
            self.values[key] = 'false' if self.values[key] == 'true' else 'true'
        else:
            keyboard = xbmc.Keyboard(self.values[key], label, kind == 'secret')
            keyboard.doModal()
            if keyboard.isConfirmed():
                self.values[key] = keyboard.getText()
        self.refresh()
