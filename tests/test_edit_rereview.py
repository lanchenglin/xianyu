import json

import pytest

from tests.test_item_edit import execute, protocol, ready, transport
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import canonical


def test_unknown_blocks_protocol_and_proposal_without_mutation(workbench, monkeypatch):
    client, service = workbench
    aid, action, body = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([], 'timeout'))
    assert execute(client, action).json()['state'] == 'unconfirmed'
    old = service.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + aid,))
    count = service.db.one('SELECT COUNT(*) n FROM actions')['n']
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 409
    body['idempotency_key'] = 'unknown-new-key'
    assert client.post('/api/item-edit', json=body).status_code == 409
    assert service.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + aid,)) == old
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == count


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-Infinity', '1e999', 'duplicate', 'nested_duplicate'])
def test_raw_json_rejected_without_persistence(workbench, bad):
    client, service = workbench
    aid, _, _ = ready(client, service)
    p = protocol()
    raw = json.dumps(p)
    if bad == 'duplicate':
        raw = '{"evidence":"secret-do-not-echo",' + raw[1:]
    elif bad == 'nested_duplicate':
        raw = raw.replace('"shipping": "fixed"', '"shipping":"secret-do-not-echo","shipping":"fixed"')
    else:
        raw = raw.replace('"sku": null', '"sku": ' + bad)
    old = service.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + aid,))
    response = client.put(f'/api/accounts/{aid}/edit-protocol', content=raw, headers={'Content-Type': 'application/json'})
    assert response.status_code in (400, 422), response.text
    assert 'secret-do-not-echo' not in response.text
    assert service.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + aid,)) == old


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_canonical_refuses_nonfinite(value):
    with pytest.raises(ValueError):
        canonical({'nested': [value]})


def test_running_blocks_concurrent_save_and_proposal(workbench, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    client, service = workbench
    aid, action, body = ready(client, service)
    entered, release = Event(), Event()
    def call(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        raise TimeoutError()
    monkeypatch.setattr(service.provider, '_live', call)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute_one, action['id'], action['digest'])
        assert entered.wait(10)
        try:
            assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 409
            body['idempotency_key'] = 'racing-new-proposal'
            assert client.post('/api/item-edit', json=body).status_code == 409
        finally:
            release.set()
        assert future.result()['state'] == 'failed'
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 200


def test_unknown_guards_run_in_write_transaction_and_scope(workbench, monkeypatch):
    from xianyu_workbench import item_edit
    client, service = workbench
    aid, action, body = ready(client, service)
    original = item_edit.unknown_guard
    calls = []
    def checked(service, connection, account_id, item_id):
        assert connection.in_transaction
        calls.append((account_id, item_id))
        return original(service, connection, account_id, item_id)
    monkeypatch.setattr(item_edit, 'unknown_guard', checked)
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 200
    body['idempotency_key'] = 'transaction-check'
    assert client.post('/api/item-edit', json=body).status_code == 201
    assert calls == [(aid, '777'), (aid, '777')]
    service.db.execute("UPDATE actions SET state='unconfirmed' WHERE id=?", (action['id'],))
    p = protocol()
    p['item_id'] = p['before']['item_id'] = p['template']['itemId'] = p['original_request']['itemId'] = '778'
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    body['payload']['item_id'] = '778'
    body['idempotency_key'] = 'different-item-not-blocked'
    assert client.post('/api/item-edit', json=body).status_code == 201
    from tests.test_workbench import account
    other = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_2"}')
    assert client.put(f'/api/accounts/{other}/edit-protocol', json=protocol()).status_code == 200


def test_proposal_rechecks_unknown_inside_insert_transaction(workbench, monkeypatch):
    from xianyu_workbench import item_edit
    client, service = workbench
    _, action, body = ready(client, service)
    original = item_edit.prepare
    def raced(*args):
        value = original(*args)
        service.db.execute("UPDATE actions SET state='unconfirmed' WHERE id=?", (action['id'],))
        return value
    monkeypatch.setattr(item_edit, 'prepare', raced)
    body['idempotency_key'] = 'raced-after-prepare'
    assert client.post('/api/item-edit', json=body).status_code == 409
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 1


@pytest.mark.parametrize('path', ['/api/accounts', '/api/actions', '/api/drafts', '/api/publish-preview'])
def test_sibling_raw_json_entrypoints_reject_duplicates(workbench, path):
    client, _ = workbench
    r = client.post(path, content='{"secret":"do-not-echo","secret":NaN}', headers={'Content-Type': 'application/json'})
    assert r.status_code == 400
    assert 'do-not-echo' not in r.text


def test_chunked_json_size_bound_and_get_unchanged(workbench):
    client, _ = workbench
    assert client.get('/healthz').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    r = client.post('/api/accounts', content=iter([b' ' * (1024 * 1024)] * 13), headers={'Content-Type': 'application/json'})
    assert r.status_code == 413


def test_nested_cookie_json_duplicate_rejected(workbench):
    client, _ = workbench
    response = client.post('/api/accounts', json={'label': 'fixture', 'mode': 'live',
        'cookies_json': '{"unb":"54321","unb":"12345","_m_h5_tk":"fictional_1"}'})
    assert response.status_code == 422
