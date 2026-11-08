"""Build a static Kodi feed from the released ZIP; no network or third-party modules."""
import hashlib
import io
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
FEED = DOCS / 'repo'


def immutable_write(path, content):
    if path.exists() and path.read_bytes() != content:
        raise ValueError('Published package changed without a version bump: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def package_repository(folder):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(folder.parent).as_posix(), (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return output.getvalue()


def build():
    manifests = []
    for addon_id in ('script.arr.bridge', 'script.arr.remove', 'repository.arr.bridge'):
        folder = ROOT / addon_id
        manifest = ET.parse(folder / 'addon.xml').getroot()
        assert manifest.attrib['id'] == addon_id
        version = manifest.attrib['version']
        filename = '{}-{}.zip'.format(addon_id, version)
        if addon_id in ('script.arr.bridge', 'script.arr.remove'):
            payload = (ROOT / 'dist' / filename).read_bytes()
        else:
            payload = package_repository(folder)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.testzip() is None
            packed = ET.fromstring(archive.read(addon_id + '/addon.xml'))
            assert ET.tostring(packed) == ET.tostring(manifest), 'Source and ZIP manifests differ'
            assert all(n.startswith(addon_id + '/') and '..' not in Path(n).parts for n in archive.namelist())
        target = FEED / addon_id / filename
        immutable_write(target, payload)
        target.with_suffix('.zip.sha256').write_text(hashlib.sha256(payload).hexdigest() + '\n')
        if addon_id == 'repository.arr.bridge':
            immutable_write(DOCS / filename, payload)
        manifests.append(manifest)
    root = ET.Element('addons')
    root.extend(manifests)
    ET.indent(root)
    index = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    (FEED / 'addons.xml').write_bytes(index)
    (FEED / 'addons.xml.md5').write_text(hashlib.md5(index).hexdigest() + '\n')
    (DOCS / '.nojekyll').touch()
    print('Built Kodi feed with ' + ', '.join(a.attrib['id'] + ' ' + a.attrib['version'] for a in manifests))


if __name__ == '__main__':
    build()
