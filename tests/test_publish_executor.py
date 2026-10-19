"""Fictional protocol fixtures; transport is replaced, never a real account."""
from dataclasses import replace

import pytest

from tests.test_publish_preview import setup_preview
from tests.test_workbench import AGENT, account, approve
from tests.test_workbench import workbench as workbench


def ready(client, service):
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    service.s = service.provider.s = replace(service.s, live_enabled=True, publish_enabled=True)
    action, body = setup_preview(client, aid)
    candidate = action['payload']['_publish_snapshot']['candidate']
    protocol = {'template': {**candidate, 'imageInfoDOList': [], 'uniqueCode': 'fictional-once',
                            'quantity': '1', 'sourceId': 'pcMainPublish'},
                'success_ret': ['SUCCESS::fixture'],
                'readback_success_ret': ['SUCCESS::readback-fixture'],
                'readback_status': {'path': ['data', 'itemDO', 'fixtureStatus'], 'value_type': 'string',
                                    'allowed_values': ['FICTIONAL_LISTED', 'FICTIONAL_REVIEW']},
                'readback_content': {'title': ['data', 'itemDO', 'title'], 'desc': ['data', 'itemDO', 'desc'],
                                     'price': ['data', 'itemDO', 'soldPrice'],
                                     'transport_fee': ['data', 'itemDO', 'transportFee'],
                                     'images': ['data', 'itemDO', 'imageInfos'],
                                     'expected_price': '12.30', 'expected_transport_fee': '1.23'},
                'evidence': 'Fictional isolated fixture only',
                'upload_authorized': True}
    response = client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol)
    assert response.status_code == 200, response.text
    body['idempotency_key'] = 'executor-fixture-new'
    action = client.post('/api/publish-preview', json=body).json()
    approve(client, action)
    return aid, action


def execute(client, action, headers=None):
    return client.post(f"/api/actions/{action['id']}/execute", json={'digest': action['digest'], 'confirm': '确认执行'}, headers=headers)


def transport(events, fail=None):
    def call(account, operation, payload, **kwargs):
        events.append((operation, payload))
        if operation == fail:
            raise TimeoutError('fictional timeout')
        if operation == 'publish.upload':
            return {'url': 'https://img.alicdn.com/fictional.png', 'width': 40, 'height': 30}
        if operation == 'publish.submit':
            assert payload['itemPriceDTO'] == {'priceInCent': '1230'}
            assert payload['itemPostFeeDTO']['postPriceInCent'] == '123'
            assert len(payload['imageInfoDOList']) == 1
            return {'ret': ['SUCCESS::fixture'], 'data': {'itemId': '777'}}
        if operation == 'publish.readback':
            return {'ret': ['SUCCESS::readback-fixture'], 'data': {'itemDO': {'itemId': 777, 'fixtureStatus': 'FICTIONAL_LISTED', 'title': '测试商品', 'desc': '虚构说明', 'soldPrice': '12.30', 'transportFee': '1.23', 'imageInfos': [{}]}, 'sellerDO': {'sellerId': 12345}}}
        pytest.fail(operation)
    return call


def test_selected_publish_upload_submit_readback_once(workbench, monkeypatch):
    client, service = workbench
    aid, action = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events))
    assert service.run_once() is False
    assert execute(client, action, {'Authorization': 'Bearer ' + AGENT}).status_code == 403
    result = execute(client, action).json()
    assert result['state'] == 'submitted', result
    assert result['result']['ownership_verified'] is True
    assert [op for op, _ in events] == ['publish.upload', 'publish.submit', 'publish.readback']
    assert execute(client, action).status_code == 409
    assert len(events) == 3


@pytest.mark.parametrize('failure', ['publish.upload', 'publish.submit', 'publish.readback'])
def test_uncertain_stage_never_retries(workbench, monkeypatch, failure):
    client, service = workbench
    _, action = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events, failure))
    result = execute(client, action).json()
    assert result['state'] == 'unconfirmed', result
    assert result['result']['stage'] in ('uploading', 'submitting', 'verifying')
    assert not service.run_once()
    assert execute(client, action).status_code == 409


@pytest.mark.parametrize('change', ['disabled', 'credentials', 'defaults', 'image', 'protocol'])
def test_changes_block_before_upload(workbench, monkeypatch, change):
    client, service = workbench
    aid, action = ready(client, service)
    if change == 'disabled':
        service.s = service.provider.s = replace(service.s, publish_enabled=False)
    elif change == 'credentials':
        service.db.execute('UPDATE accounts SET secret=? WHERE id=?', (service.vault.seal({'unb': '12345', '_m_h5_tk': 'changed'}), aid))
    elif change == 'defaults':
        service.db.execute('DELETE FROM settings WHERE key=?', ('publish-defaults:' + aid,))
    elif change == 'protocol':
        service.db.execute('DELETE FROM settings WHERE key=?', ('publish-protocol:' + aid,))
    else:
        asset = service.db.one('SELECT * FROM assets WHERE account_id=?', (aid,))
        (service.s.data_dir / 'assets' / asset['filename']).write_bytes(b'changed')
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('must not upload'))
    assert execute(client, action).json()['state'] == 'failed'


