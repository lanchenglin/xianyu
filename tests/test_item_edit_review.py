"""Independent review regressions, fictional evidence only."""
from copy import deepcopy

import pytest

from tests.test_item_edit import execute, protocol, ready, transport
from tests.test_workbench import account, approve
from tests.test_workbench import workbench as workbench


@pytest.mark.parametrize('extra', [{'status': 'OFFLINE'}, {'unknown': 'command'},
                                   {'nested': {'sku': [{'stock': 0}]}}, {'images': []}])
def test_review_unmapped_template_rejected(workbench, extra):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    p['template'].update(extra)
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


@pytest.mark.parametrize('bad', ['status', 'unknown', 'array', 'nested', 'unmapped', 'overlap', 'identity', 'type', 'evidence', 'metadata'])
def test_review_original_copy_does_not_prove_invariants(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    if bad == 'status':
        p['template']['status'] = 'OFFLINE'
    elif bad in ('unknown', 'metadata'):
        p['template'][bad] = 'arbitrary'
    elif bad == 'array':
        p['template']['images'].append({'nested': {'id': 'other'}})
    elif bad == 'nested':
        p['template']['fixed']['shipping'] = {'unsafe': True}
    elif bad == 'unmapped':
        p['invariant_mappings'].pop()
    elif bad == 'overlap':
        p['invariant_mappings'].append({'request_path': ['text'], 'before_path': ['invariants'], 'evidence': 'fictional mapping only'})
    elif bad == 'identity':
        p['template']['itemId'] = '778'
    elif bad == 'type':
        p['template']['sku'] = False
    else:
        p['invariant_mappings'][0]['evidence'] = ''
    p['original_request'] = deepcopy(p['template'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


def next_protocol():
    p = protocol()
    p['before'].update(title='new', desc='new body\nexact', price='13.20', version='v2')
    p['template']['text'] = {'title': 'new', 'desc': 'new body\nexact'}
    p['template']['price'] = '1320'
    if 'original_request' in p:
        p['original_request'] = deepcopy(p['template'])
    return p


def test_review_verified_allows_fresh_version_second_edit(workbench, monkeypatch):
    client, service = workbench
    aid, first, body = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([]))
    assert execute(client, first).json()['state'] == 'submitted'
    p = next_protocol()
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    body['idempotency_key'] = 'second-approved-price'
    body['payload']['price'] = '14.20'
    r = client.post('/api/item-edit', json=body)
    assert r.status_code == 201, r.text
    second = r.json()
    approve(client, second)
    calls = []
    def call(account, operation, payload, **kwargs):
        calls.append(operation)
        if operation == 'edit.submit':
            assert payload['template']['price'] == '1420'
            return {'ret': p['success_ret'], 'data': {'itemId': '777'}}
        value = deepcopy(p['before'])
        if 'edit.submit' in calls:
            value.update(price='14.20', version='v3')
        return {'ret': p['read_success_ret'], 'data': {'snapshot': value}}
    monkeypatch.setattr(service.provider, '_live', call)
    result = execute(client, second).json()
    assert result['state'] == 'submitted', result
    assert calls == ['edit.read', 'edit.submit', 'edit.read']
    from tests.test_workbench import AGENT
    views = client.get('/api/actions', headers={'Authorization': 'Bearer ' + AGENT}).json()
    assert all('after' not in (v['result'] or {}) for v in views)


@pytest.mark.parametrize('outcome', ['verified', 'timeout', 'ack', 'readback'])
def test_review_new_key_old_before_never_replays(workbench, monkeypatch, outcome):
    client, service = workbench
    aid, first, body = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([], None if outcome == 'verified' else outcome))
    execute(client, first)
    response = client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol())
    if outcome != 'verified':
        assert response.status_code == 409
        body['idempotency_key'] = 'new-key-unknown'
        assert client.post('/api/item-edit', json=body).status_code == 409
        return
    assert response.status_code == 200
    body['idempotency_key'] = 'new-key-old-before'
    second = client.post('/api/item-edit', json=body).json()
    approve(client, second)
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('history must block before read'))
    assert execute(client, second).json()['state'] == 'failed'


def test_review_legacy_contract_rejected_before_transport(workbench, monkeypatch):
    client, service = workbench
    aid, first, _ = ready(client, service)
    p = protocol()
    p['schema_version'] = 1
    service.db.execute('UPDATE settings SET value=? WHERE key=?', (service.vault.seal(p), 'edit-protocol:' + aid))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('no transport'))
    assert execute(client, first).json()['state'] == 'failed'


def test_review_prewrite_failure_allows_fresh_approval(workbench, monkeypatch):
    client, service = workbench
    _, first, body = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([], 'status'))
    assert execute(client, first).json()['state'] == 'failed'
    body['idempotency_key'] = 'fresh-after-no-write'
    second = client.post('/api/item-edit', json=body).json()
    approve(client, second)
    monkeypatch.setattr(service.provider, '_live', transport([]))
    assert execute(client, second).json()['state'] == 'submitted'


def test_review_concurrent_same_version_single_write(workbench, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    client, service = workbench
    _, first, body = ready(client, service)
    body['idempotency_key'] = 'concurrent-second-approval'
    second = client.post('/api/item-edit', json=body).json()
    approve(client, second)
    entered, release = Event(), Event()
    events = []
    base = transport(events)
    def call(account, operation, payload, **kwargs):
        if operation == 'edit.submit':
            entered.set()
            assert release.wait(10)
        return base(account, operation, payload, **kwargs)
    monkeypatch.setattr(service.provider, '_live', call)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute_one, first['id'], first['digest'])
        assert entered.wait(10)
        try:
            assert service.execute_one(second['id'], second['digest'])['state'] == 'approved'
        finally:
            release.set()
        assert future.result()['state'] == 'submitted'
    assert service.execute_one(second['id'], second['digest'])['state'] == 'failed'
    assert events.count('edit.submit') == 1
