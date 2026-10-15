import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing

import pytest
from cryptography.fernet import Fernet

from xianyu_workbench.db import DB
from xianyu_workbench.security import Vault


def seed(tmp_path):
    root = tmp_path / 'data'
    vault = Vault(Fernet.generate_key().decode())
    db = DB(root, vault)
    db.execute("INSERT INTO accounts(id,label,mode,secret,created) VALUES('a','fake','demo',?,1)",
               (vault.seal({'fake': 'private-cookie'}),))
    (root / 'assets').mkdir()
    data = b'fake-image'
    (root / 'assets' / 'photo.jpg').write_bytes(data)
    db.execute("INSERT INTO assets VALUES('img','a','photo.jpg',?,1)", (hashlib.sha256(data).hexdigest(),))
    (root / '.env').write_text('SECRET-NOT-EXPORTED')
    return root, vault, db


def test_backup_contains_consistent_database_assets_and_key_proof(tmp_path):
    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    output = tmp_path / 'private.zip'
    with closing(sqlite3.connect(db.path)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("UPDATE accounts SET label='committed WAL'")
        writer.commit()
        backup.create_backup(root, output, vault)
    with zipfile.ZipFile(output) as z:
        assert set(z.namelist()) == {'manifest.json', 'workbench.db', 'assets/photo.jpg'}
        manifest = json.loads(z.read('manifest.json'))
        assert vault.open(manifest['key_check']) == {'purpose': 'xianyu-backup-v1'}
        snapshot = tmp_path / 'snapshot.db'
        snapshot.write_bytes(z.read('workbench.db'))
        assert z.read('assets/photo.jpg') == b'fake-image'
    with closing(sqlite3.connect(snapshot)) as c:
        assert c.execute('SELECT label FROM accounts').fetchone()[0] == 'committed WAL'
    assert b'SECRET-NOT-EXPORTED' not in output.read_bytes()


def test_restore_destroyed_copy_pauses_and_never_replays(tmp_path):
    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    for state in ['pending', 'approved', 'running', 'unconfirmed', 'submitted', 'simulated']:
        db.execute('INSERT INTO actions(id,account_id,kind,payload,digest,mode,idem,state,created,expires) '
                   'VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (state, 'a', 'message.send', vault.seal({}), 'hash', 'demo', state, state, 1, 9999999999))
    db.execute("INSERT INTO monitors(id,account_id,query,filters,interval_s) VALUES('m','a','fake','{}',300)")
    output = tmp_path / 'private.zip'
    backup.create_backup(root, output, vault)
    db.execute("DELETE FROM actions")
    (root / 'assets' / 'photo.jpg').write_bytes(b'destroyed')
    rollback = backup.restore_backup(root, output, vault)
    assert rollback.is_dir()
    assert (root / 'assets' / 'photo.jpg').read_bytes() == b'fake-image'
    restored = DB(root, vault)
    states = {r['id']: r['state'] for r in restored.all('SELECT id,state FROM actions')}
    assert states == {'pending': 'expired', 'approved': 'expired', 'running': 'unconfirmed',
                      'unconfirmed': 'unconfirmed', 'submitted': 'submitted', 'simulated': 'simulated'}
    assert restored.one('SELECT paused FROM accounts')['paused'] == 1
    assert restored.one('SELECT enabled FROM monitors')['enabled'] == 0
    import base64

    from xianyu_workbench.config import Settings
    from xianyu_workbench.service import Service
    key = base64.urlsafe_b64encode(vault.fernet._signing_key + vault.fernet._encryption_key).decode()
    service = Service(Settings(root, 'a' * 40, 'b' * 40, key, worker_enabled=False))
    service.start()
    assert not service.run_once()
    restored.execute('UPDATE accounts SET paused=0')
    assert not service.run_once()
    service.close()


@pytest.mark.parametrize('damage', ['hash', 'traversal', 'schema', 'extra', 'symlink', 'bomb'])
def test_invalid_archive_rejected_before_touching_existing_data(tmp_path, damage):
    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    good = tmp_path / 'good.zip'
    backup.create_backup(root, good, vault)
    with zipfile.ZipFile(good) as z:
        files = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(files['manifest.json'])
    if damage == 'hash':
        files['assets/photo.jpg'] = b'tampered'
    elif damage == 'traversal':
        manifest['files']['../escaped'] = {'size': 3, 'sha256': hashlib.sha256(b'bad').hexdigest()}
        files['../escaped'] = b'bad'
    elif damage == 'schema':
        manifest['schema'] = 999
    elif damage == 'extra':
        files['extra'] = b'unlisted'
    elif damage == 'bomb':
        monkey_limit = backup.MAX_TOTAL_BYTES
        backup.MAX_TOTAL_BYTES = 10
    files['manifest.json'] = json.dumps(manifest).encode()
    bad = tmp_path / 'bad.zip'
    with zipfile.ZipFile(bad, 'w') as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            if damage == 'symlink' and name == 'assets/photo.jpg':
                info.create_system = 3
                info.external_attr = 0o120777 << 16
            z.writestr(info, data)
    before = db.path.read_bytes()
    try:
        with pytest.raises(ValueError):
            backup.restore_backup(root, bad, vault)
    finally:
        if damage == 'bomb':
            backup.MAX_TOTAL_BYTES = monkey_limit
    assert db.path.read_bytes() == before
    assert (root / 'assets/photo.jpg').read_bytes() == b'fake-image'
    assert not (tmp_path / 'escaped').exists()


def test_wrong_key_and_active_instance_preserve_data(tmp_path):
    from filelock import FileLock, Timeout

    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    output = tmp_path / 'good.zip'
    backup.create_backup(root, output, vault)
    before = db.path.read_bytes()
    with pytest.raises(ValueError):
        backup.restore_backup(root, output, Vault(Fernet.generate_key().decode()))
    with FileLock(str(root / 'server.lock')):
        with pytest.raises(Timeout):
            backup.restore_backup(root, output, vault)
        with pytest.raises(Timeout):
            backup.create_backup(root, tmp_path / 'locked.zip', vault)
    assert db.path.read_bytes() == before


def test_restore_install_failure_rolls_back(tmp_path, monkeypatch):
    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    output = tmp_path / 'good.zip'
    backup.create_backup(root, output, vault)
    db.execute("UPDATE accounts SET label='current data'")
    replace = backup.os.replace
    def fail(source, target):
        if source.parent.name.startswith('.restore-') and source.name == 'assets':
            raise OSError('injected install failure')
        return replace(source, target)
    monkeypatch.setattr(backup.os, 'replace', fail)
    with pytest.raises(OSError):
        backup.restore_backup(root, output, vault)
    assert db.one('SELECT label FROM accounts')['label'] == 'current data'
    assert (root / 'assets/photo.jpg').read_bytes() == b'fake-image'


def test_backup_refuses_package_that_exceeds_restore_limit(tmp_path, monkeypatch):
    from xianyu_workbench import backup
    root, vault, _ = seed(tmp_path)
    monkeypatch.setattr(backup, 'MAX_TOTAL_BYTES', 10)
    output = tmp_path / 'too-big.zip'
    with pytest.raises(ValueError):
        backup.create_backup(root, output, vault)
    assert not output.exists()


def test_restore_v2_archive_migrates_drafts_before_install(tmp_path):
    from xianyu_workbench import backup
    root, vault, db = seed(tmp_path)
    output = tmp_path / 'new.zip'
    backup.create_backup(root, output, vault)
    with zipfile.ZipFile(output) as z:
        files = {name: z.read(name) for name in z.namelist()}
    old_db = tmp_path / 'old.db'
    old_db.write_bytes(files['workbench.db'])
    with closing(sqlite3.connect(old_db)) as c:
        c.execute('ALTER TABLE drafts DROP COLUMN revision')
        c.execute('ALTER TABLE drafts DROP COLUMN archived')
        c.execute('PRAGMA user_version=2')
        c.execute("INSERT INTO drafts VALUES('d','a',?,123)", (vault.seal({'title': 'old draft'}),))
        c.commit()
    files['workbench.db'] = old_db.read_bytes()
    manifest = json.loads(files['manifest.json'])
    manifest['schema'] = 2
    manifest['files']['workbench.db'] = {'size': len(files['workbench.db']),
                                        'sha256': hashlib.sha256(files['workbench.db']).hexdigest()}
    files['manifest.json'] = json.dumps(manifest).encode()
    old_archive = tmp_path / 'old.zip'
    with zipfile.ZipFile(old_archive, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    backup.restore_backup(root, old_archive, vault)
    assert db.one('SELECT revision,archived FROM drafts') == {'revision': 1, 'archived': 0}
    assert vault.open(db.one('SELECT content FROM drafts')['content']) == {'title': 'old draft'}


def test_failed_retry_keeps_previous_interruption_guard(tmp_path, monkeypatch):
    from xianyu_workbench import backup
    root, vault, _ = seed(tmp_path)
    output = tmp_path / 'good.zip'
    backup.create_backup(root, output, vault)
    marker = root / 'restore-in-progress'
    marker.write_text('previous-rollback')
    replace = backup.os.replace
    def fail(source, target):
        if source.parent.name.startswith('.restore-') and source.name == 'assets':
            raise OSError('injected')
        return replace(source, target)
    monkeypatch.setattr(backup.os, 'replace', fail)
    with pytest.raises(OSError):
        backup.restore_backup(root, output, vault)
    assert marker.read_text() == 'previous-rollback'
    with pytest.raises(ValueError):
        DB(root, vault)


def test_service_constructed_before_restore_still_refuses_interrupted_start(tmp_path):
    from xianyu_workbench.config import Settings
    from xianyu_workbench.service import Service
    service = Service(Settings(tmp_path, 'a' * 40, 'b' * 40, Fernet.generate_key().decode(), worker_enabled=False))
    (tmp_path / 'restore-in-progress').write_text('interrupted')
    with pytest.raises(ValueError, match='恢复'):
        service.start()


def test_interrupted_restore_marker_refuses_startup(tmp_path):
    root, vault, _ = seed(tmp_path)
    (root / 'restore-in-progress').write_text('interrupted')
    with pytest.raises(ValueError, match='恢复'):
        DB(root, vault)


def test_admin_cli_backup_restore_without_env_file(tmp_path):
    import os
    import subprocess
    import sys

    from xianyu_workbench import backup
    root = tmp_path / 'data'
    key = Fernet.generate_key().decode()
    vault = Vault(key)
    db = DB(root, vault)
    db.execute("INSERT INTO accounts(id,label,mode,created) VALUES('a','fake','demo',1)")
    output = tmp_path / 'backup.zip'
    env = {**os.environ, 'XY_VAULT_KEY': key}
    command = [sys.executable, '-m', 'xianyu_workbench.cli']
    result = subprocess.run(command + ['backup', '--data-dir', str(root), '--output', str(output)],
                            env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    db.execute("UPDATE accounts SET label='destroyed'")
    result = subprocess.run(command + ['restore', '--data-dir', str(root), '--archive', str(output), '--offline'],
                            env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert db.one('SELECT label FROM accounts')['label'] == 'fake'
    assert key not in result.stdout + result.stderr
    env['XY_VAULT_KEY'] = Fernet.generate_key().decode()
    wrong = subprocess.run(command + ['restore', '--data-dir', str(root), '--archive', str(output), '--offline'],
                           env=env, cwd=tmp_path, capture_output=True, text=True)
    assert wrong.returncode != 0
    assert 'Traceback' not in wrong.stderr
    assert db.one('SELECT label FROM accounts')['label'] == 'fake'
    assert backup.MAX_TOTAL_BYTES > 0


@pytest.mark.parametrize('which', ['assets', 'workbench.db', 'restore-in-progress'])
def test_backup_rejects_symlink_source(tmp_path, which):
    from xianyu_workbench import backup
    root, vault, _ = seed(tmp_path)
    source = root / which
    if which == 'restore-in-progress':
        source.write_text('interrupted')
    moved = tmp_path / which
    source.rename(moved)
    source.symlink_to(moved, target_is_directory=which == 'assets')
    with pytest.raises(ValueError):
        backup.create_backup(root, tmp_path / 'bad.zip', vault)
