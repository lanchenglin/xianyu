"""Local-only asset lifecycle; historical references remain protected."""
from __future__ import annotations

import time

from .provider import Problem, asset_path
from .security import canonical


def referenced_assets(conn, vault):
    references = set()

    def visit(value):
        if isinstance(value, str):
            references.add(value)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)

    # Include archived drafts, terminal actions and private frozen settings.
    # A corrupt envelope aborts collection rather than declaring it unreferenced.
    for table, columns in (('drafts', ('content',)), ('actions', ('payload', 'result')),
                           ('settings', ('value',))):
        for column in columns:
            for row in conn.execute(f'SELECT {column} FROM {table} WHERE {column} IS NOT NULL'):
                visit(vault.open(row[0]))
    return references


def list_assets(service, account_id):
    service.provider.account(account_id)
    with service.db.connect() as conn:
        refs = referenced_assets(conn, service.vault)
        return [{**dict(row), 'referenced': row['id'] in refs}
                for row in conn.execute('SELECT id,account_id,sha256,created FROM assets WHERE account_id=? ORDER BY created DESC LIMIT 200', (account_id,))]


def recycle_asset(service, asset_id, body, actor):
    with service.db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM assets WHERE id=? AND account_id=?',
                           (asset_id, body.account_id)).fetchone()
        if not row or row['sha256'] != body.sha256:
            raise Problem('asset_conflict', '素材不存在、账号或摘要不符', 409)
        if asset_id in referenced_assets(conn, service.vault):
            raise Problem('asset_referenced', '草稿或历史审批仍引用此素材，不能删除', 409)
        root = service.s.data_dir / 'assets'
        path = root / row['filename']
        if root.is_symlink() or path.is_symlink() or path.name != asset_id + '.jpg':
            raise Problem('asset_invalid', '素材路径异常，拒绝删除', 409)
        if conn.execute('SELECT COUNT(*) FROM assets WHERE filename=?', (row['filename'],)).fetchone()[0] != 1:
            raise Problem('asset_invalid', '素材路径被重复登记，拒绝删除', 409)
        asset_path(service.s, dict(row))
        conn.execute('DELETE FROM assets WHERE id=?', (asset_id,))
        conn.execute('INSERT INTO audit(created,actor,event,target,detail) VALUES(?,?,?,?,?)',
                     (time.time(), actor, 'asset.recycled', asset_id, canonical({'account_id': body.account_id})))
    # DB first: a crash can leave an unregistered file, never a dangling reference.
    path.unlink(missing_ok=True)
    return {'id': asset_id, 'deleted': True}
