import sqlite3

import pytest
from filelock import FileLock, Timeout

import xianyu_workbench.db as database
from xianyu_workbench.db import DB, SCHEMA


def legacy_database(directory):
    directory.mkdir()
    path = directory / "workbench.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO accounts(id,label,mode,created) VALUES('old','旧账号','demo',1)")
    return path


def test_legacy_upgrade_preserves_data_and_sets_version(tmp_path):
    path = legacy_database(tmp_path / "data")
    db = DB(path.parent)
    assert db.one("PRAGMA user_version")["user_version"] == 1
    assert db.one("SELECT label FROM accounts WHERE id='old'")["label"] == "旧账号"


def test_future_version_rejected_without_modification(tmp_path):
    path = legacy_database(tmp_path / "data")
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=999")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="未来版本"):
        DB(path.parent)
    assert path.read_bytes() == before


def test_migration_backup_includes_committed_wal_snapshot(tmp_path):
    path = legacy_database(tmp_path / "data")
    with sqlite3.connect(path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE accounts SET label='WAL 中的已提交数据'")
        writer.commit()
        DB(path.parent)
        backups = list((path.parent / "backups").glob("*.db"))
        assert len(backups) == 1
        with sqlite3.connect(backups[0]) as snapshot:
            assert snapshot.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 0
            assert snapshot.execute("SELECT label FROM accounts").fetchone()[0] == "WAL 中的已提交数据"
        DB(path.parent)
        assert list((path.parent / "backups").glob("*.db")) == backups


def test_failed_migration_rolls_back_schema_data_and_version(tmp_path, monkeypatch):
    path = legacy_database(tmp_path / "data")

    def fail(conn):
        conn.execute("CREATE TABLE partial (id INTEGER)")
        conn.execute("UPDATE accounts SET label='损坏'")
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(database, "MIGRATIONS", (database.initial_schema, fail))
    with pytest.raises(RuntimeError, match="injected"):
        DB(path.parent)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        assert conn.execute("SELECT label FROM accounts").fetchone()[0] == "旧账号"
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone()
    assert len(list((path.parent / "backups").glob("*.db"))) == 1


def test_migration_refused_while_server_owns_instance_lock(tmp_path):
    path = legacy_database(tmp_path / "data")
    with FileLock(str(path.parent / "server.lock"), timeout=0):
        with pytest.raises(Timeout):
            DB(path.parent)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
