"""Real isolated UI, disposable demo server, worker off."""
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from cryptography.fernet import Fernet


def test_selected_send_ui(tmp_path):
    executable = os.getenv('XY_TEST_CHROMIUM')
    if not executable:
        pytest.skip('set XY_TEST_CHROMIUM for isolated UI')
    from playwright.sync_api import expect, sync_playwright
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, XY_DATA_DIR=str(tmp_path / 'data'), XY_ADMIN_TOKEN='a'*40,
               XY_AGENT_TOKEN='b'*40, XY_VAULT_KEY=Fernet.generate_key().decode(),
               XY_LIVE_ENABLED='false', XY_WORKER_ENABLED='false', XY_MESSAGE_SEND_ENABLED='false',
               XY_BROWSER_CDP_ENDPOINT='', XY_BROWSER_CDP_ACCOUNT_ID='', XY_BROWSER_CDP_UID='')
    process = subprocess.Popen([sys.executable, '-m', 'xianyu_workbench.cli', 'serve', '--port', str(port)],
                               cwd=tmp_path, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f'http://127.0.0.1:{port}'
        with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + 'a'*40}, trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get('/healthz').status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            aid = client.post('/api/accounts', json={'label': '单条演示', 'mode': 'demo'}).json()['id']
            actions = []
            for key in ('historical-001', 'selected-002'):
                action = client.post('/api/actions', json={'account_id': aid, 'kind': 'message.send',
                    'payload': {'cid': 'demo-chat', 'toid': '10001', 'text': key}, 'idempotency_key': key}).json()
                client.post('/api/actions/' + action['id'] + '/approve', json={'digest': action['digest'], 'confirm': '确认执行'})
                actions.append(action)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=executable, headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url)
                    page.locator('#login-token').fill('a'*40)
                    page.locator('#login-form button').click()
                    page.locator('[data-page="queue"]').click()
                    page.once('dialog', lambda dialog: dialog.accept('确认执行'))
                    page.get_by_role('button', name='仅执行这一条', exact=True).first.click(timeout=3000)
                    expect(page.locator('#queue-list')).to_contain_text('演示完成')
                    assert client.get('/api/actions/' + actions[0]['id']).json()['state'] == 'approved'
                    assert client.get('/api/actions/' + actions[1]['id']).json()['state'] == 'simulated'
                    page.route('**/api/accounts/*/messages', lambda route: route.fulfill(json={
                        'items': [{'message_id': 'fictional.123', 'cid': 'demo-chat', 'peer_uid': '10001',
                                   'sender_uid': '10001', 'body': '你好', 'body_status': 'available',
                                   'direction': 'incoming', 'recipient_verified': True, 'created_at': 1780000000000,
                                   'source': 'demo', 'fetched_at': 1780000000}], 'last_sync': None, 'demo': True}))
                    page.locator('[data-page="operations"]').click()
                    page.get_by_role('button', name='选择此会话起草待审批消息', exact=True).click(timeout=3000)
                    expect(page.locator('#chat-title')).to_contain_text('10001')
                    page.locator('#message-text').fill('单条普通咨询')
                    page.locator('#message-form .primary').click()
                    expect(page.locator('#toast')).to_contain_text('待你审批')
                    pending = client.get('/api/actions').json()[0]
                    assert pending['state'] == 'pending'
                    assert pending['payload'] == {'cid': 'demo-chat', 'toid': '10001', 'text': '单条普通咨询'}
                finally:
                    browser.close()
    finally:
        process.terminate()
        process.wait(timeout=15)
