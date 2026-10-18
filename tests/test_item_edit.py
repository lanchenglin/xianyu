"""Fictional same-ID edit contracts; no platform access."""
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.test_workbench import AGENT, account, approve
from tests.test_workbench import workbench as workbench


def protocol():
    before = {'item_id': '777', 'uid': '12345', 'version': 'v1', 'status': 'ONLINE',
              'title': 'old', 'desc': 'old body', 'price': '12.30',
              'invariants': {'images': ['fictional'], 'shipping': 'fixed', 'sku': None}}
    template = {'itemId': '777', 'text': {'title': 'old', 'desc': 'old body'},
                'price': '1230', 'fixed': {'shipping': 'fixed'}, 'status': 'ONLINE',
                'images': ['fictional'], 'sku': None}
    return {'schema_version': 2,
            'original_request': deepcopy(template),
            'invariant_mappings': [
                {'request_path': request, 'before_path': source, 'evidence': 'Fictional readback mapping evidence'}
                for request, source in [(['itemId'], ['item_id']), (['status'], ['status']),
                                        (['fixed', 'shipping'], ['invariants', 'shipping']),
                                        (['images'], ['invariants', 'images']), (['sku'], ['invariants', 'sku'])]], 'item_id': '777', 'uid': '12345', 'api_version': '1.0',
            'template': template,
            'request_paths': {'title': ['text', 'title'], 'desc': ['text', 'desc'], 'price': ['price']},
            'price_encoding': 'cent_string', 'before': before,
            'response_paths': {key: ['data', 'snapshot', key] for key in before},
            'success_ret': ['SUCCESS::fictional-edit'], 'read_success_ret': ['SUCCESS::fictional-read'],
            'complete_semantics_confirmed': True, 'evidence': 'Fictional complete isolated evidence only'}


def ready(client, service):
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    service.s = service.provider.s = replace(service.s, live_enabled=True, edit_enabled=True)
    p = protocol()
    r = client.put(f'/api/accounts/{aid}/edit-protocol', json=p)
    assert r.status_code == 200, r.text
    body = {'account_id': aid, 'kind': 'item.edit', 'payload': {'item_id': '777', 'title': 'new',
            'desc': 'new body\nexact', 'price': '13.20'}, 'idempotency_key': 'edit-fixture-once'}
    r = client.post('/api/item-edit', json=body)
    assert r.status_code == 201, r.text
    action = r.json()
    approve(client, action)
    return aid, action, body


def execute(client, action, headers=None):
    return client.post(f"/api/actions/{action['id']}/execute", json={
        'digest': action['digest'], 'confirm': '确认执行'}, headers=headers)


def transport(events, change=None):
    def call(account, operation, payload, **kwargs):
        events.append(operation)
        if operation == 'edit.submit':
            assert payload['template']['text'] == {'title': 'new', 'desc': 'new body\nexact'}
            assert payload['template']['price'] == '1320'
            if change == 'timeout':
                raise TimeoutError()
            return {'ret': ['SUCCESS::fictional-edit'], 'data': {'itemId': '888' if change == 'ack' else '777'}}
        assert operation == 'edit.read'
        snap = deepcopy(protocol()['before'])
        if 'edit.submit' in events:
            snap.update(title='new', desc='new body\nexact', price='13.20', version='v2')
            if change == 'readback':
                snap['price'] = '13.2'
        elif change in snap:
            snap[change] = 'changed'
        return {'ret': ['SUCCESS::fictional-read'], 'data': {'snapshot': snap}}
    return call


def test_same_protocol_cannot_submit_twice_with_new_idempotency_key(workbench, monkeypatch):
    client, service = workbench
    _, action, body = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events, 'timeout'))
    assert execute(client, action).json()['state'] == 'unconfirmed'
    body['idempotency_key'] = 'different-key-same-contract'
    second_events = []
    monkeypatch.setattr(service.provider, '_live', transport(second_events, 'timeout'))
    second = client.post('/api/item-edit', json=body)
    if second.status_code == 201:
        approve(client, second.json())
        assert execute(client, second.json()).json()['state'] == 'failed'
    else:
        assert second.status_code == 409
    assert events.count('edit.submit') == 1


