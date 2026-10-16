import asyncio
import copy
import json

import pytest
from test_operations import inventory, orders
from test_operations_browser import Page, event

from xianyu_workbench.operations import normalize


def order_page(identity='9001', cursor='one'):
    value = orders()
    value['data'].update(nextPage='true', lastEndRow=cursor, totalCount='20')
    value['data']['items'][0]['commonData']['orderIdStr'] = identity
    return value


class ScrollingPage(Page):
    def __init__(self, following):
        super().__init__([event('orders', order_page())])
        self.following = iter(following)
        self.scrolls = 0

    async def evaluate(self, script):
        if script == 'document.scrollingElement.scrollHeight':
            return 4000
        assert 'window.scrollTo' in script
        self.scrolls += 1
        value = next(self.following, None)
        if value is not None:
            key = f'scroll-{self.scrolls}'
            self.session.bodies[key] = json.dumps(value)
            self.session.handlers['Network.responseReceived']({'requestId': key, 'response': {
                'url': 'https://h5api.m.goofish.com/h5/mtop.idle.web.trade.bought.list/1.0/', 'status': 200}})
            self.session.handlers['Network.loadingFinished']({'requestId': key, 'encodedDataLength': 500})


def test_capture_scrolls_and_preserves_partial_on_stall():
    from xianyu_workbench.operations_browser import capture
    page = ScrollingPage([order_page('9002', 'two')])
    result = asyncio.run(capture(page, 'orders', timeout=2))
    assert [item['order_id'] for item in result['items']] == ['9001', '9002']
    assert result['pages_read'] == 2 and result['partial']
    assert result['stop_reason'] == 'time_limit'
    assert page.session.detached


def test_capture_stops_repeated_response():
    from xianyu_workbench.operations_browser import capture
    page = ScrollingPage([order_page()])
    result = asyncio.run(capture(page, 'orders', timeout=2))
    assert result['stop_reason'] == 'repeated_cursor'
    assert page.scrolls == 1


def test_inventory_only_proven_end_completes_declared_scope():
    from xianyu_workbench.operation_pagination import Traversal
    state = Traversal('inventory')
    first = inventory()
    first['data']['nextPage'] = True
    assert state.add(first)
    last = inventory()
    last['data']['cardList'][0]['cardData']['id'] = '1002'
    assert not state.add(last)
    result = state.result()
    assert result['partial'] is False
    assert result['completion'] == 'complete' and result['stop_reason'] == 'end_reached'
    assert result['scope'] == 'self_published' and result['pages_read'] == 2
    assert len(result['items']) == 2


def test_inventory_empty_terminal_and_unknown_pagination():
    from xianyu_workbench.operation_pagination import Traversal
    for more, partial in [(False, False), (True, True), ('false', True)]:
        state = Traversal('inventory')
        value = inventory()
        value['data'].update(cardList=[], nextPage=more)
        assert not state.add(value)
        assert state.result()['partial'] is partial


def test_item_limit_and_overlapping_pages_are_bounded():
    from xianyu_workbench.operation_pagination import Traversal
    state = Traversal('inventory', max_items=2)
    first = inventory()
    first['data']['nextPage'] = True
    state.add(first)
    second = copy.deepcopy(first)
    extra = copy.deepcopy(second['data']['cardList'][0])
    extra['cardData']['id'] = '1002'
    second['data']['cardList'].append(extra)
    assert state.add(second)
    third = copy.deepcopy(first)
    third['data']['cardList'][0]['cardData']['id'] = '1003'
    assert not state.add(third)
    result = state.result()
    assert result['stop_reason'] == 'item_limit' and result['partial']
    assert len(result['items']) == 2 and result['pages_read'] == 2


def test_inventory_capture_completes_only_with_self():
    from xianyu_workbench.operations_browser import capture
    result = asyncio.run(capture(Page([event('inventory'), event('head')]), 'inventory', timeout=.1))
    assert result['partial'] is False and result['scope'] == 'self_published'
    with pytest.raises(ValueError, match='response_timeout'):
        asyncio.run(capture(Page([event('inventory')]), 'inventory', timeout=.01))


def test_only_observed_order_true_is_known():
    assert normalize('orders', order_page())['has_more'] is True
    for value in ('false', '', 'TRUE', False, True, 0):
        body = order_page()
        body['data']['nextPage'] = value
        assert normalize('orders', body)['has_more'] is None


def test_orders_merge_and_stop_on_repeated_cursor_without_leaking_it():
    from xianyu_workbench.operation_pagination import Traversal
    state = Traversal('orders')
    assert state.add(order_page())
    assert state.add(order_page('9002', 'two'))
    assert not state.add(order_page('9003', 'two'))
    result = state.result()
    assert result['partial'] and result['pages_read'] == 2
    assert result['stop_reason'] == 'repeated_cursor'
    assert [x['order_id'] for x in result['items']] == ['9001', '9002']
    assert result['scope'] == 'bought_orders'
    assert 'lastEndRow' not in str(result)


def test_repeated_page_and_unknown_end_never_complete():
    from xianyu_workbench.operation_pagination import Traversal
    state = Traversal('orders')
    state.add(order_page())
    assert not state.add(order_page(cursor='two'))
    assert state.result()['stop_reason'] == 'repeated_page'
    state = Traversal('orders')
    value = order_page()
    value['data']['nextPage'] = 'false'
    assert not state.add(value)
    assert state.result()['partial']
    assert state.result()['stop_reason'] == 'pagination_semantics_unknown'


def test_capture_total_response_budget():
    from xianyu_workbench.operations_browser import capture
    pages = [order_page(str(9002 + n), str(n + 2)) for n in range(20)]
    page = ScrollingPage(pages)
    result = asyncio.run(capture(page, 'orders', timeout=4, max_bytes=1000))
    assert result['stop_reason'] == 'byte_limit'
    assert result['pages_read'] == 2
    assert result['partial']


def test_budget_cannot_hide_later_ownership_response():
    from xianyu_workbench.operations_browser import capture
    events = [event('head'), event('inventory'),
              event('head', {'ret': ['SUCCESS::OK'], 'data': {'baseInfo': {'self': False}}})]
    with pytest.raises(ValueError):
        asyncio.run(capture(Page(events), 'inventory', timeout=.1, max_bytes=1000))


def test_later_oversized_response_retains_bounded_partial():
    from xianyu_workbench.operations_browser import capture
    page = Page([event('orders', order_page()), event('orders', order_page('9002', 'two'), size=1_000_001)])
    result = asyncio.run(capture(page, 'orders', timeout=.1))
    assert result['partial'] and result['stop_reason'] == 'response_too_large'
    assert len(result['items']) == 1


def test_page_bound_and_cross_page_conflict():
    from xianyu_workbench.operation_pagination import Traversal
    state = Traversal('orders', max_pages=2)
    state.add(order_page())
    assert not state.add(order_page('9002', 'two'))
    assert state.result()['stop_reason'] == 'page_limit'
    state = Traversal('orders')
    value = order_page()
    state.add(value)
    value = copy.deepcopy(value)
    value['data']['lastEndRow'] = 'two'
    value['data']['items'][0]['commonData']['itemId'] = '9999'
    with pytest.raises(ValueError, match='duplicate_conflict'):
        state.add(value)
