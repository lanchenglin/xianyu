"""Review regressions: all statuses and response contracts are fictional."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from tests.test_publish_executor import execute, ready, transport
from tests.test_workbench import ADMIN
from tests.test_workbench import workbench as workbench
from xianyu_workbench.app import create_app


@pytest.mark.parametrize('bad', ['different_ret', 'missing', 'unknown', 'wrong_type', 'bool_type'])
def test_readback_requires_exact_contract_and_typed_status(workbench, monkeypatch, bad):
    client, service = workbench
    _, action = ready(client, service)
    events = []
    base = transport(events)
    def response(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            if bad == 'different_ret':
                value['ret'] = ['SUCCESS::different-contract']
            elif bad == 'missing':
                value['data']['itemDO'].pop('fixtureStatus', None)
            else:
                value['data']['itemDO']['fixtureStatus'] = {'unknown': 'FICTIONAL_UNKNOWN', 'wrong_type': 1, 'bool_type': True}[bad]
        return value
    monkeypatch.setattr(service.provider, '_live', response)
    result = execute(client, action).json()
    assert result['state'] == 'unconfirmed', result
    assert result['result']['stage'] == 'verifying'
    assert result['result'].get('status_verified') is not True
    assert execute(client, action).status_code == 409
    assert service.run_once() is False
    assert len(events) == 3


@pytest.mark.parametrize('field', ['readback_success_ret', 'readback_status'])
def test_legacy_protocol_missing_contract_stops_before_upload(workbench, monkeypatch, field):
    client, service = workbench
    aid, action = ready(client, service)
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('publish-protocol:' + aid,))
    protocol = service.vault.open(row['value'])
    protocol.pop(field)
    service.db.execute('UPDATE settings SET value=? WHERE key=?',
                       (service.vault.seal(protocol), 'publish-protocol:' + aid))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('must not upload'))
    assert execute(client, action).json()['state'] == 'failed'


@pytest.mark.parametrize('field', ['ret', 'path', 'type', 'values'])
def test_contract_change_requires_new_approval(workbench, monkeypatch, field):
    client, service = workbench
    aid, action = ready(client, service)
    frozen = action['payload']['_publish_snapshot']['executor']
    protocol = {k: v for k, v in frozen.items() if k not in ('revision', 'binding')}
    if field == 'ret':
        protocol['readback_success_ret'] = ['SUCCESS::changed']
    elif field == 'path':
        protocol['readback_status']['path'] = ['data', 'other']
    elif field == 'type':
        protocol['readback_status'].update(value_type='integer', allowed_values=[1])
    else:
        protocol['readback_status']['allowed_values'] = ['FICTIONAL_OTHER']
    assert client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol).status_code == 200
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('must not upload'))
    assert execute(client, action).json()['state'] == 'failed'


@pytest.mark.parametrize('status', ['FICTIONAL_LISTED', 'FICTIONAL_REVIEW'])
def test_only_explicit_allowed_status_can_verify(workbench, monkeypatch, status):
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    def response(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            value['data']['itemDO']['fixtureStatus'] = status
        return value
    monkeypatch.setattr(service.provider, '_live', response)
    result = execute(client, action).json()
    assert result['state'] == 'submitted'
    assert result['result']['status_verified'] is True


@pytest.mark.parametrize('observed,verified', [(7, True), ('7', False), (True, False), (7.0, False), (8, False)])
def test_integer_state_is_not_coerced(workbench, monkeypatch, observed, verified):
    from tests.test_workbench import approve
    client, service = workbench
    aid, previous = ready(client, service)
    protocol = {k: v for k, v in previous['payload']['_publish_snapshot']['executor'].items()
                if k not in ('revision', 'binding')}
    protocol['readback_status'].update(value_type='integer', allowed_values=[7])
    assert client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol).status_code == 200
    payload = {k: v for k, v in previous['payload'].items() if k != '_publish_snapshot'}
    action = client.post('/api/publish-preview', json={'account_id': aid, 'kind': 'item.publish',
        'payload': payload, 'idempotency_key': 'integer-status-fixture'}).json()
    approve(client, action)
    base = transport([])
    def response(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            value['data']['itemDO']['fixtureStatus'] = observed
        return value
    monkeypatch.setattr(service.provider, '_live', response)
    result = execute(client, action).json()
    assert result['state'] == ('submitted' if verified else 'unconfirmed')
    assert (result['result'].get('status_verified') is True) is verified


@pytest.mark.parametrize('live,publish', [(False, False), (False, True), (True, False), (True, True)])
def test_capabilities_match_runtime_gates(workbench, tmp_path, live, publish):
    _, service = workbench
    settings = replace(service.s, data_dir=tmp_path / 'separate', live_enabled=live, publish_enabled=publish)
    with TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + ADMIN}) as client:
        caps = client.get('/api/capabilities').json()
    assert caps['live_publish'] is (live and publish)
    assert caps['publish_policy']['live_executor_enabled'] is (live and publish)
    assert caps['publish_policy']['executor_implemented'] is True
    assert caps['publish_policy']['platform_verified'] is False