def test_edit_default_off(workbench):
    client, service = workbench
    assert getattr(service.s, 'edit_enabled', None) is False
    assert client.get('/api/capabilities').json()['item_edit']['platform_verified'] is False


def test_selected_edit_same_id_once(workbench, monkeypatch):
    client, service = workbench
    _, action, body = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events))
    assert service.run_once() is False
    assert execute(client, action, {'Authorization': 'Bearer ' + AGENT}).status_code == 403
    result = execute(client, action).json()
    assert result['state'] == 'submitted', result
    assert result['result']['content_verified'] is True
    assert events == ['edit.read', 'edit.submit', 'edit.read']
    assert execute(client, action).status_code == 409
    assert client.post('/api/item-edit', json=body).json()['id'] == action['id']


@pytest.mark.parametrize('change', ['uid', 'item_id', 'version', 'status', 'title', 'desc', 'price', 'invariants'])
def test_original_change_refuses_write(workbench, monkeypatch, change):
    client, service = workbench
    _, action, _ = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events, change))
    assert execute(client, action).json()['state'] == 'failed'
    assert events == ['edit.read']


@pytest.mark.parametrize('change', ['timeout', 'ack', 'readback'])
def test_uncertain_never_retries(workbench, monkeypatch, change):
    client, service = workbench
    _, action, _ = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events, change))
    assert execute(client, action).json()['state'] == 'unconfirmed'
    assert execute(client, action).status_code == 409
    assert events.count('edit.submit') == 1


@pytest.mark.parametrize('change', ['disabled', 'protocol', 'credential', 'takeover', 'expired'])
def test_guard_change_blocks_before_read(workbench, monkeypatch, change):
    client, service = workbench
    aid, action, _ = ready(client, service)
    if change == 'disabled':
        service.s = service.provider.s = replace(service.s, edit_enabled=False)
    elif change == 'protocol':
        service.db.execute('DELETE FROM settings WHERE key=?', ('edit-protocol:' + aid,))
    elif change == 'credential':
        service.db.execute('UPDATE accounts SET secret=? WHERE id=?', (service.vault.seal({'unb': '12345', 'changed': True}), aid))
    elif change == 'takeover':
        client.post(f'/api/accounts/{aid}/message-observation/takeover')
    else:
        service.db.execute('UPDATE actions SET expires=0 WHERE id=?', (action['id'],))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('no transport'))
    response = execute(client, action)
    assert response.status_code == 409 or response.json()['state'] in ('blocked', 'failed')


@pytest.mark.parametrize('bad', ['overlap', 'identity_path', 'unknown', 'amount', 'before', 'confirmed'])
def test_protocol_rejects_incomplete_or_ambiguous_contract(workbench, bad):
    client, service = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    if bad == 'overlap':
        p['request_paths']['title'] = ['text']
    elif bad == 'identity_path':
        p['request_paths']['title'] = ['itemId']
    elif bad == 'unknown':
        p['url'] = 'https://example.com'
    elif bad == 'amount':
        p['template']['price'] = '12.30'
    elif bad == 'before':
        del p['before']['version']
    else:
        p['complete_semantics_confirmed'] = False
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


def test_agent_no_edit_protocol_or_proposal(workbench):
    client, service = workbench
    aid, action, body = ready(client, service)
    headers = {'Authorization': 'Bearer ' + AGENT}
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol(), headers=headers).status_code == 403
    assert client.post('/api/item-edit', json=body, headers=headers).status_code == 403
    assert client.post('/api/actions', json=body, headers=headers).status_code == 403
    view = next(a for a in client.get('/api/actions', headers=headers).json() if a['id'] == action['id'])
    assert '_edit_snapshot' not in view['payload']
