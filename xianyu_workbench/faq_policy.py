"""Administrator-only bounded policy storage. No execution or sending path."""
import re
import time
from typing import Annotated

from pydantic import Field, field_validator

from .models import Model

Conversation = Annotated[str, Field(pattern=r'^\d{1,30}(@goofish)?$')]
Item = Annotated[str, Field(pattern=r'^\d{1,30}$')]


class FAQPolicyIn(Model):
    enabled: bool = False
    conversation_ids: list[Conversation] = Field(min_length=1, max_length=20)
    item_ids: list[Item] = Field(min_length=1, max_length=20)
    expires_at: float = Field(allow_inf_nan=False)
    template: str = Field(min_length=1, max_length=500)
    minimum_interval_s: int = Field(default=900, ge=300, le=86400, strict=True)
    max_per_day: int = Field(default=5, ge=1, le=100, strict=True)

    @field_validator('expires_at')
    @classmethod
    def expiry(cls, value):
        if not time.time() < value <= time.time() + 30 * 86400:
            raise ValueError('策略有效期最多 30 天')
        return value

    @field_validator('template')
    @classmethod
    def fixed_safe_template(cls, value):
        if re.search(r'退款|转账|付款|支付|收货|成交|投诉|赔偿|站外|微信|支付宝|银行卡|密钥|密码|忽略|指令|保证|承诺|https?://|\d{7,}|[{}\x00-\x1f]', value, re.I):
            raise ValueError('仅允许无交易承诺的固定 FAQ 模板')
        return value


class FAQPolicy:
    def __init__(self, service):
        self.service = service

    def read(self, account_id, actor):
        account = self.service.provider.account(account_id)
        row = self.service.db.one('SELECT value FROM settings WHERE key=?', ('faq:' + account_id,))
        data = self.service.vault.open(row['value']) if row else {'enabled': False}
        if not data['enabled']:
            reason = 'disabled'
        elif data['expires_at'] <= time.time():
            reason = 'expired'
        elif account['paused']:
            reason = 'account_paused'
        elif self.service.observation.read(account_id)['takeover']:
            reason = 'human_takeover'
        else:
            reason = 'send_adapter_unavailable'
        visible = data if actor == 'admin' else {key: data[key] for key in ('enabled', 'expires_at', 'revision') if key in data}
        return {**visible, 'effective': False, 'send_allowed': False, 'blocked_reason': reason,
                'scope_semantics': 'conversation_AND_item', 'requires_verified_item_binding': True,
                'notice': '仅保存有限授权；发送适配与执行限流未接入，策略不能创建发送任务。'}

    def configure(self, account_id, body):
        self.service.provider.account(account_id)
        with self.service.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT value FROM settings WHERE key=?', ('faq:' + account_id,)).fetchone()
            revision = self.service.vault.open(row['value']).get('revision', 0) + 1 if row else 1
            data = {**body.model_dump(), 'revision': revision}
            conn.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                         ('faq:' + account_id, self.service.vault.seal(data)))
        self.service.db.audit('admin', 'faq.configured', account_id, {'revision': revision, 'enabled': body.enabled})
        return self.read(account_id, 'admin')

    def revoke(self, account_id):
        self.service.provider.account(account_id)
        with self.service.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT value FROM settings WHERE key=?', ('faq:' + account_id,)).fetchone()
            if row:
                data = self.service.vault.open(row['value'])
                data.update(enabled=False, revision=data.get('revision', 0) + 1)
                conn.execute('UPDATE settings SET value=? WHERE key=?',
                             (self.service.vault.seal(data), 'faq:' + account_id))
        self.service.db.audit('admin', 'faq.revoked', account_id)
        return self.read(account_id, 'admin')
