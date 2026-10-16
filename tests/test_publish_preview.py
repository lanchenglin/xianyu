"""Local fictional publish evidence; no platform calls."""
from dataclasses import replace

import pytest

from tests.test_workbench import AGENT, account, approve, upload
from tests.test_workbench import workbench as workbench

DEFAULTS = {'category': {'cat_id': '1', 'cat_name': '测试类目', 'channel_cat_id': '2', 'tb_cat_id': '3'},
            'location': {'divisionId': '123', 'prov': '测试省', 'city': '测试市', 'area': '测试区',
                         'gps': '120.1,30.2', 'poiId': 'private-poi', 'poiName': '私密地点'},
            'region_summary': '测试市'}


def setup_preview(client, aid, key='publish-preview-001'):
    response = client.put(f'/api/accounts/{aid}/publish-defaults', json=DEFAULTS)
    assert response.status_code == 200, response.text
    payload = {'title': '测试商品', 'desc': '虚构说明', 'price': '12.30', 'images': [upload(client, aid)],
               'delivery': '一口价', 'post_price': '1.23', 'can_self_pickup': False}
    body = {'account_id': aid, 'kind': 'item.publish', 'payload': payload, 'idempotency_key': key}
    response = client.post('/api/publish-preview', json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def test_preview_ui_and_capability(workbench):
    client, _ = workbench
    assert 'publish-preview' in client.get('/static/app.js').text
    assert 'publish-defaults-form' in client.get('/').text
    assert client.get('/api/capabilities').json()['local_publish_preview'] is True


def test_local_preview_frozen_and_private(workbench):
    client, service = workbench
    aid = account(client)
    action, body = setup_preview(client, aid)
    snapshot = action['payload']['_publish_snapshot']
    assert snapshot['category'] == DEFAULTS['category']
    assert snapshot['location'] == DEFAULTS['location']
    assert len(snapshot['images'][0]['sha256']) == 64
    assert snapshot['candidate']['itemPriceDTO']['priceInCent'] == '1230'
    assert snapshot['candidate']['itemPostFeeDTO']['postPriceInCent'] == '123'
    assert action['state'] == 'pending'
    assert client.post('/api/publish-preview', json=body).json()['id'] == action['id']
    agent = client.get(f"/api/actions/{action['id']}", headers={'Authorization': 'Bearer ' + AGENT})
    assert 'private-poi' not in agent.text and '120.1' not in agent.text
    assert '测试市' in agent.text
    assert b'private-poi' not in service.db.path.read_bytes()
    approve(client, action)
    result = client.post(f"/api/actions/{action['id']}/execute", json={'digest': action['digest'], 'confirm': '确认执行'}).json()
    assert result['state'] == 'simulated'
    assert result['result']['demo'] is True


@pytest.mark.parametrize('change', ['summary', 'category', 'location', 'restore'])
def test_defaults_changes_require_new_approval(workbench, change):
    client, _ = workbench
    aid = account(client)
    action, _ = setup_preview(client, aid)
    approve(client, action)
    changed = {**DEFAULTS, 'region_summary': '另一地区'}
    if change == 'category':
        changed = {**DEFAULTS, 'category': {**DEFAULTS['category'], 'cat_id': '9'}}
    elif change == 'location':
        changed = {**DEFAULTS, 'location': {**DEFAULTS['location'], 'poiId': 'new-private-poi'}}
    assert client.put(f'/api/accounts/{aid}/publish-defaults', json=changed).status_code == 200
    if change == 'restore':
        assert client.put(f'/api/accounts/{aid}/publish-defaults', json=DEFAULTS).status_code == 200
    result = client.post(f"/api/actions/{action['id']}/execute", json={'digest': action['digest'], 'confirm': '确认执行'}).json()
    assert result['state'] == 'failed'
    assert '重新' in result['error']


def test_publish_defaults_admin_only(workbench):
    client, _ = workbench
    aid = account(client)
    headers = {'Authorization': 'Bearer ' + AGENT}
    for method in (client.get, client.put):
        kwargs = {'json': DEFAULTS} if method == client.put else {}
        assert method(f'/api/accounts/{aid}/publish-defaults', headers=headers, **kwargs).status_code == 403


@pytest.mark.parametrize('kind', ['item.publish', 'item.delete'])
def test_worker_never_claims_live_goods(workbench, kind):
    client, service = workbench
    aid = account(client)
    if kind == 'item.publish':
        action, _ = setup_preview(client, aid)
    else:
        action = client.post('/api/actions', json={'account_id': aid, 'kind': kind,
            'payload': {'item_id': '123', 'acknowledgement': '我理解这可能永久删除商品，不是普通下架'},
            'idempotency_key': 'delete-historical'}).json()
    approve(client, action)
    service.db.execute("UPDATE accounts SET mode='live' WHERE id=?", (aid,))
    assert service.run_once() is False
    assert client.get(f"/api/actions/{action['id']}").json()['state'] == 'approved'


@pytest.mark.parametrize('change', ['image', 'uid', 'payload', 'mode'])
def test_frozen_preview_tampering_stops(workbench, change):
    client, service = workbench
    aid = account(client)
    action, _ = setup_preview(client, aid)
    approve(client, action)
    if change == 'image':
        row = service.db.one('SELECT * FROM assets WHERE account_id=?', (aid,))
        (service.s.data_dir / 'assets' / row['filename']).write_bytes(b'changed')
    elif change == 'uid':
        service.db.execute("UPDATE accounts SET uid='88888' WHERE id=?", (aid,))
    elif change == 'mode':
        service.db.execute("UPDATE accounts SET mode='live' WHERE id=?", (aid,))
    else:
        payload = action['payload']
        payload['price'] = '99.99'
        service.db.execute('UPDATE actions SET payload=? WHERE id=?', (service.vault.seal(payload), action['id']))
    result = client.post(f"/api/actions/{action['id']}/execute", json={'digest': action['digest'], 'confirm': '确认执行'}).json()
    assert result['state'] == 'failed' and result['result'] is None


def test_cross_account_and_forged_snapshot_rejected(workbench):
    client, _ = workbench
    aid = account(client)
    action, body = setup_preview(client, aid)
    other = account(client)
    body['account_id'] = other
    assert client.post('/api/publish-preview', json=body).status_code == 409
    body['account_id'] = aid
    body['payload']['_publish_snapshot'] = action['payload']['_publish_snapshot']
    assert client.post('/api/publish-preview', json=body).status_code == 422


def test_live_delete_cannot_bypass_selected_queue(workbench, monkeypatch):
    from xianyu_workbench.provider import Problem
    client, service = workbench
    aid = account(client, 'live')
    service.provider.s = replace(service.s, live_enabled=True)
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('must not write'))
    with pytest.raises(Problem) as error:
        service.provider.call(aid, 'item.delete', {'item_id': '123'}, write=True)
    assert error.value.code == 'goods_executor_disabled'


def test_live_preview_is_local_and_execution_blocked(workbench, monkeypatch):
    client, service = workbench
    aid = account(client, 'live')
    def forbidden(*args, **kwargs):
        pytest.fail('local preview must not reach transport')
    monkeypatch.setattr(service.provider, '_live', forbidden)
    action, _ = setup_preview(client, aid)
    service.s = replace(service.s, live_enabled=True)
    approve(client, action)
    result = client.post(f"/api/actions/{action['id']}/execute", json={'digest': action['digest'], 'confirm': '确认执行'}).json()
    assert result['state'] == 'failed'
    assert result['result'] is None
    assert '证据' in result['error']
