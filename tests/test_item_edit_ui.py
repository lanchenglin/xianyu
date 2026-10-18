import json
import os
from pathlib import Path

import httpx
import pytest

from tests.test_item_edit import protocol
from tests.test_mcp_stdio import api_server as api_server


def test_admin_edit_form_and_single_action_warning():
    html = Path('xianyu_workbench/static/index.html').read_text()
    js = Path('xianyu_workbench/static/app.js').read_text()
    assert 'id="item-edit-form"' in html
    assert 'id="edit-protocol-form"' in html
    assert '同 ID 编辑仅修改文字/价格' in js
    assert "$('item-edit-form').reset()" in js


def test_admin_edit_ui_local_only(api_server):
    executable = os.getenv('XY_TEST_CHROMIUM')
    if not executable:
        pytest.skip('set XY_TEST_CHROMIUM for isolated UI')
    from playwright.sync_api import expect, sync_playwright
    url, settings, service = api_server
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}) as client:
        client.post('/api/accounts', json={'label': '虚构编辑', 'mode': 'live',
                    'cookies_json': '{"unb":"12345","_m_h5_tk":"fictional_1"}'}).raise_for_status()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            page.locator('#login-token').fill(settings.admin_token)
            page.locator('#login-form button').click()
            page.locator('[data-page="listings"]').click()
            page.locator('#edit-protocol-form textarea').fill(json.dumps(protocol()))
            page.locator('#edit-protocol-form button').click()
            expect(page.locator('#toast')).to_contain_text('编辑协议已保存')
            for key, value in {'item_id': '777', 'title': '<script>fictional</script>', 'desc': 'exact\nbody', 'price': '13.20'}.items():
                page.locator(f'#item-edit-form [name="{key}"]').fill(value)
            page.locator('#item-edit-form button').click()
            expect(page.locator('#queue-list')).to_contain_text('同 ID 编辑/改价')
            expect(page.locator('#queue-list')).to_contain_text('<script>fictional</script>')
            assert page.locator('#queue-list script').count() == 0
            assert service.db.one("SELECT state FROM actions WHERE kind='item.edit'")['state'] == 'pending'
            page.locator('#logout').click()
            page.locator('#login-token').fill(settings.agent_token)
            page.locator('#login-form button').click()
            page.locator('[data-page="listings"]').click()
            expect(page.locator('#item-edit-form')).not_to_be_visible()
            expect(page.locator('#edit-protocol-form')).not_to_be_visible()
        finally:
            browser.close()
