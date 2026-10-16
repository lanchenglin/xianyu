"""Bounded traversal of observed pages; cursors are never replayed or persisted."""
from .operations import normalize


class Traversal:
    def __init__(self, kind, *, max_pages=20, max_items=500):
        self.kind = kind
        self.max_pages, self.max_items = max_pages, max_items
        self.items, self.cursors, self.pages = {}, set(), set()
        self.latest = None
        self.pages_read = 0
        self.stop_reason = None

    def add(self, value):
        if self.stop_reason:
            return False
        page = normalize(self.kind, value)
        key = 'order_id' if self.kind == 'orders' else 'item_id'
        incoming = {item[key]: item for item in page['items']}
        for identity, item in incoming.items():
            if identity in self.items and self.items[identity] != item:
                raise ValueError('duplicate_conflict')
        fingerprint = frozenset(incoming)
        cursor = value['data'].get('lastEndRow') if self.kind == 'orders' else None
        if cursor and isinstance(cursor, str) and cursor in self.cursors:
            return self.stop('repeated_cursor')
        if fingerprint in self.pages:
            return self.stop('repeated_page')
        if len(self.items.keys() | incoming.keys()) > self.max_items:
            return self.stop('item_limit')
        self.items.update(incoming)
        self.pages.add(fingerprint)
        if isinstance(cursor, str) and cursor:
            self.cursors.add(cursor)
        self.pages_read += 1
        self.latest = page
        if page['cursor_error']:
            return self.stop(page['cursor_error'])
        if not incoming:
            return self.stop('empty_page_without_end')
        if self.pages_read >= self.max_pages:
            return self.stop('page_limit')
        return True

    def stop(self, reason):
        self.stop_reason = reason
        return False

    def result(self):
        if self.latest is None:
            raise ValueError('response_timeout')
        return {**self.latest, 'items': list(self.items.values()),
                'partial': True, 'completion': 'bounded_pages',
                'scope': 'bought_orders' if self.kind == 'orders' else 'self_published',
                'pages_read': self.pages_read, 'stop_reason': self.stop_reason,
                'page_limit': self.max_pages, 'item_limit': self.max_items}
