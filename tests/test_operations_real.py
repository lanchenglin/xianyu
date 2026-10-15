"""Fresh Chromium, random CDP port, intercepted fictional pages only."""
import asyncio
import json
import os
import subprocess
import time

import pytest
from test_operations import inventory, orders

pytestmark = pytest.mark.skipif(not os.getenv('XY_TEST_CHROMIUM'), reason='isolated Chromium opt-in')


def test_real_cdp_network_listener_identity_and_cleanup(tmp_path, monkeypatch):
    from playwright.async_api import async_playwright

    from xianyu_workbench.browser_config import BrowserError
    from xianyu_workbench.operations_browser import collect
    profile = tmp_path / 'fresh-profile'
    profile.mkdir()
    from message_ws_fixture import message_server
    from test_messages import frame
    server = message_server(tmp_path, json.dumps(frame()))
    ws_port, received = server.__enter__()
    process = subprocess.Popen([os.environ['XY_TEST_CHROMIUM'], '--headless=new', '--no-sandbox',
        '--ignore-certificate-errors', '--no-proxy-server',
        '--disable-features=LocalNetworkAccessChecks',
        f'--host-resolver-rules=MAP wss-goofish.dingtalk.com 127.0.0.1:{ws_port}',
        '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
        '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
        '--user-data-dir=' + str(profile), 'about:blank'], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, env={**{k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'TMPDIR')},
                                       'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path)})
    try:
        port_file = profile / 'DevToolsActivePort'
        for _ in range(150):
            if port_file.exists() or process.poll() is not None:
                break
            time.sleep(.1)
        assert port_file.exists()
        port = int(port_file.read_text().splitlines()[0])
        assert port not in (9235, 8099)
        address = f'http://127.0.0.1:{port}'
        for key, value in {'XY_BROWSER_CDP_ENDPOINT': address, 'XY_BROWSER_CDP_ACCOUNT_ID': 'fictional',
            'XY_OPERATION_ACCOUNT_ID': 'fictional', 'XY_BROWSER_CDP_UID': '12345', 'XY_OPERATION_UID': '12345'}.items():
            monkeypatch.setenv(key, value)

        async def check():
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(address)
                context = browser.contexts[0]
                original = context.pages[0]
                await original.set_content('<title>original fixture</title>')
                await context.add_cookies([{'name': 'unb', 'value': '12345', 'domain': '.goofish.com', 'path': '/'}])
                state = {'self': True, 'switch': False}
                async def route(request):
                    url = request.request.url
                    if url == 'https://www.goofish.com/im':
                        await request.fulfill(status=200, content_type='text/html', body=
                            '<script>new WebSocket("wss://wss-goofish.dingtalk.com/")</script>')
                    elif url in ('https://www.goofish.com/bought', 'https://www.goofish.com/personal'):
                        apis = ['mtop.idle.web.trade.bought.list'] if url.endswith('bought') else [
                            'mtop.idle.web.user.page.head', 'mtop.idle.web.xyh.item.list']
                        script = ';'.join(f"fetch('https://h5api.m.goofish.com/h5/{api}/1.0/')" for api in apis)
                        await request.fulfill(status=200, content_type='text/html', body=f'<script>{script}</script>')
                    elif '/h5/' in url:
                        value = orders() if 'bought.list' in url else inventory()
                        if 'page.head' in url:
                            value = {'ret': ['SUCCESS::OK'], 'data': {'baseInfo': {'self': state['self']}}}
                        if state['switch']:
                            await context.add_cookies([{'name': 'unb', 'value': '54321', 'domain': '.goofish.com', 'path': '/'}])
                        await request.fulfill(status=200, content_type='application/json',
                            headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(value))
                    else:
                        await request.abort()
                await context.route('**/*', route)
                for kind in ('orders', 'inventory'):
                    result = await asyncio.to_thread(collect, kind)
                    assert result['partial'] and len(result['items']) == 1
                    assert len(context.pages) == 1
                    assert await original.title() == 'original fixture'
                # Full provider → real bridge subprocess → random local CDP → normalized output.
                from cryptography.fernet import Fernet

                from xianyu_workbench.config import Settings
                from xianyu_workbench.db import DB
                from xianyu_workbench.provider import Problem, Provider
                from xianyu_workbench.security import Vault
                settings = Settings(tmp_path / 'cache', 'a'*40, 'b'*40, Fernet.generate_key().decode(),
                    browser_cdp_endpoint=address, browser_cdp_account_id='fictional', browser_cdp_uid='12345',
                    operation_timeout=3, worker_enabled=False)
                vault = Vault(settings.vault_key)
                provider = Provider(settings, DB(settings.data_dir, vault), vault)
                account = {'id': 'fictional', 'uid': '12345', 'secret': 'must-not-decrypt'}
                value = await asyncio.to_thread(provider._live, account, 'orders', {}, write=False)
                assert value['items'][0]['order_id'] == '9001'
                assert len(context.pages) == 1
                from dataclasses import replace
                provider.s = replace(settings, operation_timeout=20)
                value = await asyncio.to_thread(provider._live, account, 'messages', {}, write=False)
                assert value['items'][0]['message_id'] == '987654'
                assert value['items'][0]['body'] is None
                assert received == []  # No IM commands, ACK, heartbeat or writes from collector.
                assert len(context.pages) == 1 and not original.is_closed()
                provider.s = settings
                # No response on task navigation: cooperative cancellation must close only its tab.
                await context.unroute('**/*', route)
                async def silence(request):
                    await request.fulfill(status=200, content_type='text/html', body='<title>no response</title>')
                await context.route('**/*', silence)
                with pytest.raises(Problem) as error:
                    await asyncio.to_thread(provider._live, account, 'orders', {}, write=False)
                assert error.value.code == 'timeout'
                assert len(context.pages) == 1 and not original.is_closed()
                await context.unroute('**/*', silence)
                await context.route('**/*', route)
                state['self'] = False
                with pytest.raises(BrowserError, match='identity'):
                    await asyncio.to_thread(collect, 'inventory')
                assert len(context.pages) == 1
                state['switch'] = True
                with pytest.raises(BrowserError, match='identity'):
                    await asyncio.to_thread(collect, 'orders')
                assert len(context.pages) == 1 and process.poll() is None
                assert await original.title() == 'original fixture'
        asyncio.run(check())
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
        server.__exit__(None, None, None)
