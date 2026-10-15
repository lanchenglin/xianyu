from __future__ import annotations

import os
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from cryptography.fernet import InvalidToken
from filelock import FileLock

from .security import Vault, canonical, redact

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, mode TEXT NOT NULL,
 uid TEXT NOT NULL DEFAULT '', secret TEXT, paused INTEGER NOT NULL DEFAULT 0,
 pause_reason TEXT NOT NULL DEFAULT '', last_call REAL NOT NULL DEFAULT 0,
 last_write REAL NOT NULL DEFAULT 0, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
 kind TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
 mode TEXT NOT NULL, idem TEXT NOT NULL, state TEXT NOT NULL,
 created REAL NOT NULL, approved_at REAL, expires REAL NOT NULL,
 result TEXT, error TEXT, UNIQUE(account_id, idem)
);
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
 filename TEXT NOT NULL, sha256 TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
 content TEXT NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog (
 account_id TEXT NOT NULL REFERENCES accounts(id), item_id TEXT NOT NULL,
 owned INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL, updated REAL NOT NULL,
 PRIMARY KEY(account_id,item_id)
);
CREATE TABLE IF NOT EXISTS monitors (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
 query TEXT NOT NULL, filters TEXT NOT NULL, interval_s INTEGER NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1, next_run REAL NOT NULL DEFAULT 0,
 last_run REAL, last_error TEXT, seen TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, monitor_id TEXT NOT NULL,
 content TEXT NOT NULL, created REAL NOT NULL, read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL,
 actor TEXT NOT NULL, event TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS action_queue ON actions(state,created);
CREATE INDEX IF NOT EXISTS monitor_due ON monitors(enabled,next_run);
"""


def initial_schema(conn):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def reconciliation_schema(conn):
    conn.execute("""CREATE TABLE reconciliations (
        action_id TEXT PRIMARY KEY REFERENCES actions(id),
        account_id TEXT NOT NULL REFERENCES accounts(id),
        outcome TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at REAL NOT NULL,
        idem TEXT NOT NULL, UNIQUE(account_id, idem)
    )""")


def draft_revision_schema(conn):
    conn.execute('ALTER TABLE drafts ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
    conn.execute('ALTER TABLE drafts ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')


def notification_state_schema(conn):
    conn.execute('ALTER TABLE notifications ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')


def notification_delivery_schema(conn):
    conn.execute('''CREATE TABLE notification_deliveries (
        id TEXT PRIMARY KEY, notification_id INTEGER NOT NULL UNIQUE REFERENCES notifications(id),
        state TEXT NOT NULL, attempts INTEGER NOT NULL, next_attempt REAL NOT NULL,
        updated REAL NOT NULL, error TEXT
    )''')


MIGRATIONS = (initial_schema, reconciliation_schema, draft_revision_schema,
              notification_state_schema, notification_delivery_schema)


class DB:
    def __init__(self, directory: Path, vault: Vault | None = None):
        if (directory / 'restore-in-progress').exists():
            raise ValueError('上次恢复未完成，拒绝启动；请离线检查回滚副本并重新恢复')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.path = directory / "workbench.db"
        with FileLock(str(directory / "server.lock"), timeout=0):
            self.migrate(vault)
        self.path.chmod(0o600)

    def migrate(self, vault: Vault | None):
        with closing(sqlite3.connect(self.path)) as probe:
            if probe.execute("PRAGMA user_version").fetchone()[0] > len(MIGRATIONS):
                raise ValueError("数据库为未知未来版本，拒绝启动；请使用匹配版本程序")
            if vault:
                self.validate_key(probe, vault)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            existing = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
            if existing and version < len(MIGRATIONS):
                self.backup(version)
            for index in range(version, len(MIGRATIONS)):
                MIGRATIONS[index](conn)
                conn.execute(f"PRAGMA user_version={index + 1}")
        self.path.chmod(0o600)

    @staticmethod
    def validate_key(conn, vault: Vault):
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        encrypted = {"accounts": ("secret",), "actions": ("payload", "result"),
                     "drafts": ("content",), "settings": ("value",),
                     "reconciliations": ("evidence",)}
        try:
            for table, columns in encrypted.items():
                if table not in tables:
                    continue
                for column in columns:
                    for row in conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"):
                        vault.open(row[0])
        except (InvalidToken, ValueError, TypeError):
            raise ValueError("密钥不匹配或加密数据损坏，拒绝启动；原数据未修改") from None

    def backup(self, version: int) -> Path:
        directory = self.path.parent / "backups"
        directory.mkdir(exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        path = directory / f"before-v{version}-{uuid.uuid4().hex}.db"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            # A separate reader sees committed WAL data while the migration holds the writer lock.
            with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(path)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("迁移前备份校验失败，停止升级")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def all(self, sql: str, params=()) -> list[dict]:
        with self.connect() as c:
            return [dict(x) for x in c.execute(sql, params)]

    def one(self, sql: str, params=()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params=()) -> None:
        with self.connect() as c:
            c.execute(sql, params)

    def audit(self, actor: str, event: str, target: str = "", detail: Any = None) -> None:
        self.execute("INSERT INTO audit(created,actor,event,target,detail) VALUES(?,?,?,?,?)",
                     (time.time(), actor, event, target, canonical(redact(detail or {}))))
