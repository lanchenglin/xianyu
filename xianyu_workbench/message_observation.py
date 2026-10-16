"""Low-frequency last-message observation; never a sending authority."""
import time

from pydantic import Field

from .models import Model


class ObservationIn(Model):
    enabled: bool = False
    interval_s: int = Field(default=900, ge=300, le=86400, strict=True)


class MessageObservation:
    def __init__(self, service):
        self.service = service
        self.db = service.db

    def read(self, account_id):
        account = self.service.provider.account(account_id)
        row = self.db.one('SELECT * FROM message_observation WHERE account_id=?', (account_id,))
        result = row or {'account_id': account_id, 'enabled': False, 'interval_s': 900,
                         'takeover': False, 'next_run': 0, 'failures': 0,
                         'last_error': None, 'last_run': None, 'revision': 0}
        return {**result, 'enabled': bool(result['enabled']), 'takeover': bool(result['takeover']),
                'account_paused': bool(account['paused']),
                'coverage': 'conversation_last_message_samples', 'send_allowed': False}

    def guard(self, account_id):
        from .provider import Problem
        state = self.read(account_id)
        if state['takeover']:
            raise Problem('human_takeover', '人工已接管；停止采集和草稿，不授予发送权限', 409)

    def takeover(self, account_id, active, actor):
        self.service.provider.account(account_id)
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if active:
                conn.execute("UPDATE actions SET state='blocked',error='人工接管后原消息申请失效，需重新申请审批' "
                             "WHERE account_id=? AND kind='message.send' AND state IN ('pending','approved')",
                             (account_id,))
            conn.execute('INSERT INTO message_observation(account_id,takeover) VALUES(?,?) '
                         'ON CONFLICT(account_id) DO UPDATE SET takeover=excluded.takeover, '
                         'next_run=?+interval_s,revision=revision+1', (account_id, active, time.time()))
        self.db.audit(actor, 'message.takeover' if active else 'message.released', account_id)
        return self.read(account_id)

    def run_once(self):
        from .operations_cache import OperationsCache
        from .provider import Problem

        now = time.time()
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT m.* FROM message_observation m JOIN accounts a ON a.id=m.account_id '
                               'WHERE m.enabled=1 AND m.takeover=0 AND a.paused=0 AND m.next_run<=? '
                               'ORDER BY m.next_run LIMIT 1', (now,)).fetchone()
            if not row:
                return False
            row = dict(row)
            conn.execute('UPDATE message_observation SET next_run=? WHERE account_id=?',
                         (now + row['interval_s'], row['account_id']))
        error = None
        try:
            OperationsCache(self.service).sync(row['account_id'], 'messages')
        except Problem as exc:
            error = exc.code
        except Exception:
            error = 'collection_failed'
        failures = min(row['failures'] + 1, 16) if error else 0
        delay = min(row['interval_s'] * 2 ** failures, 86400)
        self.db.execute('UPDATE message_observation SET next_run=?,last_run=?,failures=?,last_error=? '
                        'WHERE account_id=? AND revision=?',
                        (time.time() + delay, now, failures, error, row['account_id'], row['revision']))
        return True

    def configure(self, account_id, body):
        self.service.provider.account(account_id)
        with self.db.connect() as conn:
            conn.execute('INSERT INTO message_observation(account_id,enabled,interval_s,next_run) VALUES(?,?,?,?) '
                         'ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled, '
                         'interval_s=excluded.interval_s,next_run=excluded.next_run,revision=revision+1',
                         (account_id, body.enabled, body.interval_s, time.time() + body.interval_s))
        self.db.audit('admin', 'message.observation.configured', account_id,
                      {'enabled': body.enabled, 'interval_s': body.interval_s})
        return self.read(account_id)
