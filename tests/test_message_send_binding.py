import time
from dataclasses import replace

import pytest

from tests.test_workbench import account, approve
from tests.test_workbench import workbench as workbench
from xianyu_workbench.provider import Problem


def setup_live(client, service, monkeypatch):
    aid = account(client, 'live', '{"unb":"11","cookie2":"fictional","_m_h5_tk":"fictional_123456"}')
    settings = replace(service.s, live_enabled=True, message_send_enabled=True,
                       browser_cdp_endpoint='http://127.0.0.1:19876', browser_cdp_account_id=aid, browser_cdp_uid='11')
    service.s = service.provider.s = settings
    items = [{'cid': '123', 'peer_uid': '22', 'sender_uid': '22', 'recipient_verified': True,
              'message_id': '100.abc', 'direction': 'incoming', 'body': '你好', 'body_status': 'available',
              'created_at': int(time.time()*1000)}]
    calls = []

    def live(account, operation, payload, *, write):
        calls.append((operation, payload.copy()))
        if operation == 'messages':
            return {'items': items.copy()}
        assert operation == 'message.send'
        assert payload == {'cid': '123', 'toid': '22', 'text': '您好'}
        return {'ok': True, 'mid': 'local-only'}

    monkeypatch.setattr(service.provider, '_live', live)
    return aid, items, calls


def propose(client, aid, key='safe-send-001'):
    return client.post('/api/actions', json={'account_id': aid, 'kind': 'message.send',
                       'payload': {'cid': '123', 'toid': '22', 'text': '您好'}, 'idempotency_key': key})


def test_verified_pair_frozen_and_rechecked(workbench, monkeypatch):
    client, service = workbench
    aid, items, calls = setup_live(client, service, monkeypatch)
    response = propose(client, aid)
    assert response.status_code == 201, response.text
    action = response.json()
    assert action['payload']['_binding']['uid'] == '11'
    assert action['payload']['_binding']['source'] == 'independent_cookie_ws'
    approve(client, action)
    service.execute_one(action['id'], action['digest'])
    assert [op for op, _ in calls] == ['messages', 'messages', 'message.send', 'messages']
    result = client.get('/api/actions/' + action['id']).json()
    assert result['state'] == 'unconfirmed'
    assert result['result']['verification'] == 'unconfirmed'
    assert result['result']['delivery_confirmed'] is False


@pytest.mark.parametrize('change', ['peer', 'cookie', 'switch', 'takeover', 'expired'])
def test_binding_changes_never_send(workbench, monkeypatch, change):
    client, service = workbench
    aid, items, calls = setup_live(client, service, monkeypatch)
    response = propose(client, aid)
    assert response.status_code == 201, response.text
    action = response.json()
    approve(client, action)
    if change == 'peer':
        items[0]['peer_uid'] = '33'
    elif change == 'cookie':
        service.db.execute('UPDATE accounts SET secret=? WHERE id=?', (service.vault.seal({'unb': '11', 'cookie2': 'changed'}), aid))
    elif change == 'switch':
        service.s = service.provider.s = replace(service.s, message_send_enabled=False)
    elif change == 'takeover':
        service.observation.takeover(aid, True, 'admin')
    else:
        service.db.execute('UPDATE actions SET expires=? WHERE id=?', (time.time()-1, action['id']))
    try:
        service.execute_one(action['id'], action['digest'])
    except Problem:
        pass
    assert not any(op == 'message.send' for op, _ in calls)


def test_idempotent_proposal_does_not_repeat_read(workbench, monkeypatch):
    client, service = workbench
    aid, items, calls = setup_live(client, service, monkeypatch)
    first = propose(client, aid)
    assert first.status_code == 201
    second = propose(client, aid)
    assert second.status_code == 201
    assert second.json()['id'] == first.json()['id']
    assert len(calls) == 1


def test_live_messages_require_selected_execution(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    assert service.run_once() is False
    assert not any(op == 'message.send' for op, _ in calls)


def test_frozen_binding_private_to_admin(workbench, monkeypatch):
    from tests.test_workbench import AGENT
    client, service = workbench
    aid, _, _ = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    result = client.get('/api/actions/' + action['id'], headers={'Authorization': 'Bearer ' + AGENT}).json()
    assert 'credential_digest' not in str(result)
    assert '19876' not in str(result)


def test_write_failure_is_terminal_and_readback_only(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    original = service.provider._live

    def fail(account, operation, payload, *, write):
        if write:
            calls.append((operation, payload))
            raise Problem('uncertain', 'unknown', 504)
        return original(account, operation, payload, write=write)

    monkeypatch.setattr(service.provider, '_live', fail)
    result = service.execute_one(action['id'], action['digest'])
    assert result['state'] == 'unconfirmed'
    assert result['result']['verification'] == 'unconfirmed'
    assert [op for op, _ in calls] == ['messages', 'messages', 'message.send', 'messages']
    assert not service.run_once()


def test_cookie_change_during_preflight_cannot_change_send_identity(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    original = service.provider._live

    def mutate(account, operation, payload, *, write):
        result = original(account, operation, payload, write=write)
        if operation == 'messages':
            service.db.execute('UPDATE accounts SET secret=? WHERE id=?',
                (service.vault.seal({'unb': '11', '_m_h5_tk': 'changed_123'}), aid))
        return result

    monkeypatch.setattr(service.provider, '_live', mutate)
    service.execute_one(action['id'], action['digest'])
    assert not any(op == 'message.send' for op, _ in calls)
