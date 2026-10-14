from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .security import canonical, redact

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


class DB:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.path = directory / "workbench.db"
        with self.connect() as conn:
            conn.executescript(SCHEMA)
        self.path.chmod(0o600)

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
