"""Fictional text fixtures; observed web shape is not executor verification."""
import pytest

from tests.test_publish_executor import execute, ready, transport
from tests.test_publish_preview import DEFAULTS
from tests.test_workbench import approve
from tests.test_workbench import workbench as workbench


def web_action(client, service):
    aid, old = ready(client, service)
    config = {**DEFAULTS, 'text_mode': 'web_combined'}
    assert client.put(f'/api/accounts/{aid}/publish-defaults', json=config).status_code == 200
    protocol = {k: v for k, v in old['payload']['_publish_snapshot']['executor'].items() if k not in ('revision', 'binding')}
    desc = '测试商品\n虚构说明\n欢迎咨询'
    protocol['text_mode'] = 'web_combined'
    protocol['template']['itemTextDTO'] = {'title': desc, 'desc': desc, 'titleDescSeparate': False}
    assert client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol).status_code == 200
    payload = {k: v for k, v in old['payload'].items() if k != '_publish_snapshot'}
    payload['desc'] = desc
    response = client.post('/api/publish-preview', json={'account_id': aid, 'kind': 'item.publish', 'payload': payload, 'idempotency_key': 'web-combined'})
    assert response.status_code == 201, response.text
    action = response.json()
    approve(client, action)
    return aid, action


def test_web_combined_transmits_full_desc_but_reads_short_title(workbench, monkeypatch):
    client, service = workbench
    _, action = web_action(client, service)
    base = transport([])
    def call(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.submit':
            assert payload['itemTextDTO'] == {'title': action['payload']['desc'], 'desc': action['payload']['desc'], 'titleDescSeparate': False}
        if operation == 'publish.readback':
            value['data']['itemDO']['desc'] = action['payload']['desc']
        return value
    monkeypatch.setattr(service.provider, '_live', call)
    assert execute(client, action).json()['state'] == 'submitted'


@pytest.mark.parametrize('mode', ['separate', 'web_combined', 'unknown'])
def test_defaults_text_mode_is_explicit_and_closed(workbench, mode):
    client, service = workbench
    aid, _ = ready(client, service)
    response = client.put(f'/api/accounts/{aid}/publish-defaults', json={**DEFAULTS, 'text_mode': mode})
    assert response.status_code == (422 if mode == 'unknown' else 200)


def test_web_mode_daily_generation_and_mode_change_stop(workbench, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, action = web_action(client, service)
    base = transport([])
    def call(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            value['data']['itemDO']['desc'] = action['payload']['desc']
        return value
    monkeypatch.setattr(service.provider, '_live', call)
    assert execute(client, action).json()['state'] == 'submitted'
    body = {'enabled': True, 'source_action_id': action['id'], 'generation_mode': 'timestamp_random_v1',
            'confirm': '授权每日最多一条', 'evidence': 'Fictional isolated web mode evidence'}
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    def daily(account, operation, payload, **kwargs):
        value = call(account, operation, payload, **kwargs)
        if operation == 'publish.submit':
            assert payload['uniqueCode'] != 'fictional-once'
            assert payload['itemTextDTO']['title'] == action['payload']['desc']
            assert payload['itemTextDTO']['titleDescSeparate'] is False
            value['data']['itemId'] = '778'
        elif operation == 'publish.readback':
            value['data']['itemDO']['itemId'] = 778
        return value
    monkeypatch.setattr(service.provider, '_live', daily)
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    assert DailyPublish(service).tick(aid, now=at)['state'] == 'submitted'
    assert client.put(f'/api/accounts/{aid}/publish-defaults', json={**DEFAULTS, 'text_mode': 'separate'}).status_code == 200
    assert client.get(f'/api/accounts/{aid}/daily-publish').json()['effective'] is False
    assert DailyPublish(service).tick(aid, now=at + 86400)['reason'] == 'authority_changed'
    assert client.get(f'/api/accounts/{aid}/daily-publish').json()['enabled'] is False


@pytest.mark.parametrize('mutation', ['unknown_mode', 'mode_mismatch', 'request_title'])
def test_protocol_modes_never_relax_candidate_matching(workbench, mutation):
    client, service = workbench
    aid, action = web_action(client, service)
    protocol = {k: v for k, v in action['payload']['_publish_snapshot']['executor'].items() if k not in ('revision', 'binding')}
    if mutation == 'unknown_mode':
        protocol['text_mode'] = 'unknown'
    elif mutation == 'mode_mismatch':
        protocol['text_mode'] = 'separate'
    else:
        protocol['template']['itemTextDTO']['title'] = action['payload']['title']
    response = client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol)
    if mutation == 'unknown_mode':
        assert response.status_code == 422
    else:
        assert response.status_code == 200
        payload = {k: v for k, v in action['payload'].items() if k != '_publish_snapshot'}
        assert client.post('/api/publish-preview', json={'account_id': aid, 'kind': 'item.publish', 'payload': payload,
                                                      'idempotency_key': 'bad-web-mode'}).status_code == 409


def test_mode_change_blocks_old_action(workbench, monkeypatch):
    client, service = workbench
    aid, action = web_action(client, service)
    assert client.put(f'/api/accounts/{aid}/publish-defaults', json={**DEFAULTS, 'text_mode': 'separate'}).status_code == 200
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('old mode must not transmit'))
    assert execute(client, action).json()['state'] == 'failed'
