"""Bounded administrator grants; the only executor remains the actions queue."""
import copy
import secrets
import time
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field

from .models import Model
from .provider import Problem
from .publish_preview import preflight
from .security import digest


class DailyPublishIn(Model):
    enabled: bool = False
    generation_mode: Literal['disabled', 'timestamp_random_v1'] = 'disabled'
    source_action_id: str = Field(min_length=1, max_length=64)
    time: str = Field(default='09:00', pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    evidence: str = Field(min_length=10, max_length=2000)
    confirm: Literal['授权每日最多一条']


class DailyPublish:
    def __init__(self, service):
        self.s = service

    @staticmethod
    def unresolved(conn, account_id):
        return conn.execute("SELECT 1 FROM daily_publish_dates d LEFT JOIN actions a ON a.id=d.action_id WHERE d.account_id=? AND (a.id IS NULL OR a.state!='submitted') LIMIT 1", (account_id,)).fetchone() is not None

    def read(self, account_id):
        policy = self._policy(account_id)
        with self.s.db.connect() as c:
            unresolved = self.unresolved(c, account_id)
        reason = 'daily_unresolved' if unresolved else None
        if not reason and not policy['enabled']:
            reason = policy.get('blocked_reason') or 'disabled'
        if not reason and policy.get('generation_mode') != 'timestamp_random_v1':
            reason = 'generation_reauthorization_required'
        if not reason and (not self.s.s.live_enabled or not self.s.s.publish_enabled):
            reason = 'executor_disabled'
        if not reason:
            try:
                account = self.s.provider.account(account_id)
                if account['paused']:
                    raise Problem('account_paused', '账号暂停', 409)
                self.s.observation.guard(account_id)
                preflight(self.s, account, policy['payload'], executing=True)
            except Problem as exc:
                reason = exc.code
        return {**policy, 'effective': reason is None, 'blocked_reason': reason}

    def _policy(self, account_id):
        self.s.provider.account(account_id)
        row = self.s.db.one('SELECT value FROM settings WHERE key=?', ('daily-publish:' + account_id,))
        return self.s.vault.open(row['value']) if row else {'enabled': False, 'timezone': 'Asia/Shanghai', 'time': '09:00'}

    def configure(self, account_id, body):
        s = self.s
        account = s.provider.account(account_id)
        row = s.db.one('SELECT * FROM actions WHERE id=? AND account_id=?', (body.source_action_id, account_id))
        result = s.vault.open(row['result']) if row and row['result'] else {}
        if (not row or row['kind'] != 'item.publish' or row['mode'] != 'live' or row['state'] != 'submitted'
                or not all(result.get(k) is True for k in ('ownership_verified', 'status_verified', 'content_verified'))):
            raise Problem('publish_verification_required', '需要同账号工作台执行器精确回读成功的 action 和管理员真实证据', 409)
        if body.enabled and body.generation_mode != 'timestamp_random_v1':
            raise Problem('generation_mode_required', '需管理员显式授权已取证的毫秒加随机整数生成模式', 409)
        payload = s.vault.open(row['payload'])
        preflight(s, account, payload, executing=True)
        s.observation.guard(account_id)
        if account['paused']:
            raise Problem('account_paused', '账号暂停', 409)
        value = {**body.model_dump(), 'timezone': 'Asia/Shanghai', 'max_per_day': 1,
                 'revision': uuid.uuid4().hex, 'payload': payload, 'blocked_reason': None}
        with s.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if body.enabled and self.unresolved(c, account_id):
                raise Problem('daily_unresolved', '每日执行存在未确定结果，禁止重新授权绕过', 409)
            c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                      ('daily-publish:' + account_id, s.vault.seal(value)))
        s.db.audit('admin', 'daily_publish.configured', account_id, {'revision': value['revision'], 'enabled': body.enabled})
        return self.read(account_id)

    def revoke(self, account_id, reason='revoked'):
        s = self.s
        with s.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT value FROM settings WHERE key=?', ('daily-publish:' + account_id,)).fetchone()
            if row:
                value = s.vault.open(row['value'])
                value.update(enabled=False, revision=uuid.uuid4().hex, blocked_reason=reason)
                c.execute('UPDATE settings SET value=? WHERE key=?', (s.vault.seal(value), 'daily-publish:' + account_id))
        s.db.audit('admin', 'daily_publish.revoked', account_id, {'reason': reason})
        return self.read(account_id)

    def guard(self, account_id, action_id):
        s = self.s
        entry = s.db.one('SELECT * FROM daily_publish_dates WHERE action_id=?', (action_id,))
        if not entry:
            return
        policy = self._policy(account_id)
        if not policy['enabled'] or policy['revision'] != entry['revision']:
            raise Problem('daily_revoked', '每日授权已撤销或改变', 409)
        s.observation.guard(account_id)
        account = s.provider.account(account_id)
        if account['paused']:
            raise Problem('account_paused', '账号暂停', 409)
        preflight(s, account, policy['payload'], executing=True)

    def comparison_payload(self, account_id, action_id, payload):
        entry = self.s.db.one('SELECT * FROM daily_publish_dates WHERE account_id=? AND action_id=?', (account_id, action_id))
        if not entry:
            return payload
        policy = self._policy(account_id)
        if (not policy['enabled'] or policy.get('generation_mode') != 'timestamp_random_v1'
                or policy['revision'] != entry['revision']):
            raise Problem('daily_revoked', '每日生成授权已失效', 409)
        code = payload['_publish_snapshot']['executor']['template']['uniqueCode']
        reservation = self.s.db.one('SELECT value FROM settings WHERE key=?', ('publish-code:' + digest(code),))
        if not reservation or self.s.vault.open(reservation['value']) != {'account_id': account_id, 'action_id': action_id}:
            raise Problem('daily_code_changed', '生成码与首次冻结记录不一致', 409)
        compared = copy.deepcopy(payload)
        compared['_publish_snapshot']['executor']['template']['uniqueCode'] = policy['payload']['_publish_snapshot']['executor']['template']['uniqueCode']
        if digest(compared) != digest(policy['payload']):
            raise Problem('daily_payload_changed', '每日授权仅允许受证 uniqueCode 字段变化', 409)
        return compared

    def verify_new_item(self, account_id, action_id, item_id):
        if not self.s.db.one('SELECT 1 FROM daily_publish_dates WHERE action_id=?', (action_id,)):
            return
        for row in self.s.db.all("SELECT result FROM actions WHERE account_id=? AND id!=? AND kind='item.publish' AND result IS NOT NULL", (account_id, action_id)):
            result = self.s.vault.open(row['result'])
            if str(result.get('item_id', '')) == item_id:
                raise ValueError('daily publish returned an existing item')

    def tick(self, account_id, *, now=None):
        s = self.s
        now = time.time() if now is None else now
        with s.db.connect() as c:
            if self.unresolved(c, account_id):
                return {'reason': 'daily_unresolved'}
        policy = self._policy(account_id)
        if not policy['enabled']:
            return {'reason': 'disabled'}
        if policy.get('generation_mode') != 'timestamp_random_v1':
            self.revoke(account_id, 'generation_reauthorization_required')
            return {'reason': 'generation_reauthorization_required'}
        local = datetime.fromtimestamp(now, ZoneInfo('Asia/Shanghai'))
        if local.strftime('%H:%M') != policy['time']:
            return {'reason': 'outside_minute'}
        if not s.s.live_enabled or not s.s.publish_enabled:
            return {'reason': 'executor_disabled'}
        try:
            account = s.provider.account(account_id)
            s.observation.guard(account_id)
            if account['paused']:
                raise Problem('account_paused', '账号暂停', 409)
            preflight(s, account, policy['payload'], executing=True)
        except Problem:
            self.revoke(account_id, 'authority_changed')
            return {'reason': 'authority_changed'}
        action_id = uuid.uuid4().hex
        date = local.date().isoformat()
        with s.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            current = c.execute('SELECT value FROM settings WHERE key=?', ('daily-publish:' + account_id,)).fetchone()
            if not current or s.vault.open(current['value']) != policy:
                return {'reason': 'authority_changed'}
            if self.unresolved(c, account_id):
                return {'reason': 'daily_unresolved'}
            if c.execute('SELECT 1 FROM daily_publish_dates WHERE account_id=? AND local_date=?', (account_id, date)).fetchone():
                return {'reason': 'date_used'}
            created = time.time()
            # One draw only. Collision aborts this transaction before any external write.
            code = str(int(created * 1000)) + str(secrets.randbelow(1000))
            key = 'publish-code:' + digest(code)
            if c.execute('SELECT 1 FROM settings WHERE key=?', (key,)).fetchone():
                return {'reason': 'generation_collision'}
            for prior in c.execute("SELECT payload FROM actions WHERE kind='item.publish'").fetchall():
                template = s.vault.open(prior['payload']).get('_publish_snapshot', {}).get('executor', {}).get('template', {})
                if template.get('uniqueCode') == code:
                    return {'reason': 'generation_collision'}
            payload = copy.deepcopy(policy['payload'])
            payload['_publish_snapshot']['executor']['template']['uniqueCode'] = code
            signature = digest({'account_id': account_id, 'kind': 'item.publish', 'payload': payload, 'mode': 'live'})
            c.execute('INSERT INTO settings(key,value) VALUES(?,?)',
                      (key, s.vault.seal({'account_id': account_id, 'action_id': action_id})))
            c.execute('INSERT INTO actions(id,account_id,kind,payload,digest,mode,idem,state,created,approved_at,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (action_id, account_id, 'item.publish', s.vault.seal(payload), signature, 'live',
                       'daily:' + date, 'approved', created, created, created + 60 - local.second))
            c.execute('INSERT INTO daily_publish_dates VALUES(?,?,?,?)', (account_id, date, action_id, policy['revision']))
        s.db.audit('admin_policy', 'daily_publish.authorized', action_id, {'revision': policy['revision'], 'date': date})
        result = s.execute_one(action_id, signature)
        if result['state'] != 'submitted':
            self.revoke(account_id, 'result_not_verified')
        return {'action_id': action_id, 'state': result['state']}
