"""Installed explicitly by bridge before importing upstream command modules."""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from .browser_config import CDP_OPERATIONS, BrowserError, discover
from .cancellation import cancellation_scope
from .cdp import endpoint, guarded_websocket, task_page, websocket_url
from .security import strict_json


def playwright():
    from playwright.async_api import async_playwright
    return async_playwright()


def validate_operation(operation: str):
    address = os.environ.get('XY_BROWSER_CDP_ENDPOINT', '')
    if not address:
        return
    try:
        endpoint(address)
    except ValueError:
        raise BrowserError('cdp_config_invalid') from None
    send_allowed = operation == 'message.send' and os.environ.get('XY_MESSAGE_SEND_ENABLED') == 'true'
    if operation not in CDP_OPERATIONS and not send_allowed:
        raise BrowserError('cdp_search_only')
    if (not os.environ.get('XY_BROWSER_CDP_ACCOUNT_ID') or
            os.environ.get('XY_BROWSER_CDP_ACCOUNT_ID') != os.environ.get('XY_OPERATION_ACCOUNT_ID') or
            not os.environ.get('XY_BROWSER_CDP_UID') or
            os.environ.get('XY_BROWSER_CDP_UID') != os.environ.get('XY_OPERATION_UID')):
        raise BrowserError('cdp_binding_mismatch')


@asynccontextmanager
async def goofish_page(*, headless=None, viewport=(1440, 900), cookies=None, focus_emulation=False):
    address = os.environ.get('XY_BROWSER_CDP_ENDPOINT', '')
    if address:
        validate_operation('search')
        try:
            ws = websocket_url(address)
            async with cancellation_scope(), guarded_websocket(ws) as guarded, playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(guarded, timeout=10000, no_defaults=True)
                # Stopping Playwright disconnects its transport. Never Browser.close/context.close.
                async with task_page(browser, os.environ['XY_OPERATION_UID'], focus_emulation=focus_emulation) as page:
                    yield page
        except ValueError as exc:
            raise BrowserError(str(exc) if str(exc).startswith('cdp_') else 'cdp_unavailable') from None
        return
    if cookies is None:
        filename = os.environ.get('GOOFISH_COOKIES_PATH')
        if not filename:
            raise BrowserError('browser_cookies_missing')
        cookies = strict_json(Path(filename).read_text(encoding='utf-8'))
    if not os.environ.get('XY_OPERATION_UID') or cookies.get('unb') != os.environ['XY_OPERATION_UID']:
        raise BrowserError('account_mismatch')
    choice = discover(os.environ.get('XY_BROWSER', 'auto'), os.environ.get('XY_BROWSER_EXECUTABLE', ''))
    parent = Path.home() / '.goofish-cli' / 'profiles'
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    profile = tempfile.mkdtemp(prefix='browser-', dir=parent)
    try:
        async with playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=profile, executable_path=choice.executable,
                headless=os.environ.get('GOOFISH_HEADLESS') == '1' if headless is None else headless,
                viewport={'width': viewport[0], 'height': viewport[1]},
                locale='zh-CN', timezone_id='Asia/Shanghai',
                args=['--no-default-browser-check', '--no-first-run'])
            try:
                taobao = {'_m_h5_tk', '_m_h5_tk_enc', 'x5sec', 'sgcookie', 'cookie2', '_tb_token_'}
                await context.add_cookies([{'name': name, 'value': value, 'path': '/',
                    'domain': '.taobao.com' if name in taobao else '.goofish.com',
                    'secure': True, 'sameSite': 'None'} for name, value in cookies.items() if value])
                yield await context.new_page()
            finally:
                await context.close()
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def install(operation: str):
    validate_operation(operation)
    from goofish_cli.core import browser
    browser.goofish_page = goofish_page
    if os.environ.get('XY_BROWSER_CDP_ENDPOINT'):
        from goofish_cli.core.session import Session

        def forbidden_session(*args, **kwargs):
            raise BrowserError('cdp_session_forbidden')

        if operation == 'message.send':
            original_load = Session.load

            def bound_session(*args, **kwargs):
                session = original_load(*args, **kwargs)
                if session.unb != os.environ['XY_OPERATION_UID']:
                    raise BrowserError('account_mismatch')
                return session

            Session.load = bound_session
        else:
            Session.load = forbidden_session
