"""Bounded local imports. Each proposal still enters the sole approval queue."""
from __future__ import annotations

import time
import uuid

from pydantic import ValidationError

from .models import ActionIn, DraftIn
from .provider import Problem
from .security import digest


def preview(service, body):
    service.provider.account(body.account_id)
    rows = []
    for index, value in enumerate(body.rows):
        if 'account_id' in value:
            raise Problem('import_account', '每行不可指定账号，使用批次账号', 422)
        try:
            row = DraftIn(account_id=body.account_id, **value).model_dump(mode='json')
        except ValidationError:
            raise Problem('import_row', f'第{index + 1}行草稿字段无效', 422) from None
        service.validate_assets(body.account_id, row['images'])
        rows.append(row)
    return {'digest': digest({'account_id': body.account_id, 'rows': rows}), 'rows': rows,
            'notice': '只创建本地草稿；每条仍需单独申请、审批，不批量发布'}


def confirm(service, body):
    with service.db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        result = preview(service, body)
        if result['digest'] != body.digest:
            raise Problem('import_changed', '导入内容变化，请重新预览', 409)
        old = c.execute('SELECT * FROM draft_imports WHERE account_id=? AND idem=?',
                        (body.account_id, body.idempotency_key)).fetchone()
        if old:
            if old['digest'] != body.digest:
                raise Problem('idempotency_conflict', '幂等键已用于其他导入内容', 409)
            return {'id': old['id'], 'count': len(result['rows'])}
        import_id = uuid.uuid4().hex
        c.execute('INSERT INTO draft_imports(id,account_id,idem,digest,created) VALUES(?,?,?,?,?)',
                  (import_id, body.account_id, body.idempotency_key, body.digest, time.time()))
        for index, row in enumerate(result['rows']):
            draft_id = uuid.uuid4().hex
            c.execute('INSERT INTO drafts(id,account_id,content,updated) VALUES(?,?,?,?)',
                      (draft_id, body.account_id, service.vault.seal(row), time.time()))
            c.execute('INSERT INTO draft_import_rows(import_id,position,draft_id) VALUES(?,?,?)',
                      (import_id, index, draft_id))
    return {'id': import_id, 'count': len(result['rows'])}


def progress(service, account_id, import_id):
    batch = service.db.one('SELECT * FROM draft_imports WHERE id=? AND account_id=?', (import_id, account_id))
    if not batch:
        raise Problem('import_not_found', '导入批次不存在或账号不符', 409)
    rows = []
    for row in service.db.all('SELECT d.*,r.position FROM draft_import_rows r JOIN drafts d ON d.id=r.draft_id WHERE r.import_id=? ORDER BY r.position', (import_id,)):
        action = service.db.one('SELECT id,state FROM actions WHERE account_id=? AND idem=?',
                                (account_id, f"import:{row['id']}:{row['revision']}"))
        rows.append({'draft_id': row['id'], 'revision': row['revision'], 'archived': bool(row['archived']),
                     'title': service.vault.open(row['content'])['title'], 'action': action})
    return {'id': import_id, 'account_id': account_id, 'rows': rows}


def propose_row(service, account_id, import_id, draft_id, revision, actor):
    progress(service, account_id, import_id)
    row = service.db.one('SELECT d.* FROM draft_import_rows r JOIN drafts d ON d.id=r.draft_id '
                         'WHERE r.import_id=? AND d.id=? AND d.account_id=? AND d.revision=? AND d.archived=0',
                         (import_id, draft_id, account_id, revision))
    if not row:
        raise Problem('draft_conflict', '草稿版本、账号或状态变化', 409)
    content = service.vault.open(row['content'])
    content.pop('account_id', None)
    return service.propose(ActionIn(account_id=account_id, kind='item.publish', payload=content,
                                   idempotency_key=f'import:{draft_id}:{revision}'), actor, publish_preview=True,
                           draft_guard=(draft_id, revision))
