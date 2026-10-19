"""Bridge-only bounded response observation on an owned task tab; no request replay."""
from __future__ import annotations

import asyncio
import base64
import os
from urllib.parse import urlsplit

from .browser_adapter import goofish_page, validate_operation
from .browser_config import BrowserError
from .operation_pagination import Traversal
from .operations import MAX_BODY, SOURCES, success_data
from .security import strict_json

HEAD = 'mtop.idle.web.user.page.head'
PAGES = {'orders': 'https://www.goofish.com/bought', 'inventory': 'https://www.goofish.com/personal'}


async def capture(page, kind: str, *, timeout=25, max_bytes=5_000_000) -> dict:
    if kind not in PAGES:
        raise ValueError('operation_not_allowed')
    session = await page.context.new_cdp_session(page)
    pending, observed = {}, asyncio.Queue(maxsize=16)
    overflow = False
    loading = set()

    def target_for(value):
        url = urlsplit(value.get('url', ''))
        allowed = {f'/h5/{SOURCES[kind]}/1.0/': kind}
        if kind == 'inventory':
            allowed[f'/h5/{HEAD}/1.0/'] = 'head'
        if (url.scheme != 'https' or url.hostname not in ('h5api.m.goofish.com', 'h5api.m.taobao.com')
                or url.port not in (None, 443) or url.username or url.password or url.path not in allowed):
            return None
        return allowed[url.path]

    def requested(event):
        nonlocal overflow
        if target_for(event.get('request', {})):
            if len(loading) >= 16:
                overflow = True
            else:
                loading.add(event['requestId'])

    def response(event):
        nonlocal overflow
        value = event.get('response', {})
        target = target_for(value)
        if target is None:
            return
        if len(pending) >= 16:
            overflow = True
            return
        pending[event['requestId']] = (target, value.get('status'))

    def failed(event):
        key = event['requestId']
        loading.discard(key)
        pending.pop(key, None)

    def finished(event):
        nonlocal overflow
        key = event['requestId']
        loading.discard(key)
        if key not in pending:
            return
        target, status = pending.pop(key)
        try:
            observed.put_nowait((key, target, status, event.get('encodedDataLength', MAX_BODY + 1)))
        except asyncio.QueueFull:
            overflow = True

    session.on('Network.requestWillBeSent', requested)
    session.on('Network.responseReceived', response)
    session.on('Network.loadingFinished', finished)
    session.on('Network.loadingFailed', failed)
    traversal = Traversal(kind)
    result, own = None, kind == 'orders'
    total_bytes = 0
    loop = asyncio.get_running_loop()
    tick = .75
    next_tick = loop.time() + tick
    height = None
    try:
        async with asyncio.timeout(timeout):
            await session.send('Network.enable', {'maxTotalBufferSize': MAX_BODY * 2,
                                                  'maxResourceBufferSize': MAX_BODY})
            await page.goto(PAGES[kind], wait_until='domcontentloaded', timeout=int(timeout * 1000))
            while True:
                if page.url.split('?', 1)[0].rstrip('/') != PAGES[kind]:
                    raise ValueError('page_redirected')
                if overflow:
                    raise ValueError('response_limit')
                if result is not None and own and observed.empty() and traversal.stop_reason:
                    break
                if observed.empty() and loop.time() >= next_tick:
                    if result is not None and own and not loading and not pending:
                        current_height = await page.evaluate('document.scrollingElement.scrollHeight')
                        if current_height == height:
                            # Re-arm a bottom scroll missed before the page installed its hook.
                            # One movement per tick; no synthetic events, clicks or requests.
                            await page.evaluate('''() => {
                                const root = document.scrollingElement;
                                const bottom = Math.max(0, root.scrollHeight - root.clientHeight);
                                window.scrollTo(0, root.scrollTop >= bottom - 2 ? Math.max(0, bottom - 64) : bottom);
                            }''')
                        height = current_height
                    else:
                        height = None
                    next_tick = loop.time() + tick
                try:
                    key, target, status, size = await asyncio.wait_for(
                        observed.get(), max(.001, next_tick - loop.time()))
                except TimeoutError:
                    continue
                if status != 200:
                    continue
                if not isinstance(size, (int, float)) or size > MAX_BODY or size < 0:
                    raise ValueError('response_too_large')
                body = await session.send('Network.getResponseBody', {'requestId': key})
                raw = body.get('body', '')
                if not isinstance(raw, str) or len(raw) > MAX_BODY * 2:
                    raise ValueError('response_too_large')
                raw = base64.b64decode(raw, validate=True) if body.get('base64Encoded') else raw.encode('utf-8')
                if len(raw) > MAX_BODY:
                    raise ValueError('response_too_large')
                total_bytes += max(len(raw), size)
                if total_bytes > max_bytes:
                    if result is not None and own and target == kind:
                        traversal.stop('byte_limit')
                        result = traversal.result()
                        break
                    raise ValueError('response_limit')
                try:
                    value = strict_json(raw)
                    data = success_data(value)
                except (ValueError, TypeError):
                    continue
                if target == 'head':
                    if data.get('baseInfo', {}).get('self') is not True:
                        raise ValueError('cdp_identity_mismatch')
                    own = True
                else:
                    traversal.add(value)
                    result = traversal.result()
                    height = None
            if page.url.split('?', 1)[0].rstrip('/') != PAGES[kind]:
                raise ValueError('page_redirected')
            return result
    except ValueError as exc:
        if (str(exc) == 'response_too_large' and result is not None and own and target == kind
                and not overflow and page.url.split('?', 1)[0].rstrip('/') == PAGES[kind]):
            traversal.stop('response_too_large')
            return traversal.result()
        raise
    except TimeoutError:
        if page.url.split('?', 1)[0].rstrip('/') != PAGES[kind]:
            raise ValueError('page_redirected') from None
        if result is not None and own and not overflow:
            traversal.stop('time_limit')
            return traversal.result()
        raise ValueError('response_timeout') from None
    finally:
        await session.detach()


