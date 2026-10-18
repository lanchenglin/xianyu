"""Only fresh isolated Chromium; never attach to an existing user browser."""
import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.cdp_startup import wait_for_cdp_port

PROBE = Path(__file__).resolve().parents[1] / 'scripts' / 'page_state_probe.js'
pytestmark = pytest.mark.skipif(not os.getenv('XY_TEST_CHROMIUM'), reason='isolated Chromium opt-in')


@pytest.fixture
def isolated_cdp(tmp_path):
    profile = tmp_path / 'probe-profile'
    process = subprocess.Popen([
        os.environ['XY_TEST_CHROMIUM'], '--headless=new', '--no-sandbox',
        '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
        '--no-proxy-server', '--remote-debugging-address=127.0.0.1',
        '--remote-debugging-port=0', '--user-data-dir=' + str(profile), 'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'TMPDIR')})
    try:
        port = wait_for_cdp_port(process, profile)
        assert port not in (9235, 8099)
        yield f'http://127.0.0.1:{port}'
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_probe_geometry_resource_state_without_page_secrets(isolated_cdp):
    # Catch leaking page text/URLs/attributes or measuring the wrong scroll root.
    assert PROBE.exists(), 'read-only page state probe is not implemented'

    async def check():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(isolated_cdp, no_defaults=True)
            context = browser.contexts[0]
            original = context.pages[0]
            page = await context.new_page()
            try:
                await page.route('**/*', lambda route: route.abort())
                await page.set_content('''<!doctype html><style>
                    body {margin:0; width:1800px; height:2400px}
                    .card {height:100px; width:200px; display:block}
                    </style><div class="card" data-secret="PRIVATE_ATTRIBUTE">PRIVATE_TEXT</div>
                    <img src="https://invalid.example/PRIVATE_PATH?token=PRIVATE_QUERY">
                    <script>window.secret='PRIVATE_SCRIPT'</script>''', wait_until='domcontentloaded')
                result = await page.evaluate(PROBE.read_text(), ['.card'])
                assert result['root']['scrollHeight'] == 2400
                assert result['groups'][0]['count'] == 1
                assert result['groups'][0]['samples'][0]['rect']['height'] == 100
                assert result['groups'][0]['samples'][0]['css']['display'] == 'block'
                assert result['stylesheets'][0]['ruleCount'] == 2
                assert result['images']['count'] == 1
                assert result['scriptCount'] == 1
                assert 'PRIVATE_' not in json.dumps(result)
                assert 'invalid.example' not in json.dumps(result)
                assert len(context.pages) == 2 and not original.is_closed()
            finally:
                await page.close()
            assert len(context.pages) == 1
    asyncio.run(check())


@pytest.mark.parametrize('cancel', [False, True])
def test_task_focus_isolated_target_lifetime(isolated_cdp, monkeypatch, cancel):
    from xianyu_workbench import cdp

    async def check():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(isolated_cdp, no_defaults=True)
            context = browser.contexts[0]
            original = context.pages[0]
            # Identity is tested with synthetic cookies in test_cdp; no cookie injection here.
            async def identity(owned_browser, uid):
                assert owned_browser is browser and uid == 'fixture'
                return context
            monkeypatch.setattr(cdp, 'check_identity', identity)
            commands = []
            sessions = []
            real_session = context.new_cdp_session
            async def tracked_session(target):
                assert target is not original
                session = await real_session(target)
                send = session.send
                async def tracked_send(method, params=None):
                    commands.append((target, method, params))
                    return await send(method, params)
                monkeypatch.setattr(session, 'send', tracked_send)
                sessions.append(session)
                return session
            monkeypatch.setattr(context, 'new_cdp_session', tracked_session)
            async def work():
                async with cdp.task_page(browser, 'fixture', focus_emulation=True) as page:
                    await page.set_content('<!doctype html><body>fixture</body>')
                    # Do not activate the original: creation leaves it backgrounded.
                    assert await original.evaluate('document.hidden') is True
                    assert await page.evaluate('document.hidden') is False
                    assert commands == [(page, 'Emulation.setFocusEmulationEnabled', {'enabled': True})]
                    if cancel:
                        asyncio.current_task().cancel()
                        await asyncio.sleep(0)
                return page
            if cancel:
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.create_task(work())
            else:
                await work()
            assert len(context.pages) == 1 and context.pages[0] is original
            assert original.url == 'about:blank' and not original.is_closed()
            assert len(sessions) == 1
            with pytest.raises(Exception, match='closed|detached'):
                await sessions[0].send('Runtime.evaluate', {'expression': '1'})
    asyncio.run(check())


@pytest.mark.parametrize('no_defaults', [True, False])
def test_cdp_focus_characterization(isolated_cdp, no_defaults):
    """A background tab can gate layout on visibility, independent of viewport."""
    async def check():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(isolated_cdp, no_defaults=no_defaults)
            context = browser.contexts[0]
            original = context.pages[0]
            page = await context.new_page()
            try:
                await page.set_content('''<!doctype html><body><script>
                    function layout() {
                        document.body.style.height = document.hidden ? '1241px' : '3729px';
                    }
                    document.addEventListener('visibilitychange', layout); layout();
                    </script></body>''')
                await original.bring_to_front()
                await page.wait_for_timeout(150)
                before = await page.evaluate('() => ({hidden:document.hidden, height:document.body.offsetHeight, width:innerWidth})')
                assert before['hidden'] is no_defaults
                assert before['height'] == (1241 if no_defaults else 3729)
                if no_defaults:
                    session = await context.new_cdp_session(page)
                    await session.send('Emulation.setFocusEmulationEnabled', {'enabled': True})
                    after = await page.evaluate('() => ({hidden:document.hidden, height:document.body.offsetHeight, width:innerWidth})')
                    assert after == {'hidden': False, 'height': 3729, 'width': before['width']}
                    await session.detach()
                assert not original.is_closed()
            finally:
                await page.close()
    asyncio.run(check())
