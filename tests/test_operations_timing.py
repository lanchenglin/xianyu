"""Real CDP on intercepted HTML, fresh Chromium; no platform or service I/O."""
import asyncio
import json
import os

import pytest
from test_operation_pagination import order_page
from test_operations import inventory

pytestmark = pytest.mark.skipif(not os.getenv('XY_TEST_CHROMIUM'), reason='isolated Chromium opt-in')


@pytest.mark.parametrize('kind,late_hook,pages', [('inventory', False, 2), ('orders', True, 2),
                                                ('orders', False, 5)])
def test_delayed_layout_and_hook_continue_observation(kind, late_hook, pages):
    from playwright.async_api import async_playwright

    from xianyu_workbench.operations_browser import capture

    async def check():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=os.environ['XY_TEST_CHROMIUM'], headless=True)
            try:
                context = await browser.new_context()
                requests = []
                api = 'mtop.idle.web.xyh.item.list' if kind == 'inventory' else 'mtop.idle.web.trade.bought.list'
                endpoint = f'https://h5api.m.goofish.com/h5/{api}/1.0/'
                # Response precedes rendering/hook registration by 2.7s. The late-hook
                # variant has already reached bottom: another scrollTo(bottom) is a no-op.
                html = '''<body style="margin:0;height:HEIGHTpx"><script>
                window.scrolls = [];
                window.addEventListener('scroll', () => scrolls.push(performance.now()));
                const endpoint = ENDPOINT;
                let loading = true, count = 0;
                async function load() {
                    loading = true;
                    await (await fetch(endpoint)).json();
                    count++;
                    setTimeout(() => {
                        document.body.style.height = (4000 * count) + 'px';
                        loading = false;
                    }, 2700);
                }
                load();
                fetch('https://h5api.m.goofish.com/h5/mtop.idle.web.user.page.head/1.0/');
                setTimeout(() => window.addEventListener('scroll', () => {
                    if (!loading && innerHeight + scrollY >= document.body.scrollHeight - 2) load();
                }), HOOK);
                </script></body>'''.replace('HEIGHT', '4000' if late_hook else '100').replace(
                    'ENDPOINT', json.dumps(endpoint)).replace('HOOK', '2700' if late_hook else '0')

                async def route(route):
                    url = route.request.url
                    if url == f'https://www.goofish.com/{"personal" if kind == "inventory" else "bought"}':
                        await route.fulfill(content_type='text/html', body=html)
                    elif url == endpoint:
                        requests.append(url)
                        n = len(requests)
                        value = inventory() if kind == 'inventory' else order_page(str(9000 + n), str(n))
                        if kind == 'inventory':
                            value['data']['cardList'][0]['cardData']['id'] = str(1000 + n)
                            value['data']['nextPage'] = n < 2
                        elif n == pages and pages == 2:
                            value['data']['nextPage'] = 'false'
                        elif n > pages:
                            await asyncio.sleep(30)
                            return
                        await route.fulfill(content_type='application/json', headers={
                            'Access-Control-Allow-Origin': '*'}, body=json.dumps(value))
                    elif 'page.head' in url:
                        await route.fulfill(content_type='application/json', headers={
                            'Access-Control-Allow-Origin': '*'}, body=json.dumps({
                                'ret': ['SUCCESS::OK'], 'data': {'baseInfo': {'self': True}}}))
                    else:
                        await route.abort()

                await context.route('**/*', route)
                page = await context.new_page()
                result = await capture(page, kind, timeout=18 if pages == 5 else 8)
                assert result['pages_read'] == pages
                assert pages <= len(requests) <= pages + (pages == 5)
                assert len(result['items']) == pages
                assert result['partial'] is (kind == 'orders')
                expected_stop = 'time_limit' if pages == 5 else (
                    'end_reached' if kind == 'inventory' else 'pagination_semantics_unknown')
                assert result['stop_reason'] == expected_stop
                scrolls = await page.evaluate('scrolls')
                assert all(b - a >= 450 for a, b in zip(scrolls, scrolls[1:]))
            finally:
                await browser.close()

    asyncio.run(check())
