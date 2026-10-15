import asyncio
import json

import pytest
from test_operations import inventory, orders


class Session:
    def __init__(self, events):
        self.events, self.handlers, self.bodies = events, {}, {}
        self.detached = False

    def on(self, name, handler):
        self.handlers[name] = handler

    async def send(self, method, params=None):
        if method == 'Network.getResponseBody':
            return {'body': self.bodies[params['requestId']], 'base64Encoded': False}
        assert method == 'Network.enable'
        assert params['maxResourceBufferSize'] <= 1_000_000
        return {}

    async def detach(self):
        self.detached = True


class Page:
    def __init__(self, events):
        self.session = Session(events)
        self.context = self
        self.url = 'about:blank'

    async def new_cdp_session(self, page):
        assert page is self
        return self.session

    async def goto(self, url, **kwargs):
        assert url in ('https://www.goofish.com/bought', 'https://www.goofish.com/personal')
        self.url = url
        for i, (api, body, status, size) in enumerate(self.session.events):
            key = str(i)
            self.session.bodies[key] = json.dumps(body)
            self.session.handlers['Network.responseReceived']({'requestId': key, 'response': {
                'url': f'https://h5api.m.goofish.com/h5/{api}/1.0/', 'status': status}})
            self.session.handlers['Network.loadingFinished']({'requestId': key, 'encodedDataLength': size})


def event(kind, body=None, status=200, size=500):
    api = {'orders': 'mtop.idle.web.trade.bought.list', 'inventory': 'mtop.idle.web.xyh.item.list',
           'head': 'mtop.idle.web.user.page.head'}[kind]
    if body is None:
        body = {'orders': orders, 'inventory': inventory,
                'head': lambda: {'ret': ['SUCCESS::OK'], 'data': {'baseInfo': {'self': True}}}}[kind]()
    return api, body, status, size


def test_listener_skips_failed_response_but_accepts_later_valid_page():
    from xianyu_workbench.operations_browser import capture
    page = Page([event('orders', {'ret': ['FAIL::private'], 'data': {}}), event('orders')])
    result = asyncio.run(capture(page, 'orders', timeout=.1))
    assert result['items'][0]['order_id'] == '9001'
    assert page.session.detached


@pytest.mark.parametrize('events', [[event('orders', {'ret': ['FAIL::bad'], 'data': {}})],
    [event('orders', status=403)], [event('orders', size=1_000_001)], []])
def test_listener_failure_never_success(events):
    from xianyu_workbench.operations_browser import capture
    page = Page(events)
    with pytest.raises(ValueError):
        asyncio.run(capture(page, 'orders', timeout=.02))
    assert page.session.detached


def test_inventory_requires_head_self():
    from xianyu_workbench.operations_browser import capture
    page = Page([event('inventory'), event('head')])
    result = asyncio.run(capture(page, 'inventory', timeout=.1))
    assert result['items'][0]['item_id'] == '1001'
    bad = event('head', {'ret': ['SUCCESS::OK'], 'data': {'baseInfo': {'self': False}}})
    page = Page([event('inventory'), bad, event('head')])
    with pytest.raises(ValueError, match='identity'):
        asyncio.run(capture(page, 'inventory', timeout=.1))
    assert page.session.detached


def test_inventory_without_head_times_out():
    from xianyu_workbench.operations_browser import capture
    with pytest.raises(ValueError):
        asyncio.run(capture(Page([event('inventory')]), 'inventory', timeout=.02))


def test_bridge_read_operation_uses_no_upstream(monkeypatch):
    from xianyu_workbench import bridge, operations_browser
    monkeypatch.setattr(operations_browser, 'collect', lambda kind: {'kind': kind})
    assert bridge.dispatch('orders', {}) == {'kind': 'orders'}
    with pytest.raises(ValueError):
        bridge.dispatch('orders', {'url': 'https://evil.invalid'})
