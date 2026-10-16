from pathlib import Path

import pytest
from test_backup import seed

from xianyu_workbench import backup


@pytest.mark.parametrize('limit', ['database', 'asset', 'total', 'files', 'manifest'])
def test_create_limits_reject_before_content_reads(tmp_path, monkeypatch, limit):
    root, vault, db = seed(tmp_path)
    if limit in ('asset', 'total'):
        (root / 'assets/photo.jpg').write_bytes(b'x' * (db.path.stat().st_size + 100))
    if limit == 'database':
        monkeypatch.setattr(backup, 'MAX_TOTAL_BYTES', db.path.stat().st_size - 1)
    elif limit == 'asset':
        monkeypatch.setattr(backup, 'MAX_TOTAL_BYTES', db.path.stat().st_size + 99)
    elif limit == 'total':
        monkeypatch.setattr(backup, 'MAX_TOTAL_BYTES', db.path.stat().st_size + 100)
    elif limit == 'files':
        monkeypatch.setattr(backup, 'MAX_FILES', 2)  # DB + manifest + one asset = three
    else:
        monkeypatch.setattr(backup, 'MAX_TOTAL_BYTES', db.path.stat().st_size + 11)
    def forbidden(*args, **kwargs):
        pytest.fail('file content read before resource rejection')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    import sqlite3
    connect = sqlite3.connect
    class NoSnapshotConnection(sqlite3.Connection):
        def backup(self, *args, **kwargs):
            pytest.fail('snapshot allocated before resource rejection')
    monkeypatch.setattr(backup.sqlite3, 'connect',
                        lambda *args, **kwargs: connect(*args, **kwargs, factory=NoSnapshotConnection))
    output = tmp_path / 'rejected.zip'
    with pytest.raises(ValueError, match='限制'):
        backup.create_backup(root, output, vault)
    assert not output.exists()


def test_streaming_backup_is_accepted_by_restore_validator(tmp_path, monkeypatch):
    import zipfile
    root, vault, _ = seed(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail('whole-file read is forbidden for database and assets')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    output = tmp_path / 'good.zip'
    backup.create_backup(root, output, vault)
    stage = tmp_path / 'validated'
    stage.mkdir()
    with zipfile.ZipFile(output) as archive:
        backup.validate_archive(archive, stage, vault)
    with (stage / 'assets/photo.jpg').open('rb') as stream:
        assert stream.read() == b'fake-image'


def test_backup_rejects_foreign_key_corruption_without_output_or_source_changes(tmp_path):
    import sqlite3
    from contextlib import closing
    root, vault, db = seed(tmp_path)
    with closing(sqlite3.connect(db.path)) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute("INSERT INTO drafts(id,account_id,content,updated) VALUES('orphan','missing',?,1)",
                     (vault.seal({'title': 'fake orphan'}),))
        conn.commit()
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchone()
    before = db.path.read_bytes()
    output = tmp_path / 'invalid.zip'
    with pytest.raises(ValueError):
        backup.create_backup(root, output, vault)
    assert not output.exists()
    assert db.path.read_bytes() == before
    assert db.one("SELECT account_id FROM drafts WHERE id='orphan'")['account_id'] == 'missing'
