"""Fictional data only; no platform or logged-in browser access."""
from dataclasses import replace

import pytest

from tests.test_workbench import AGENT, account, approve, message
from tests.test_workbench import workbench as workbench
from xianyu_workbench.browser_adapter import validate_operation
from xianyu_workbench.browser_config import BrowserError


def test_send_switch_defaults_off(workbench):
    _, service = workbench
    assert service.s.message_send_enabled is False
    caps = workbench[0].get('/api/capabilities').json()
    assert caps['message_send_policy']['default_enabled'] is False
    assert caps['message_send_policy']['allowed_operations'] == ['message.send']
    assert caps['message_send_policy']['credential_source'] == 'independent_cookie_ws'
    assert caps['message_send_policy']['automatic_acceptance_verified'] is False


def test_bridge_exact_opt_in(monkeypatch):
    for key, value in {
        'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:19876',
        'XY_BROWSER_CDP_ACCOUNT_ID': 'fictional', 'XY_OPERATION_ACCOUNT_ID': 'fictional',
        'XY_BROWSER_CDP_UID': '11', 'XY_OPERATION_UID': '11',
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(BrowserError):
        validate_operation('message.send')
    monkeypatch.setenv('XY_MESSAGE_SEND_ENABLED', 'true')
    validate_operation('message.send')
    for operation in ('item.delete', 'item.publish', 'history', 'chats', 'javascript'):
        with pytest.raises(BrowserError):
            validate_operation(operation)


def test_execute_selected_never_drains_other_approved(workbench):
    client, service = workbench
    aid = account(client)
    first = message(client, aid, key='historical-001').json()
    second = message(client, aid, key='selected-0002').json()
    approve(client, first)
    approve(client, second)
    response = client.post(f"/api/actions/{second['id']}/execute", json={'digest': second['digest'], 'confirm': '确认执行'})
    assert response.status_code == 200, response.text
    assert client.get(f"/api/actions/{second['id']}").json()['state'] == 'simulated'
    assert client.get(f"/api/actions/{first['id']}").json()['state'] == 'approved'
    assert client.post(f"/api/actions/{second['id']}/execute", json={'digest': second['digest'], 'confirm': '确认执行'}).status_code == 409


def test_execute_selected_admin_only(workbench):
    client, _ = workbench
    aid = account(client)
    action = message(client, aid).json()
    approve(client, action)
    response = client.post(f"/api/actions/{action['id']}/execute", headers={'Authorization': 'Bearer ' + AGENT},
                           json={'digest': action['digest'], 'confirm': '确认执行'})
    assert response.status_code == 403


def test_enabled_switch_requires_fixed_cdp_binding(workbench):
    _, service = workbench
    with pytest.raises(ValueError, match='message_send_binding_required'):
        replace(service.s, message_send_enabled=True).validate()
