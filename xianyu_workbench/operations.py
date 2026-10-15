"""Pure, minimal projections of observed MTOP structures. No cursor guesses."""
from __future__ import annotations

SOURCES = {'orders': 'mtop.idle.web.trade.bought.list', 'inventory': 'mtop.idle.web.xyh.item.list'}
MAX_ITEMS = 100
MAX_BODY = 1_000_000


def success_data(value):
    if not isinstance(value, dict):
        raise ValueError('response_invalid')
    ret = value.get('ret')
    if (not isinstance(ret, list) or not ret or
            not all(isinstance(x, str) and x.startswith('SUCCESS::') for x in ret)):
        raise ValueError('response_failed')
    data = value.get('data')
    if not isinstance(data, dict):
        raise ValueError('response_invalid')
    return data


def text(value, *, maximum=200, identifier=False):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError('field_invalid')
    if identifier and (not value.isascii() or not value.isdecimal()):
        raise ValueError('field_invalid')
    return value


def normalize(kind: str, value: dict) -> dict:
    if kind not in SOURCES:
        raise ValueError('operation_not_allowed')
    data = success_data(value)
    rows = data.get('items' if kind == 'orders' else 'cardList')
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError('items_invalid')
    items = {}
    try:
        for row in rows:
            if kind == 'orders':
                common, head = row['commonData'], row['head']['data']
                item = {'order_id': text(common['orderIdStr'], maximum=64, identifier=True),
                        'item_id': text(common['itemId'], maximum=64, identifier=True),
                        'status': text(common['tradeStatusEnum']),
                        'created_at': text(head['createTime']), 'status_text': text(head['statusViewMsg'])}
                key = item['order_id']
            else:
                card = row['cardData']
                if type(card['itemStatus']) is not int:
                    raise ValueError('field_invalid')
                item = {'item_id': text(card['id'], maximum=64, identifier=True),
                        'status': card['itemStatus'], 'price': text(card['priceInfo']['price'], maximum=100),
                        'title': text(card['title'], maximum=500)}
                key = item['item_id']
            if key in items and items[key] != item:
                raise ValueError('duplicate_conflict')
            items[key] = item
    except (KeyError, TypeError):
        raise ValueError('field_invalid') from None
    more = data.get('nextPage')
    if kind == 'orders':
        error = 'pagination_semantics_unknown' if isinstance(more, str) else 'pagination_type_invalid'
        more = None
    else:
        error = None if type(more) is bool else 'pagination_type_invalid'
        more = more if type(more) is bool else None
    total = data.get('totalCount')
    if kind == 'orders':
        total = int(total) if isinstance(total, str) and total.isascii() and total.isdecimal() and len(total) <= 10 else None
    elif type(total) is not int or total < 0:
        total = None
    if total is None or (kind == 'orders' and (not isinstance(data.get('lastEndRow'), str)
                                              or len(data['lastEndRow']) > 1000)):
        error = 'pagination_type_invalid'
    return {'items': list(items.values()), 'source': SOURCES[kind], 'partial': True,
            'completion': 'single_page', 'has_more': more, 'cursor_error': error, 'reported_total': total}
