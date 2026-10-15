"""Opt-in local Chromium only; fake cookies, fresh profiles, no marketplace navigation."""
import asyncio
import os
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(not os.getenv('XY_TEST_CHROMIUM'), reason='set XY_TEST_CHROMIUM for isolated system browser tests')


def test_real_isolated_launch(tmp_path, monkeypatch):
    from xianyu_workbench.browser_adapter import goofish_page
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('XY_BROWSER', 'chromium')
    monkeypatch.setenv('XY_BROWSER_EXECUTABLE', os.environ['XY_TEST_CHROMIUM'])
    monkeypatch.setenv('XY_OPERATION_UID', '12345')
    monkeypatch.delenv('XY_BROWSER_CDP_ENDPOINT', raising=False)
    async def run():
        async with goofish_page(headless=True, cookies={'unb': '12345'}) as page:
            assert page.url == 'about:blank'
            await page.set_content('<title>isolated test</title><p>fake data only</p>')
            assert await page.title() == 'isolated test'
    asyncio.run(run())
    assert not list((tmp_path / '.goofish-cli/profiles').iterdir())


def test_real_cdp_disconnect_keeps_browser_and_existing_tab(tmp_path, monkeypatch):
    from playwright.async_api import async_playwright

    from xianyu_workbench.browser_adapter import goofish_page
    from xianyu_workbench.cdp import guarded_websocket, websocket_url
    profile = tmp_path / 'profile'
    profile.mkdir()
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'SYSTEMROOT', 'TMPDIR', 'LANG')}
    env.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    process = subprocess.Popen([os.environ['XY_TEST_CHROMIUM'], '--headless=new', '--no-sandbox',
        '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
        '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
        '--user-data-dir=' + str(profile), 'about:blank'], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        port_file = profile / 'DevToolsActivePort'
        for _ in range(150):
            if port_file.exists() or process.poll() is not None:
                break
            time.sleep(.1)
        assert port_file.exists(), 'isolated Chromium did not expose its random CDP port'
        port = int(port_file.read_text().splitlines()[0])
        assert port != 9235
        address = f'http://127.0.0.1:{port}'
        for key, value in {'XY_BROWSER_CDP_ENDPOINT': address, 'XY_BROWSER_CDP_ACCOUNT_ID': 'fake-account',
                           'XY_OPERATION_ACCOUNT_ID': 'fake-account', 'XY_BROWSER_CDP_UID': '12345',
                           'XY_OPERATION_UID': '12345'}.items():
            monkeypatch.setenv(key, value)
        async def run():
            ws = websocket_url(address)
            async with guarded_websocket(ws) as guarded, async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(guarded)
                context = browser.contexts[0]
                original = context.pages[0]
                await original.set_content('<title>owned by fixture</title>')
                # Only the test fixture seeds fake identity; adapter may not mutate it.
                await context.add_cookies([{'name': 'unb', 'value': '12345', 'domain': '.goofish.com', 'path': '/'}])
                before = await context.cookies()
                async with goofish_page(cookies={'unb': 'must-not-inject'}) as task:
                    assert task.url == 'about:blank'
                    await task.set_content('<p>local task only</p>')
                    assert len(context.pages) == 2
                assert not original.is_closed()
                assert await original.title() == 'owned by fixture'
                assert len(context.pages) == 1
                assert await context.cookies() == before
                assert process.poll() is None
                with pytest.raises(RuntimeError, match='local failure'):
                    async with goofish_page():
                        raise RuntimeError('local failure')
                assert len(context.pages) == 1
                assert not original.is_closed()
                # Exercise the real provider timeout and bridge cancellation, not a
                # manually raised exception. Only replace marketplace work with local HTML.
                from unittest.mock import MagicMock

                from cryptography.fernet import Fernet

                from xianyu_workbench.config import Settings
                from xianyu_workbench.provider import Problem, Provider
                settings = Settings(tmp_path / 'workbench', 'a'*40, 'b'*40, Fernet.generate_key().decode(),
                                    operation_timeout=5, browser_cdp_endpoint=address,
                                    browser_cdp_account_id='fake-account', browser_cdp_uid='12345')
                vault = MagicMock()
                vault.open.side_effect = AssertionError('CDP must not decrypt')
                provider = Provider(settings, MagicMock(), vault)
                real_popen = subprocess.Popen
                script = '''
import asyncio
from xianyu_workbench import bridge
from xianyu_workbench.browser_adapter import goofish_page, install
async def local():
    async with goofish_page() as page:
        await page.set_content('<title>timeout task</title>')
        await asyncio.sleep(60)
def dispatch(operation, payload):
    install(operation)
    return asyncio.run(local())
bridge.dispatch = dispatch
bridge.main()
'''
                def spawn(command, **kwargs):
                    assert 'GOOFISH_COOKIES_PATH' not in kwargs['env']
                    return real_popen([command[0], '-u', '-c', script], **kwargs)
                with monkeypatch.context() as patch:
                    patch.setattr('xianyu_workbench.provider.subprocess.Popen', spawn)
                    call = asyncio.create_task(asyncio.to_thread(provider._live,
                        {'id': 'fake-account', 'uid': '12345', 'secret': 'must-not-read'}, 'search', {}, write=False))
                    saw_task = False
                    for _ in range(100):
                        if len(context.pages) == 2:
                            saw_task = True
                            break
                        if call.done():
                            break
                        await asyncio.sleep(.05)
                    with pytest.raises(Problem) as error:
                        await call
                    assert error.value.code == 'timeout'
                    assert saw_task, 'test must observe the owned page before timeout'
                assert len(context.pages) == 1
                assert not original.is_closed()
                assert await original.title() == 'owned by fixture'
                assert await context.cookies() == before
                assert process.poll() is None
                vault.open.assert_not_called()
            # Both Playwright connections stopped; process and original target still alive.
            assert process.poll() is None
            async with guarded_websocket(ws) as guarded, async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(guarded)
                assert len(browser.contexts[0].pages) == 1
                assert await browser.contexts[0].pages[0].title() == 'owned by fixture'
        asyncio.run(run())
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
