"""Account-scoped private sample cache; missing rows never imply deletion."""
import hashlib
import hmac
import time

from .operations import MESSAGE_SOURCE, SOURCES
from .provider import Problem
from .security import canonical


class OperationsCache:
    def __init__(self, service):
        self.service = service
        self.db, self.vault = service.db, service.vault

    def read(self, account_id, kind):
        account = self.service.provider.account(account_id)
        rows = self.db.all('SELECT payload,source,fetched_at,record_key FROM operation_records '
                           'WHERE account_id=? AND kind=? ORDER BY fetched_at DESC LIMIT 500', (account_id, kind))
        return {'items': [{**self.vault.open(row['payload']), 'source': row['source'],
                           'fetched_at': row['fetched_at'],
                           **({'sample_id': row['record_key']} if kind == 'messages' else {})} for row in rows],
                'last_sync': self.db.one('SELECT * FROM operation_syncs WHERE account_id=? AND kind=? '
                                         'ORDER BY id DESC LIMIT 1', (account_id, kind)),
                'partial': True, 'completion': 'cached_samples', 'cache_limit': 500,
                'demo': account['mode'] == 'demo'}

    def sync(self, account_id, kind):
        if kind == 'messages':
            self.service.observation.guard(account_id)
        account = self.service.provider.account(account_id)
        source = 'demo' if account['mode'] == 'demo' else (MESSAGE_SOURCE if kind == 'messages' else SOURCES[kind])
        try:
            result = self.service.provider.call(account_id, kind, {})
        except Exception as exc:
            # Codes only, never remote messages or raw response bodies.
            safe = exc.code if isinstance(exc, Problem) and exc.code in {'response_timeout', 'response_invalid', 'field_invalid',
                'response_failed', 'response_too_large', 'items_invalid', 'duplicate_conflict',
                'response_limit', 'page_redirected', 'cid_mismatch',
                'cdp_identity_mismatch', 'cdp_binding_mismatch', 'cdp_context_ambiguous',
                'account_paused', 'rate_limited', 'busy', 'timeout', 'live_disabled', 'cdp_required'} else 'collection_failed'
            self.db.execute('INSERT INTO operation_syncs(account_id,kind,source,fetched_at,state,partial,'
                            'completion,error,item_count) VALUES(?,?,?,?,?,1,?,?,0)',
                            (account_id, kind, source, time.time(), 'failed', 'failed', safe))
            raise Problem(safe, '只读采集失败；旧缓存保留，不代表本次成功。请根据安全错误码检查。', exc.status if isinstance(exc, Problem) else 502) from None
        fetched = time.time()
        with self.db.connect() as conn:
            for item in result['items']:
                identity = ([item['cid'], item['message_id']] if kind == 'messages'
                            else item['order_id' if kind == 'orders' else 'item_id'])
                key = hmac.new(self.service.s.vault_key.encode(),
                               canonical([account_id, kind, identity]).encode(), hashlib.sha256).hexdigest()
                conn.execute('INSERT INTO operation_records(account_id,kind,record_key,payload,source,fetched_at) '
                             'VALUES(?,?,?,?,?,?) ON CONFLICT(account_id,kind,record_key) DO UPDATE SET '
                             'payload=excluded.payload,source=excluded.source,fetched_at=excluded.fetched_at',
                             (account_id, kind, key, self.vault.seal(item), source, fetched))
            conn.execute('INSERT INTO operation_syncs(account_id,kind,source,fetched_at,state,partial,'
                         'completion,cursor_error,item_count,has_more,reported_total,scope,pages_read,stop_reason) '
                         'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (account_id, kind, source, fetched, 'partial' if result['partial'] else 'complete',
                          int(result['partial']), result['completion'], result['cursor_error'], len(result['items']),
                          result['has_more'], result['reported_total'], result.get('scope', 'legacy_samples'),
                          result.get('pages_read', 1), result.get('stop_reason')))
        return {**result, 'source': source, 'fetched_at': fetched, 'demo': account['mode'] == 'demo'}
