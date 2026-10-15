"""Narrow loopback CDP validation and ownership; never closes a borrowed browser."""
from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

import httpx


def endpoint(value: str) -> str:
    if not re.fullmatch(r'http://(?:127\.0\.0\.1|\[::1\]):[0-9]+/?', value):
        raise ValueError('cdp_endpoint_invalid')
    try:
        if not 1 <= urlsplit(value).port <= 65535:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('cdp_endpoint_invalid') from None
    return value.rstrip('/')


def websocket_url(value: str, *, transport=None) -> str:
    base = endpoint(value)
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=5, transport=transport) as client:
        with client.stream('GET', base + '/json/version') as response:
            if response.status_code != 200:
                raise ValueError('cdp_discovery_failed')
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 65536:
                    raise ValueError('cdp_discovery_failed')
    import json
    ws = json.loads(content).get('webSocketDebuggerUrl', '')
    prefix = base.replace('http://', 'ws://', 1) + '/devtools/browser/'
    if not isinstance(ws, str) or not ws.startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_-]+', ws[len(prefix):]):
        raise ValueError('cdp_websocket_invalid')
    return ws


@asynccontextmanager
async def guarded_websocket(ws: str):
    """Pin TCP destination and suppress HTTP redirects in Playwright's WS handshake."""
    target = urlsplit(ws)
    base = endpoint('http://' + target.netloc)
    if not ws.startswith(base.replace('http:', 'ws:') + '/devtools/browser/'):
        raise ValueError('cdp_websocket_invalid')
    tasks = set()

    async def relay(reader, writer):
        while chunk := await reader.read(65536):
            writer.write(chunk)
            await writer.drain()

    async def accept(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        remote = None
        try:
            request = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
            if request.split(b'\r\n', 1)[0] != f'GET {target.path} HTTP/1.1'.encode():
                return
            incoming, remote = await asyncio.wait_for(asyncio.open_connection(target.hostname, target.port), 5)
            lines = request.split(b'\r\n')
            lines = [line for line in lines if not line.lower().startswith(b'host:')]
            lines.insert(1, ('Host: ' + target.netloc).encode())
            remote.write(b'\r\n'.join(lines))
            await remote.drain()
            response = await asyncio.wait_for(incoming.readuntil(b'\r\n\r\n'), 5)
            if response.split(b'\r\n', 1)[0].split(b' ')[1:2] != [b'101']:
                return
            writer.write(response)
            await writer.drain()
            pumps = [asyncio.create_task(relay(reader, remote)), asyncio.create_task(relay(incoming, writer))]
            try:
                await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for pump in pumps:
                    pump.cancel()
                await asyncio.gather(*pumps, return_exceptions=True)
        except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        finally:
            for stream in (remote, writer):
                if stream:
                    stream.close()
                    with suppress(Exception):
                        await stream.wait_closed()
            tasks.discard(task)

    server = await asyncio.start_server(accept, '127.0.0.1', 0, limit=16384)
    try:
        yield f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}{target.path}'
    finally:
        server.close()
        await server.wait_closed()
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def check_identity(browser, uid: str):
    if len(browser.contexts) != 1:
        raise ValueError('cdp_context_ambiguous')
    context = browser.contexts[0]
    cookies = await context.cookies(['https://www.goofish.com/'])
    identities = [c.get('value') for c in cookies if c.get('name') == 'unb'
                  and c.get('domain') in ('.goofish.com', 'goofish.com', 'www.goofish.com', '.www.goofish.com')]
    if not uid or not identities or any(value != uid for value in identities):
        raise ValueError('cdp_identity_mismatch')
    return context


@asynccontextmanager
async def task_page(browser, uid: str):
    context = await check_identity(browser, uid)
    page = await context.new_page()
    try:
        yield page
        await check_identity(browser, uid)
    finally:
        with suppress(Exception):
            await page.close()
