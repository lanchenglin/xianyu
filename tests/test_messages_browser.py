import asyncio
import json

import pytest
from test_messages import frame
from test_operations_browser import Session

from xianyu_workbench import operations_browser


class Page:
    def __init__(self, frames, url='wss://wss-goofish.dingtalk.com/'):
        self.frames, self.socket_url = frames, url
        self.session = Session([])
        self.context = self
        self.url = 'about:blank'

    async def new_cdp_session(self, page):
        return self.session

    async def goto(self, url, **kwargs):
        assert url == 'https://www.goofish.com/im'
        self.url = url
        self.session.handlers['Network.webSocketCreated']({'requestId': '1', 'url': self.socket_url})
        for value in self.frames:
            self.session.handlers['Network.webSocketFrameReceived']({'requestId': '1',
                'response': {'opcode': 1, 'payloadData': json.dumps(value)}})


def test_owned_im_observation_collects_later_last_messages_without_sends():
    empty = {'code': 200, 'body': {'userConvs': []}}
    page = Page([empty, frame(), frame()])
    result = asyncio.run(operations_browser.capture_messages(page, '11', timeout=.02))
    assert len(result['items']) == 1
    assert result['completion'] == 'last_message_samples'
    assert page.session.detached


@pytest.mark.parametrize('url', ['wss://evil.invalid/', 'ws://wss-goofish.dingtalk.com/',
    'wss://wss-goofish.dingtalk.com/evil', 'wss://wss-goofish.dingtalk.com:444/'])
def test_socket_allowlist_timeout_and_cleanup(url):
    page = Page([frame()], url)
    with pytest.raises(ValueError, match='response_timeout'):
        asyncio.run(operations_browser.capture_messages(page, '11', timeout=.01))
    assert page.session.detached


def test_collection_preserves_safe_failure_code(monkeypatch):
    from contextlib import asynccontextmanager

    from xianyu_workbench.browser_config import BrowserError
    @asynccontextmanager
    async def boundary(*, focus_emulation=False):
        assert focus_emulation is False
        try:
            yield Page([])
        except ValueError:
            raise BrowserError('cdp_unavailable') from None
    async def fail(*args, **kwargs):
        raise ValueError('response_timeout')
    monkeypatch.setenv('XY_BROWSER_CDP_ENDPOINT', 'http://127.0.0.1:9998')
    monkeypatch.setenv('XY_OPERATION_UID', '11')
    monkeypatch.setattr(operations_browser, 'validate_operation', lambda kind: None)
    monkeypatch.setattr(operations_browser, 'goofish_page', boundary)
    monkeypatch.setattr(operations_browser, 'capture_messages', fail)
    with pytest.raises(BrowserError, match='response_timeout'):
        operations_browser.collect('messages')


def test_excessive_nested_frame_rejected_before_projection():
    data = frame()
    nested = {}
    data['unused'] = nested
    for _ in range(40):
        nested['next'] = {}
        nested = nested['next']
    page = Page([data])
    with pytest.raises(ValueError, match='response_invalid'):
        asyncio.run(operations_browser.capture_messages(page, '11', timeout=.01))
    assert page.session.detached


def test_malformed_observed_message_does_not_become_empty_success():
    data = frame()
    del data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']['messageId']
    page = Page([data])
    with pytest.raises(ValueError, match='field_invalid'):
        asyncio.run(operations_browser.capture_messages(page, '11', timeout=.01))
    assert page.session.detached