@pytest.mark.parametrize('bad', ['ack', 'owner', 'id', 'read_ret'])
def test_bad_response_remains_unknown(workbench, monkeypatch, bad):
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    def response(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if bad == 'ack' and operation == 'publish.submit':
            value['ret'] = ['NOT_SUCCESS::fixture']
        if operation == 'publish.readback':
            if bad == 'owner':
                value['data']['sellerDO']['sellerId'] = '999'
            elif bad == 'id':
                value['data']['itemDO']['itemId'] = '888'
            elif bad == 'read_ret':
                value['ret'] = ['FAIL::fixture']
        return value
    monkeypatch.setattr(service.provider, '_live', response)
    assert execute(client, action).json()['state'] == 'unconfirmed'


def test_upload_receipt_persisted_before_submit(workbench, monkeypatch):
    client, service = workbench
    aid, action = ready(client, service)
    base = transport([])
    def response(account, operation, payload, **kwargs):
        if operation == 'publish.submit':
            row = service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))
            saved = service.vault.open(row['result'])
            assert saved['uploads'][0]['asset_id'] == action['payload']['images'][0]
            assert saved['uploads'][0]['url'] == 'https://img.alicdn.com/fictional.png'
            assert len(saved['uploads'][0]['sha256']) == 64
            raise TimeoutError()
        return base(account, operation, payload, **kwargs)
    monkeypatch.setattr(service.provider, '_live', response)
    result = execute(client, action).json()
    assert result['result']['stage'] == 'submitting'
    assert result['result']['uploads'][0]['width'] == 40
    agent = client.get(f"/api/actions/{action['id']}", headers={'Authorization': 'Bearer ' + AGENT})
    assert 'https://img.alicdn.com' not in agent.text


def test_concurrent_selected_execution_claims_only_once(workbench, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from xianyu_workbench.provider import Problem
    client, service = workbench
    _, action = ready(client, service)
    started, release = threading.Event(), threading.Event()
    events = []
    base = transport(events)
    def delayed(account, operation, payload, **kwargs):
        if operation == 'publish.upload':
            started.set()
            assert release.wait(10)
        return base(account, operation, payload, **kwargs)
    monkeypatch.setattr(service.provider, '_live', delayed)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute_one, action['id'], action['digest'])
        assert started.wait(10)
        try:
            with pytest.raises(Problem):
                service.execute_one(action['id'], action['digest'])
        finally:
            release.set()
        assert future.result()['state'] == 'submitted'
    assert len(events) == 3


def test_change_after_upload_stops_submit_and_stays_unknown(workbench, monkeypatch):
    client, service = workbench
    aid, action = ready(client, service)
    events = []
    base = transport(events)
    def changed(account, operation, payload, **kwargs):
        result = base(account, operation, payload, **kwargs)
        service.db.execute('UPDATE accounts SET paused=1 WHERE id=?', (aid,))
        return result
    monkeypatch.setattr(service.provider, '_live', changed)
    assert execute(client, action).json()['state'] == 'unconfirmed'
    assert [op for op, _ in events] == ['publish.upload']


def test_identity_change_during_readback_cannot_confirm(workbench, monkeypatch):
    client, service = workbench
    aid, action = ready(client, service)
    base = transport([])
    def changed(account, operation, payload, **kwargs):
        result = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            service.db.execute("UPDATE accounts SET uid='999' WHERE id=?", (aid,))
        return result
    monkeypatch.setattr(service.provider, '_live', changed)
    assert execute(client, action).json()['state'] == 'unconfirmed'


def test_public_provider_and_private_transport_deny_unselected(workbench, monkeypatch):
    from xianyu_workbench.provider import Problem
    client, service = workbench
    aid, _ = ready(client, service)
    for operation in ('publish.upload', 'publish.submit', 'publish.readback', 'item.publish'):
        with pytest.raises(Problem):
            service.provider.call(aid, operation, {}, write=True)
    for operation in ('publish.upload', 'publish.submit', 'publish.readback'):
        with pytest.raises(Problem) as error:
            service.provider._live(service.provider.account(aid), operation, {}, write=True)
        assert error.value.code == 'publish_authorization_required'


def test_restart_preserves_stage_and_prevents_replay(workbench):
    client, service = workbench
    _, action = ready(client, service)
    saved = {'stage': 'submitting', 'uploaded_count': 1, 'ownership_verified': False}
    service.db.execute("UPDATE actions SET state='running',result=? WHERE id=?", (service.vault.seal(saved), action['id']))
    service.recover()
    restored = client.get(f"/api/actions/{action['id']}").json()
    assert restored['state'] == 'unconfirmed'
    assert restored['result'] == {**saved, 'failure': {'code': 'unknown_historical', 'stage': 'submitting'}}
    assert service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result']) == saved
    assert execute(client, action).status_code == 409
    assert service.run_once() is False


def test_real_provider_subprocess_boundary_without_network(workbench, monkeypatch):
    import json
    from pathlib import Path
    client, service = workbench
    _, action = ready(client, service)
    events, paths = [], []
    base = transport(events)
    class Process:
        returncode = 0
        def communicate(self, text, timeout):
            request = json.loads(text)
            data = base(None, request['operation'], request['payload'])
            return json.dumps({'ok': True, 'data': data}), ''
    def popen(command, **kwargs):
        env = kwargs['env']
        assert env['XY_PUBLISH_ENABLED'] == 'true'
        assert env['XY_MESSAGE_SEND_ENABLED'] == 'false'
        assert env['GOOFISH_NO_CHROME_BOOTSTRAP'] == '1'
        path = Path(env['GOOFISH_COOKIES_PATH'])
        assert json.loads(path.read_text())['unb'] == '12345'
        paths.append(path)
        return Process()
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', popen)
    result = execute(client, action).json()
    assert result['state'] == 'submitted', result
    assert len(events) == 3 and all(not path.exists() for path in paths)


def test_protocol_private_admin_only(workbench):
    client, service = workbench
    aid, action = ready(client, service)
    headers = {'Authorization': 'Bearer ' + AGENT}
    assert client.put(f'/api/accounts/{aid}/publish-protocol', json={}, headers=headers).status_code == 403
    response = client.get(f"/api/actions/{action['id']}", headers=headers)
    assert 'fictional-once' not in response.text
    assert 'credential_digest' not in response.text
