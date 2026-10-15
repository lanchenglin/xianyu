# ruff: noqa: F811
import asyncio
import os
import sys

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_mcp_stdio import api_server  # noqa: F401


def seed(url, settings):
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}, trust_env=False) as client:
        return client.post('/api/accounts', json={'label': 'Fictional sample account', 'mode': 'demo'}).json()['id']


def test_real_stdio_sample_sync_and_read(api_server, tmp_path):
    url, settings, _ = api_server
    ident = seed(url, settings)
    async def check():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'xianyu_workbench.mcp_server'],
            cwd=str(tmp_path), env={'PATH': os.environ.get('PATH', ''), 'XY_API_URL': url,
                                   'XY_AGENT_TOKEN': settings.agent_token})
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert {'sync_order_sample', 'cached_orders', 'sync_inventory_sample', 'cached_inventory'} <= names
            for tool in ['sync_order_sample', 'cached_orders', 'sync_inventory_sample', 'cached_inventory']:
                result = await session.call_tool(tool, {'account_id': ident})
                assert not result.isError
                assert 'single_page' in str(result) or 'cached_samples' in str(result)
                assert 'partial' in str(result)
    asyncio.run(check())


@pytest.mark.skipif(not os.getenv('XY_TEST_CHROMIUM'), reason='isolated Chromium opt-in')
def test_real_ui_sample_sync_account_switch_and_xss(api_server):
    from playwright.sync_api import expect, sync_playwright
    url, settings, service = api_server
    first = seed(url, settings)
    second = seed(url, settings)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=os.environ['XY_TEST_CHROMIUM'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto(url)
        page.locator('#login-token').fill(settings.agent_token)
        page.locator('#login-form button').click()
        expect(page.locator('#shell')).to_be_visible()
        expect(page.locator('#login-form button')).to_be_enabled()
        page.locator('[data-page="operations"]').click(timeout=3000)
        page.locator('#account-select').select_option(first)
        page.locator('#sync-orders').click()
        expect(page.locator('#orders-samples')).to_contain_text('900001')
        expect(page.locator('#orders-status')).to_contain_text('部分样本')
        page.locator('#sync-messages').click()
        expect(page.locator('#messages-samples')).to_contain_text('987654')
        expect(page.locator('#messages-samples')).to_contain_text('body unavailable')
        expect(page.locator('#messages-samples button')).to_have_count(0)
        page.locator('#sync-inventory').click()
        expect(page.locator('#inventory-samples')).to_contain_text('100001')
        row = service.db.one("SELECT * FROM operation_records WHERE kind='inventory'")
        item = service.vault.open(row['payload'])
        item['title'] = '<img src=x onerror=alert(1)>'
        service.db.execute('UPDATE operation_records SET payload=? WHERE record_key=?',
                           (service.vault.seal(item), row['record_key']))
        page.locator('#refresh-samples').click()
        expect(page.locator('#inventory-samples')).to_contain_text('<img src=x onerror=alert(1)>')
        expect(page.locator('#inventory-samples img')).to_have_count(0)
        page.locator('#account-select').select_option(second)
        expect(page.locator('#orders-samples')).not_to_contain_text('900001')
        expect(page.locator('#messages-samples')).not_to_contain_text('987654')
        expect(page.locator('#inventory-samples')).not_to_contain_text('100001')
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not errors
        browser.close()
