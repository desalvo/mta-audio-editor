import io
import tarfile
import zipfile
from scripts.license_gate import audit_archive


def test_safe_zip(tmp_path):
    p = tmp_path / 'source.zip'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('mta/THIRD_PARTY_NOTICES.md', 'notices')
        z.writestr('mta/app.py', 'pass')
    result = audit_archive(p)
    assert result['ok'] and result['members_checked'] == 2


def test_reject_vst_zip(tmp_path):
    p = tmp_path / 'bad.zip'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('package/Plugins/External.vst3/Contents/x86_64-linux/Plugin.so', b'bad')
    assert not audit_archive(p)['ok']


def test_reject_traversal_tar(tmp_path):
    p = tmp_path / 'bad.tar.gz'
    with tarfile.open(p, 'w:gz') as tar:
        data = b'contents'
        info = tarfile.TarInfo('../escape.txt')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    assert not audit_archive(p)['ok']


def test_unknown_package_not_misrepresented_as_checked(tmp_path):
    p = tmp_path / 'app.rpm'
    p.write_bytes(b'not a tar or zip')
    assert not audit_archive(p)['ok']
