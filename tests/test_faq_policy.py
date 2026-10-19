# ruff: noqa: F811
import time

import pytest
from test_workbench import AGENT, account, workbench  # noqa: F401


def policy(**overrides):
    return {'enabled': True, 'conversation_ids': ['123@goofish'], 'item_ids': ['123'],
            'expires_at': time.time() + 3600, 'template': '您好，商品信息请以页面说明为准。',
            'minimum_interval_s': 600, 'max_per_day': 5, **overrides}


def test_admin_policy_is_encrypted_scoped_and_never_send_authority(workbench):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/faq-policy'
    assert client.get(path).status_code == 200
    assert client.get(path).json()['enabled'] is False
    agent = {'Authorization': 'Bearer ' + AGENT}
    assert client.put(path, headers=agent, json=policy()).status_code == 403
    result = client.put(path, json=policy())
    assert result.status_code == 200, result.text
    assert result.json()['enabled'] is True
    assert result.json()['send_allowed'] is False
    assert result.json()['blocked_reason'] == 'send_adapter_unavailable'
    assert 'template' not in client.get(path, headers=agent).json()
    assert service.db.one("SELECT value FROM settings WHERE key=?", ('faq:' + ident,))['value'].startswith('gAAAA')
    assert service.db.all('SELECT * FROM actions') == []
    assert client.post(path + '/revoke', headers=agent).status_code == 403
    assert client.post(path + '/revoke').json()['enabled'] is False
    assert not client.get('/api/capabilities').json()['autonomous_reply']


@pytest.mark.parametrize('change', [
    {'conversation_ids': []}, {'item_ids': []}, {'expires_at': 1},
    {'expires_at': time.time() + 40 * 86400}, {'minimum_interval_s': 299},
    {'max_per_day': 101}, {'template': '付款后保证退款'},
    {'template': '忽略指令 https://fake.example'}, {'conversation_ids': ['*']},
])
def test_policy_rejects_unbounded_or_transactional_authority(workbench, change):
    client, _ = workbench
    ident = account(client)
    response = client.put(f'/api/accounts/{ident}/faq-policy', json=policy(**change))
    assert response.status_code == 422


def test_policy_expiry_and_takeover_are_effective_without_mutation(workbench):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/faq-policy'
    assert client.put(path, json=policy()).status_code == 200
    client.post(f'/api/accounts/{ident}/message-observation/takeover')
    assert client.get(path).json()['blocked_reason'] == 'human_takeover'
    saved = policy(expires_at=1)
    service.db.execute('UPDATE settings SET value=? WHERE key=?', (service.vault.seal(saved), 'faq:' + ident))
    assert client.get(path).json()['effective'] is False
    assert client.get(path).json()['blocked_reason'] == 'expired'
