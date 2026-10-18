"""Bounded observations of search samples, never platform price mutations."""
from __future__ import annotations

import math
import re
import time
from decimal import Decimal, InvalidOperation

from .provider import Problem
from .security import canonical


def price_value(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value)
    if not re.fullmatch(r'\d{1,7}(?:\.\d{1,2})?', text):
        return None
    try:
        price = Decimal(text)
        return format(price, '.2f') if 0 < price <= 1000000 else None
    except InvalidOperation:
        return None


def observe(service, monitor, result, *, now=None):
    now = time.time() if now is None else now
    fetched = result.get('fetched_at')
    if type(fetched) not in (int, float) or not math.isfinite(fetched) or not 0 <= now - fetched <= 300:
        return
    samples = {}
    for item in result.get('items', [])[:50]:
        item_id = str(item.get('item_id', ''))
        if re.fullmatch(r'\d{1,30}', item_id):
            value = price_value(item.get('price'))
            samples[item_id] = value if item_id not in samples else None
    with service.db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        latest = c.execute('SELECT MAX(observed) FROM price_samples WHERE monitor_id=?', (monitor['id'],)).fetchone()[0]
        if latest is not None and fetched <= latest:
            return
        previous = {row['item_id']: row for row in c.execute(
            'SELECT * FROM price_samples WHERE monitor_id=? AND observed=?', (monitor['id'], latest))}
        # Missing samples explicitly break comparison continuity.
        for item_id in previous.keys() - samples.keys():
            samples[item_id] = None
        for item_id, price in samples.items():
            old = previous.get(item_id)
            c.execute('INSERT INTO price_samples(account_id,monitor_id,item_id,price,observed,mode) VALUES(?,?,?,?,?,?)',
                      (monitor['account_id'], monitor['id'], item_id, price, fetched, result['mode']))
            if (old and old['price'] is not None and price is not None and old['mode'] == result['mode']
                    and 0 < fetched - old['observed'] <= min(86400, monitor['interval_s'] * 2)
                    and Decimal(price) < Decimal(old['price'])):
                c.execute('INSERT INTO notifications(monitor_id,content,created) VALUES(?,?,?)',
                          (monitor['id'], canonical({'kind': 'price_drop', 'item_id': item_id,
                           'previous_price': old['price'], 'price': price, 'mode': result['mode'],
                           'notice': '仅搜索样本价格变化，非库存/成交保证，不执行业务操作'}), now))
        c.execute('DELETE FROM price_samples WHERE monitor_id=? AND id NOT IN '
                  '(SELECT id FROM price_samples WHERE monitor_id=? ORDER BY observed DESC,id DESC LIMIT 1000)',
                  (monitor['id'], monitor['id']))


def history(service, account_id, monitor_id):
    monitor = service.db.one('SELECT * FROM monitors WHERE id=? AND account_id=?', (monitor_id, account_id))
    if not monitor:
        raise Problem('monitor_conflict', '监控不存在或账号不符', 409)
    return {'items': service.db.all('SELECT item_id,price,observed,mode FROM price_samples WHERE account_id=? AND monitor_id=? ORDER BY observed DESC,id DESC LIMIT 200',
                                  (account_id, monitor_id)),
            'notice': '最多200条搜索样本；缺失价格不代表免费、售罄或降价；不是全平台价格历史'}
