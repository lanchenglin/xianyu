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
