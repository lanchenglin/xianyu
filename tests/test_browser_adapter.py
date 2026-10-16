import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def runtime(tmp_path, monkeypatch):
    from xianyu_workbench import browser_adapter as a
    cookie_file = tmp_path / 'cookies.json'
    cookie_file.write_text(json.dumps({'unb': '12345'}))
    monkeypatch.setenv('GOOFISH_COOKIES_PATH', str(cookie_file))
    monkeypatch.setenv('XY_OPERATION_UID', '12345')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    context = MagicMock(add_cookies=AsyncMock(), close=AsyncMock(), new_page=AsyncMock(return_value=object()))
    chromium = MagicMock(launch_persistent_context=AsyncMock(return_value=context))
    @asynccontextmanager
    async def playwright():
        yield SimpleNamespace(chromium=chromium)
    monkeypatch.setattr(a, 'playwright', playwright)
    monkeypatch.setattr(a, 'discover', lambda *args: SimpleNamespace(executable='/fake/chromium'))
    return a, chromium, context


@pytest.mark.parametrize('home_source', ['HOME', 'USERPROFILE'])
def test_launch_parameters_and_cleanup(tmp_path, monkeypatch, home_source):
    import os
    from pathlib import Path

    # Model Windows home selection without touching the host's actual profile.
    monkeypatch.setenv('USERPROFILE', str(tmp_path / 'unisolated-home'))
    if home_source == 'USERPROFILE':
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: cls(os.environ['USERPROFILE'])))
    a, chromium, context = runtime(tmp_path, monkeypatch)
    async def run():
        async with a.goofish_page(headless=True, viewport=(800, 600)):
            pass
    asyncio.run(run())
    kw = chromium.launch_persistent_context.call_args.kwargs
    assert kw['executable_path'] == '/fake/chromium'
    assert 'channel' not in kw
    assert kw['headless'] is True
    assert kw['viewport'] == {'width': 800, 'height': 600}
    assert Path(kw['user_data_dir']).parent == tmp_path / '.goofish-cli' / 'profiles'
    assert not Path(kw['user_data_dir']).exists()
    context.add_cookies.assert_awaited_once()
    context.close.assert_awaited_once()


def test_launch_failure_never_retries(tmp_path, monkeypatch):
    a, chromium, context = runtime(tmp_path, monkeypatch)
    chromium.launch_persistent_context.side_effect = RuntimeError('launch failed')
    async def run():
        with pytest.raises(Exception):
            async with a.goofish_page():
                pytest.fail('no page')
    asyncio.run(run())
    chromium.launch_persistent_context.assert_awaited_once()


def test_no_default_cookie_loading(tmp_path, monkeypatch):
    a, chromium, context = runtime(tmp_path, monkeypatch)
    monkeypatch.delenv('GOOFISH_COOKIES_PATH')
    async def run():
        with pytest.raises(Exception):
            async with a.goofish_page():
                pytest.fail('no cookies')
    asyncio.run(run())
    chromium.launch_persistent_context.assert_not_called()


@pytest.mark.parametrize('operation', ['search', 'orders', 'inventory', 'messages'])
def test_cdp_connection_does_not_apply_browser_defaults(tmp_path, monkeypatch, operation):
    a, chromium, context = runtime(tmp_path, monkeypatch)
    for key, value in {'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:9999',
                       'XY_BROWSER_CDP_ACCOUNT_ID': 'fake', 'XY_OPERATION_ACCOUNT_ID': 'fake',
                       'XY_BROWSER_CDP_UID': '12345'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(a, 'websocket_url', lambda address: 'ws://127.0.0.1:9999/devtools/browser/fake')
    @asynccontextmanager
    async def guard(ws):
        yield ws
    monkeypatch.setattr(a, 'guarded_websocket', guard)
    context.cookies = AsyncMock(return_value=[{'name': 'unb', 'value': '12345', 'domain': '.goofish.com'}])
    context.new_page.return_value = MagicMock(close=AsyncMock())
    chromium.connect_over_cdp = AsyncMock(return_value=MagicMock(contexts=[context]))
    session = MagicMock(send=AsyncMock(), detach=AsyncMock())
    context.new_cdp_session = AsyncMock(return_value=session)
    if operation == 'search':
        async def run():
            async with a.goofish_page(cookies={'unb': 'wrong'}):
                pass
        asyncio.run(run())
    else:
        from xianyu_workbench import operations_browser as ops
        monkeypatch.setattr(ops, 'capture', AsyncMock(return_value={'items': []}))
        monkeypatch.setattr(ops, 'capture_messages', AsyncMock(return_value={'items': []}))
        assert ops.collect(operation) == {'items': []}
    if operation in ('orders', 'inventory'):
        context.new_cdp_session.assert_awaited_once_with(context.new_page.return_value)
        session.send.assert_awaited_once_with('Emulation.setFocusEmulationEnabled', {'enabled': True})
        session.detach.assert_awaited_once()
    else:
        context.new_cdp_session.assert_not_called()
    assert chromium.connect_over_cdp.call_args.kwargs['no_defaults'] is True
    context.add_cookies.assert_not_called()
    context.close.assert_not_called()
    chromium.launch_persistent_context.assert_not_called()


def test_cdp_disconnect_never_launches_fallback(tmp_path, monkeypatch):
    a, chromium, context = runtime(tmp_path, monkeypatch)
    for key, value in {'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:9999',
                       'XY_BROWSER_CDP_ACCOUNT_ID': 'fake', 'XY_OPERATION_ACCOUNT_ID': 'fake',
                       'XY_BROWSER_CDP_UID': '12345'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(a, 'websocket_url', lambda address: 'ws://127.0.0.1:9999/devtools/browser/fake')
    @asynccontextmanager
    async def guard(ws):
        yield ws
    monkeypatch.setattr(a, 'guarded_websocket', guard)
    chromium.connect_over_cdp = AsyncMock(side_effect=RuntimeError('disconnected'))
    async def run():
        with pytest.raises(RuntimeError, match='disconnected'):
            async with a.goofish_page():
                pytest.fail('must not yield')
    asyncio.run(run())
    chromium.connect_over_cdp.assert_awaited_once()
    chromium.launch_persistent_context.assert_not_called()


@pytest.mark.parametrize('operation', ['item', 'chats', 'history', 'message.send', 'item.delete', 'item.publish'])
def test_cdp_operations_fail_closed(monkeypatch, operation):
    from xianyu_workbench.browser_adapter import validate_operation
    monkeypatch.setenv('XY_BROWSER_CDP_ENDPOINT', 'http://127.0.0.1:9999')
    with pytest.raises(Exception):
        validate_operation(operation)