async def capture_messages(page, uid: str, *, timeout=8) -> dict:
    """Observe server frames for a bounded window; never issue an IM protocol command."""
    from .operations import normalize_messages

    session = await page.context.new_cdp_session(page)
    sockets, frames = set(), asyncio.Queue(maxsize=64)
    overflow = False

    def created(event):
        if event.get('url') in ('wss://wss-goofish.dingtalk.com/', 'wss://wss-goofish.dingtalk.com:443/'):
            if len(sockets) < 8:
                sockets.add(event.get('requestId'))

    def received(event):
        nonlocal overflow
        if event.get('requestId') not in sockets:
            return
        response = event.get('response', {})
        if response.get('opcode') != 1:
            return
        raw = response.get('payloadData')
        if not isinstance(raw, str) or len(raw) > MAX_BODY:
            overflow = True
            return
        try:
            frames.put_nowait(raw)
        except asyncio.QueueFull:
            overflow = True

    session.on('Network.webSocketCreated', created)
    session.on('Network.webSocketFrameReceived', received)
    result, items = None, {}
    try:
        await session.send('Network.enable', {'maxTotalBufferSize': MAX_BODY * 2,
                                              'maxResourceBufferSize': MAX_BODY})
        await page.goto('https://www.goofish.com/im', wait_until='domcontentloaded', timeout=25000)
        deadline = asyncio.get_running_loop().time() + timeout
        count = 0
        while True:
            if overflow or count > 256:
                raise ValueError('response_limit')
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(frames.get(), remaining)
            except TimeoutError:
                break
            count += 1
            try:
                value = strict_json(raw)
                stack, nodes = [(value, 0)], 0
                while stack:
                    node, depth = stack.pop()
                    nodes += 1
                    if depth > 20 or nodes > 20000:
                        raise ValueError('response_invalid')
                    if isinstance(node, dict):
                        stack.extend((child, depth + 1) for child in node.values())
                    elif isinstance(node, list):
                        stack.extend((child, depth + 1) for child in node)
            except (ValueError, RecursionError):
                raise ValueError('response_invalid') from None
            if not isinstance(value, dict) or not isinstance(value.get('body'), dict):
                continue
            if 'userConvs' not in value['body']:
                continue
            result = normalize_messages(value, uid)
            for item in result['items']:
                key = (item['cid'], item['message_id'])
                if key in items and items[key] != item:
                    raise ValueError('duplicate_conflict')
                items[key] = item
                if len(items) > 100:
                    raise ValueError('response_limit')
        if overflow:
            raise ValueError('response_limit')
        if result is None:
            raise ValueError('response_timeout')
        if page.url != 'https://www.goofish.com/im':
            raise ValueError('page_redirected')
        return {**result, 'items': list(items.values())}
    finally:
        await session.detach()


def collect(kind: str) -> dict:
    if not os.environ.get('XY_BROWSER_CDP_ENDPOINT'):
        raise BrowserError('cdp_required')
    validate_operation(kind)

    async def run():
        async with goofish_page(focus_emulation=kind in ('orders', 'inventory')) as page:
            try:
                if kind == 'messages':
                    return await capture_messages(page, os.environ['XY_OPERATION_UID'])
                return await capture(page, kind)
            except ValueError as exc:
                # Preserve collector codes before the browser boundary maps transport errors.
                raise BrowserError(str(exc)) from None
    try:
        return asyncio.run(run())
    except ValueError as exc:
        raise BrowserError(str(exc)) from None
