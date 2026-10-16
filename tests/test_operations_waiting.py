import asyncio

import pytest
from test_operation_pagination import ScrollingPage
from test_operations_browser import Page, event


@pytest.mark.parametrize('loading', [False, True, 'failed'])
def test_stalled_page_ticks_are_bounded_and_loading_suppresses_scroll(loading):
    from xianyu_workbench.operations_browser import capture

    class WaitingPage(ScrollingPage):
        def __init__(self):
            super().__init__([])
            self.moves = []

        async def evaluate(self, script):
            if script != 'document.body.scrollHeight':
                self.moves.append(asyncio.get_running_loop().time())
                if loading:
                    self.session.handlers['Network.requestWillBeSent']({'requestId': 'waiting', 'request': {
                        'url': 'https://h5api.m.goofish.com/h5/mtop.idle.web.trade.bought.list/1.0/'}})
                    if loading == 'failed':
                        self.session.handlers['Network.loadingFailed']({'requestId': 'waiting'})
            return await super().evaluate(script)

    page = WaitingPage()
    result = asyncio.run(capture(page, 'orders', timeout=4))
    assert result['pages_read'] == 1 and result['stop_reason'] == 'time_limit'
    assert result['partial'] and page.session.detached
    assert 1 <= len(page.moves) <= 4
    assert all(b - a >= .5 for a, b in zip(page.moves, page.moves[1:]))
    if loading is True:
        assert len(page.moves) == 1
    else:
        assert len(page.moves) >= 2


def test_no_self_never_scrolls_even_after_tick():
    from xianyu_workbench.operations_browser import capture
    page = Page([event('inventory')])  # No evaluate method: scrolling would fail the test.
    with pytest.raises(ValueError, match='response_timeout'):
        asyncio.run(capture(page, 'inventory', timeout=1))
    assert page.session.detached
