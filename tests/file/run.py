#!/usr/bin/env python3
"""Native atomic-save behavior, metadata and failure cleanup (no UI)."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
env = dict(os.environ, ZEN_STD=str(ROOT.parent / 'zen/src'),
           CFLAGS='-O2 -Wno-parentheses-equality')
subprocess.run([str(ROOT.parent / 'zen/zen'), 'build', '.'],
               cwd=Path(__file__).parent, env=env, check=True, timeout=120)
exe = ROOT / 'build/file-state'
with tempfile.TemporaryDirectory(prefix='zen-file-test-') as temporary:
    folder = Path(temporary)
    def save(path, data, existing=False, success=True):
        result = subprocess.run([str(exe), str(path), data,
                                 'existing' if existing else 'new'], timeout=10)
        assert result.returncode == (0 if success else 1), (path, result.returncode)
        assert not list(folder.rglob('*.zen-*')), 'staging file leaked'
    target = folder / 'code.zen'
    save(target, 'initial')
    assert target.read_text() == 'initial'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    target.chmod(0o751)
    os.utime(target, (946684800, 946684800))
    subprocess.run(['xattr', '-w', 'com.zen.atomic-save-test', 'preserve me', str(target)], check=True)
    save(target, 'replacement', existing=True)
    assert target.read_text() == 'replacement'
    assert target.stat().st_mtime > 946684800
    assert stat.S_IMODE(target.stat().st_mode) == 0o751
    assert subprocess.check_output(['xattr', '-p', 'com.zen.atomic-save-test', str(target)]).strip() == b'preserve me'
    # Simulate an entry created after the app decided it was a new document.
    save(target, 'must not overwrite', success=False)
    assert target.read_text() == 'replacement'
    save(folder / 'missing-parent' / 'file', 'no', success=False)
    save(folder / 'missing-existing', 'no', existing=True, success=False)
    link = folder / 'alias'
    link.symlink_to(target)
    save(link, 'no', existing=True, success=False)
    save(link, 'no', success=False)
    assert link.is_symlink() and target.read_text() == 'replacement'
    dangling = folder / 'dangling'
    dangling.symlink_to(folder / 'absent')
    save(dangling, 'no', existing=True, success=False)
    save(dangling, 'no', success=False)
    assert dangling.is_symlink()
    directory = folder / 'directory'
    directory.mkdir()
    save(directory, 'no', success=False)
    save(directory, 'no', existing=True, success=False)
    assert directory.is_dir()
    save(target, '', existing=True)
    assert target.read_bytes() == b''
print('PASS: existing/new atomic save, executable mode and xattr preservation, exclusive publication, missing parent/source, symlink refusal, empty file and staging cleanup')
