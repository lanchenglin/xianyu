"""Bridge-only bounded response observation on an owned task tab; no request replay."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from urllib.parse import urlsplit

from .browser_adapter import goofish_page, validate_operation
from .browser_config import BrowserError
from .operations import MAX_BODY, SOURCES, normalize, success_data

HEAD = 'mtop.idle.web.user.page.head'
PAGES = {'orders': 'https://www.goofish.com/bought', 'inventory': 'https://www.goofish.com/personal'}


async def capture(page, kind: str, *, timeout=25) -> dict:
    if kind not in PAGES:
        raise ValueError('operation_not_allowed')
    session = await page.context.new_cdp_session(page)
    pending, observed = {}, asyncio.Queue(maxsize=16)
    overflow = False

    def response(event):
        nonlocal overflow
        value = event.get('response', {})
        url = urlsplit(value.get('url', ''))
        allowed = {f'/h5/{SOURCES[kind]}/1.0/': kind}
        if kind == 'inventory':
            allowed[f'/h5/{HEAD}/1.0/'] = 'head'
        if (url.scheme != 'https' or url.hostname not in ('h5api.m.goofish.com', 'h5api.m.taobao.com')
                or url.port not in (None, 443) or url.username or url.password or url.path not in allowed):
            return
        if len(pending) >= 16:
            overflow = True
            return
        pending[event['requestId']] = (allowed[url.path], value.get('status'))

    def finished(event):
        nonlocal overflow
        key = event['requestId']
        if key not in pending:
            return
        target, status = pending.pop(key)
        try:
            observed.put_nowait((key, target, status, event.get('encodedDataLength', MAX_BODY + 1)))
        except asyncio.QueueFull:
            overflow = True

    session.on('Network.responseReceived', response)
    session.on('Network.loadingFinished', finished)
    try:
        async with asyncio.timeout(timeout):
            await session.send('Network.enable', {'maxTotalBufferSize': MAX_BODY * 2,
                                                  'maxResourceBufferSize': MAX_BODY})
            await page.goto(PAGES[kind], wait_until='domcontentloaded', timeout=int(timeout * 1000))
            result, own = None, kind == 'orders'
            while result is None or not own or not observed.empty():
                if overflow:
                    raise ValueError('response_limit')
                key, target, status, size = await observed.get()
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
                try:
                    value = json.loads(raw)
                    data = success_data(value)
                except (ValueError, TypeError):
                    continue
                if target == 'head':
                    if data.get('baseInfo', {}).get('self') is not True:
                        raise ValueError('cdp_identity_mismatch')
                    own = True
                elif result is None:
                    result = normalize(kind, value)
            if page.url.split('?', 1)[0].rstrip('/') != PAGES[kind]:
                raise ValueError('page_redirected')
            return result
    except TimeoutError:
        raise ValueError('response_timeout') from None
    finally:
        await session.detach()


def collect(kind: str) -> dict:
    if not os.environ.get('XY_BROWSER_CDP_ENDPOINT'):
        raise BrowserError('cdp_required')
    validate_operation(kind)

    async def run():
        async with goofish_page() as page:
            return await capture(page, kind)
    try:
        return asyncio.run(run())
    except ValueError as exc:
        raise BrowserError(str(exc)) from None
