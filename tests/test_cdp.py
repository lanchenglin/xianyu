import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


@pytest.mark.parametrize('url', ['http://localhost:9000', 'http://127.1:9000', 'http://192.168.0.1:9000',
    'http://127.0.0.1:9000?x=y', 'http://127.0.0.1:9000#x', 'http://u:p@127.0.0.1:9000',
    'http://127.0.0.1:9000/other', 'https://127.0.0.1:9000', 'http://[::ffff:127.0.0.1]:9000'])
def test_endpoint_rejected(url):
    from xianyu_workbench.cdp import endpoint
    with pytest.raises(ValueError):
        endpoint(url)


@pytest.mark.parametrize('url', ['http://127.0.0.1:9000', 'http://[::1]:9000/'])
def test_loopback_endpoint(url):
    from xianyu_workbench.cdp import endpoint
    assert endpoint(url) == url.rstrip('/')


@pytest.mark.parametrize('status,ws', [(302, ''), (200, 'ws://evil.example:9000/devtools/browser/test'),
    (200, 'ws://127.0.0.1:9001/devtools/browser/test'), (200, 'ws://127.0.0.1:9000/devtools/browser/test?secret=x')])
def test_discovery_response_rejected(status, ws):
    from xianyu_workbench.cdp import websocket_url
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={'webSocketDebuggerUrl': ws},
                                                                 headers={'Location': 'http://evil.example'}))
    with pytest.raises(ValueError):
        websocket_url('http://127.0.0.1:9000', transport=transport)


def test_websocket_redirect_not_forwarded():
    from xianyu_workbench.cdp import guarded_websocket
    async def run():
        async def upstream(reader, writer):
            await reader.readuntil(b'\r\n\r\n')
            writer.write(b'HTTP/1.1 302 Found\r\nLocation: ws://evil.example/\r\n\r\n')
            await writer.drain()
            writer.close()
        server = await asyncio.start_server(upstream, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with guarded_websocket(f'ws://127.0.0.1:{port}/devtools/browser/test') as address:
                from urllib.parse import urlsplit
                target = urlsplit(address)
                reader, writer = await asyncio.open_connection(target.hostname, target.port)
                writer.write(b'GET /devtools/browser/test HTTP/1.1\r\nHost: localhost\r\n\r\n')
                await writer.drain()
                assert await reader.read() == b''
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()
    asyncio.run(run())


def test_websocket_discovery():
    from xianyu_workbench.cdp import websocket_url
    ws = 'ws://127.0.0.1:9000/devtools/browser/test'
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'webSocketDebuggerUrl': ws}))
    assert websocket_url('http://127.0.0.1:9000', transport=transport) == ws


def fake_browser(cookies, count=1):
    context = MagicMock()
    context.cookies = AsyncMock(return_value=cookies)
    context.new_page = AsyncMock(return_value=MagicMock(close=AsyncMock()))
    context.add_cookies = AsyncMock()
    context.close = AsyncMock()
    browser = MagicMock(contexts=[context] * count, close=AsyncMock())
    return browser, context


def cookie(uid='12345', domain='.goofish.com'):
    return {'name': 'unb', 'value': uid, 'domain': domain, 'path': '/'}


@pytest.mark.parametrize('cookies,count', [([], 1), ([cookie('999')], 1), ([cookie(domain='.evil.com')], 1),
    ([cookie(), cookie('999')], 1), ([cookie()], 2)])
def test_cdp_identity_fails_before_new_page(cookies, count):
    from xianyu_workbench.cdp import task_page
    browser, context = fake_browser(cookies, count)
    async def run():
        with pytest.raises(ValueError):
            async with task_page(browser, '12345'):
                pytest.fail('must not yield')
    asyncio.run(run())
    context.new_page.assert_not_called()
    context.add_cookies.assert_not_called()
    context.close.assert_not_called()
    browser.close.assert_not_called()


@pytest.mark.parametrize('failure', ['none', 'attach', 'send', 'cancel_send', 'body', 'cancel_body', 'identity', 'detach'])
def test_task_focus_target_and_cleanup(failure):
    from xianyu_workbench.cdp import task_page
    browser, context = fake_browser([cookie()])
    original = MagicMock(close=AsyncMock())
    context.pages = [original]
    page = context.new_page.return_value
    session = MagicMock(send=AsyncMock(), detach=AsyncMock())
    context.new_cdp_session = AsyncMock(return_value=session)
    if failure == 'attach':
        context.new_cdp_session.side_effect = RuntimeError('attach')
    if failure in ('send', 'cancel_send'):
        session.send.side_effect = asyncio.CancelledError() if failure == 'cancel_send' else RuntimeError('send')
    if failure == 'detach':
        session.detach.side_effect = RuntimeError('detach')
    if failure == 'identity':
        context.cookies.side_effect = [[cookie()], [cookie('999')]]

    async def run():
        async with task_page(browser, '12345', focus_emulation=True) as owned:
            assert owned is page
            session.send.assert_awaited_once_with('Emulation.setFocusEmulationEnabled', {'enabled': True})
            if failure == 'body':
                raise RuntimeError('body')
            if failure == 'cancel_body':
                raise asyncio.CancelledError()

    error = (asyncio.CancelledError if failure.startswith('cancel') else
             ValueError if failure == 'identity' else RuntimeError)
    if failure in ('none', 'detach'):
        asyncio.run(run())
    else:
        with pytest.raises(error):
            asyncio.run(run())
    context.new_cdp_session.assert_awaited_once_with(page)
    if failure != 'attach':
        session.detach.assert_awaited_once()
    page.close.assert_awaited_once()
    original.close.assert_not_called()
    browser.new_browser_cdp_session.assert_not_called()
    browser.close.assert_not_called()
    context.close.assert_not_called()
    context.add_cookies.assert_not_called()
    if failure == 'none':
        assert context.cookies.await_count == 2


def test_task_focus_default_off():
    from xianyu_workbench.cdp import task_page
    browser, context = fake_browser([cookie()])
    async def run():
        async with task_page(browser, '12345'):
            pass
    asyncio.run(run())
    context.new_cdp_session.assert_not_called()


def test_only_own_page_closed_on_failure():
    from xianyu_workbench.cdp import task_page
    browser, context = fake_browser([cookie()])
    async def run():
        with pytest.raises(RuntimeError):
            async with task_page(browser, '12345') as page:
                raise RuntimeError('disconnect or site failure')
        page.close.assert_awaited_once()
    asyncio.run(run())
    context.new_page.assert_awaited_once()
    context.add_cookies.assert_not_called()
    context.close.assert_not_called()
    browser.close.assert_not_called()
