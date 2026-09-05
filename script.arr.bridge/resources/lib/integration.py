"""Small, reversible AF2 patch and opt-in shortcut installer."""
import os
import re
import xml.etree.ElementTree as ET

START = '<!-- Arr Bridge information action BEGIN -->'
END = '<!-- Arr Bridge information action END -->'
AF2_BUTTON = '''<!-- Arr Bridge information action BEGIN -->
            <include content="DialogInfo_Button_Expansion" condition="System.HasAddon(script.arr.bridge)">
                <param name="id">4098</param>
                <param name="groupid">4198</param>
                <param name="sliceid">4298</param>
                <param name="label">Add to Arr</param>
                <param name="icon">special://skin/extras/icons/watchlist.png</param>
                <param name="visible">String.IsEqual(ListItem.DBTYPE,movie) | String.IsEqual(ListItem.DBTYPE,tvshow) | String.IsEqual(ListItem.DBTYPE,season) | String.IsEqual(ListItem.DBTYPE,episode) | String.IsEqual(ListItem.Property(tmdb_type),movie) | String.IsEqual(ListItem.Property(tmdb_type),tv)</param>
                <onclick>RunScript(script.arr.bridge,action=add)</onclick>
            </include>
            <!-- Arr Bridge information action END -->'''

KEYMAP = '''<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <global><keyboard><a mod="ctrl,shift">RunScript(script.arr.bridge,action=add)</a></keyboard></global>
  <DialogVideoInfo><keyboard><a mod="ctrl,shift">RunScript(script.arr.bridge,action=add)</a></keyboard></DialogVideoInfo>
</keymap>
'''


def patch_af2(text, remove=False):
    ET.fromstring(text)
    if START in text:
        if not remove:
            return text
        result = re.sub(r'\n            ' + re.escape(START) + r'.*?' + re.escape(END), '', text, count=1, flags=re.S)
        if result == text or START in result:
            raise ValueError('Incomplete patch markers. Restore your backup manually.')
    elif remove:
        return text
    else:
        for control_id in ('4098', '4198', '4298'):
            if re.search(r'(?:id="' + control_id + r'"|>' + control_id + r'</param>)', text):
                raise ValueError('The skin already uses an Arr Bridge control ID. No changes made.')
        pattern = r'(<include\s+name="Items_DialogVideoInfo_MenuBar"\s*>\s*<definition>)'
        if len(re.findall(pattern, text)) != 1:
            raise ValueError('This skin layout is not supported. Use the context menu or shortcut.')
        result = re.sub(pattern, lambda m: m.group(1) + '\n            ' + AF2_BUTTON, text, count=1)
    ET.fromstring(result)
    return result


def atomic_write(path, text):
    temp = path + '.arrbridge-tmp'
    with open(temp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def skin_action(remove=False):
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
    if xbmc.getSkinDir() != 'skin.arctic.fuse.2':
        xbmcgui.Dialog().ok('Arctic Fuse 2', 'Activate Arctic Fuse 2 before using this option.')
        return
    root = xbmcvfs.translatePath(xbmcaddon.Addon('skin.arctic.fuse.2').getAddonInfo('path'))
    path = os.path.join(root, '1080i', 'Includes_Items.xml')
    with open(path, encoding='utf-8', newline='') as f:
        old = f.read()
    new = patch_af2(old, remove)
    if old == new:
        xbmcgui.Dialog().ok('Arr Bridge', 'The information button is already ' + ('removed.' if remove else 'enabled.'))
        return
    # Backup only once and never overwrite the original backup.
    backup = path + '.arrbridge-backup'
    if not os.path.exists(backup):
        with open(backup, 'x', encoding='utf-8', newline='') as f:
            f.write(old)
    atomic_write(path, new)
    xbmcgui.Dialog().ok('Arr Bridge', 'Information button {}. The skin will now reload.'.format('removed' if remove else 'enabled'))
    xbmc.executebuiltin('ReloadSkin()')


def shortcut_action(remove=False):
    import xbmc
    import xbmcgui
    import xbmcvfs
    root = xbmcvfs.translatePath('special://profile/keymaps/')
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, 'arrbridge.xml')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            if f.read() != KEYMAP:
                raise ValueError('arrbridge.xml has custom changes. Edit it manually to preserve your bindings.')
    if remove:
        if os.path.exists(path):
            os.unlink(path)
    else:
        atomic_write(path, KEYMAP)
    xbmc.executebuiltin('Action(reloadkeymaps)')
    xbmcgui.Dialog().ok('Arr Bridge', 'Ctrl+Shift+A shortcut ' + ('removed.' if remove else 'installed. Use it on a media item or its information screen.'))
