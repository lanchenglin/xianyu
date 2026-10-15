"""Explicit local draft generation, never model calls, proposals or platform writes."""
import re
import time
import uuid

from .provider import Problem


class MessageReplies:
    def __init__(self, service):
        self.service = service

    def generate(self, account_id, sample_id):
        service = self.service
        account = service.provider.account(account_id)
        if account['paused']:
            raise Problem('account_paused', '账号暂停，交人工处理', 409)
        if not re.fullmatch('[a-f0-9]{64}', sample_id):
            raise Problem('not_found', '消息样本不存在', 404)
        row = service.db.one("SELECT * FROM operation_records WHERE account_id=? AND kind='messages' AND record_key=?",
                             (account_id, sample_id))
        if not row:
            raise Problem('not_found', '消息样本不存在', 404)
        latest = service.db.one("SELECT state,fetched_at FROM operation_syncs WHERE account_id=? AND kind='messages' ORDER BY id DESC LIMIT 1",
                                (account_id,))
        if (not latest or latest['state'] != 'partial' or row['fetched_at'] != latest['fetched_at']
                or time.time() - row['fetched_at'] > 3600):
            raise Problem('stale_sample', '样本过期或最后采集失败，请重新只读采集后人工选择', 409)
        item = service.vault.open(row['payload'])
        if (item.get('direction') != 'incoming' or item.get('body_status') != 'available'
                or item.get('recipient_verified') is not True or not item.get('peer_uid')
                or item.get('sender_uid') != item['peer_uid']):
            raise Problem('message_ineligible', '仅可为已核验对方普通文本生成草稿', 409)
        text = item['body']
        # Conservative local triage, not a comprehensive content classifier.
        if re.search(r'退款|转账|付款|支付|收货|成交|投诉|赔偿|站外|微信|支付宝|银行卡|密钥|密码|忽略|指令|https?://|\d{7,}', text, re.I):
            raise Problem('manual_required', '交易、隐私或指令类内容请人工处理', 409)
        # No buyer text is sent to an external model or interpolated into the draft.
        result = {'text': '您好，已收到您的咨询，我先核实商品情况后再答复您。',
                  'state': 'draft', 'source': 'local_template', 'requires_approval': True,
                  'sent': False, 'cid': item['cid'], 'peer_uid': item['peer_uid'],
                  'notice': '本地建议，仅供人工核对；不创建发送提案，CDP 写入仍禁止。'}
        with service.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = conn.execute('SELECT id,payload FROM message_reply_drafts WHERE account_id=? AND sample_id=?',
                               (account_id, sample_id)).fetchone()
            if old:
                return {'id': old['id'], **service.vault.open(old['payload'])}
            ident = uuid.uuid4().hex
            conn.execute('INSERT INTO message_reply_drafts VALUES(?,?,?,?,?)',
                         (ident, account_id, sample_id, service.vault.seal(result), time.time()))
        return {'id': ident, **result}
