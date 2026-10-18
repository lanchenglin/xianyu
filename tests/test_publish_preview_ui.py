"""Isolated Chromium against a disposable local API; never platform browser."""
import json
import os

import httpx
import pytest

from tests.test_mcp_stdio import api_server as api_server
from tests.test_publish_preview import DEFAULTS
from tests.test_workbench import upload


def test_local_publish_preview_ui(api_server):
    executable = os.getenv('XY_TEST_CHROMIUM')
    if not executable:
        pytest.skip('set XY_TEST_CHROMIUM for isolated UI')
    from playwright.sync_api import expect, sync_playwright
    url, settings, service = api_server
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}) as client:
        aid = client.post('/api/accounts', json={'label': '本地发布', 'mode': 'demo'}).json()['id']
        image = upload(client, aid)
        client.post('/api/drafts', json={'account_id': aid, 'title': '虚构商品', 'desc': '本地测试',
                                       'price': '12.30', 'images': [image]})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=executable, headless=True)
            try:
                page = browser.new_page()
                page.goto(url)
                page.locator('#login-token').fill(settings.admin_token)
                page.locator('#login-form button').click()
                page.locator('[data-page="listings"]').click()
                page.locator('#daily-publish-status').click()
                expect(page.locator('#daily-publish-result')).to_contain_text('"enabled": false')
                page.locator('#daily-publish-tick').click()
                expect(page.locator('#daily-publish-result')).to_contain_text('disabled')
                page.locator('#daily-publish-revoke').click()
                expect(page.locator('#daily-publish-result')).to_contain_text('"enabled": false')
                import sqlite3
                with sqlite3.connect(service.db.path) as c:
                    c.execute('INSERT INTO daily_publish_dates VALUES(?,?,?,?)', (aid, '2026-10-18', 'missing-ui', 'old'))
                page.locator('#daily-publish-status').click()
                expect(page.locator('#daily-publish-result')).to_contain_text('"effective": false')
                expect(page.locator('#daily-publish-result')).to_contain_text('daily_unresolved')
                page.locator('#daily-publish-tick').click()
                expect(page.locator('#daily-publish-result')).to_contain_text('daily_unresolved')
                page.locator('#publish-defaults-form textarea').fill(json.dumps(DEFAULTS, ensure_ascii=False))
                page.locator('#publish-defaults-form button').click()
                expect(page.locator('#toast')).to_contain_text('本地快照已加密保存')
                page.locator('#publish-protocol-form textarea').fill(json.dumps({
                    'template': {'imageInfoDOList': [], 'uniqueCode': 'fictional-ui'},
                    'success_ret': ['SUCCESS::fixture'], 'evidence': 'Isolated UI fixture only',
                    'readback_success_ret': ['SUCCESS::readback-fixture'],
                    'readback_status': {'path': ['data', 'fixtureStatus'], 'value_type': 'string',
                                        'allowed_values': ['FICTIONAL_LISTED']},
                    'readback_content': {'title': ['data', 'itemDO', 'title'], 'desc': ['data', 'itemDO', 'desc'],
                                         'price': ['data', 'itemDO', 'soldPrice'], 'transport_fee': ['data', 'itemDO', 'transportFee'],
                                         'images': ['data', 'itemDO', 'imageInfos'],
                                         'expected_price': '12.30', 'expected_transport_fee': '0'},
                    'upload_authorized': True}))
                page.locator('#publish-protocol-form button').click()
                expect(page.locator('#toast')).to_contain_text('协议已加密保存')
                page.get_by_role('button', name='载入编辑区', exact=True).click()
                page.locator('#listing-form .primary').click()
                expect(page.locator('#toast')).to_contain_text('待你审批')
                page.locator('#publish-preview').click()
                expect(page.locator('#queue-list')).to_contain_text('private-poi')
                actions = client.get('/api/actions').json()
                assert len(actions) == 2 and actions[0]['state'] == 'pending'
                page.locator('#logout').click()
                page.locator('#login-token').fill(settings.agent_token)
                page.locator('#login-form button').click()
                page.locator('[data-page="queue"]').click()
                expect(page.locator('#queue-list')).to_contain_text('测试市')
                expect(page.locator('#queue-list')).not_to_contain_text('private-poi')
                expect(page.locator('#queue-list')).not_to_contain_text('120.1')
                page.locator('[data-page="listings"]').click()
                expect(page.locator('#publish-defaults-form')).not_to_be_visible()
                expect(page.locator('#publish-protocol-form')).not_to_be_visible()
                expect(page.locator('#daily-publish-form')).not_to_be_visible()
            finally:
                browser.close()
