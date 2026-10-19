"""Only fictional accounts and stubbed transport; never platform evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.test_publish_executor import execute, ready, transport
from tests.test_workbench import AGENT
from tests.test_workbench import workbench as workbench


def setup(client, service, monkeypatch):
    aid, action = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([]))
    assert execute(client, action).json()['state'] == 'submitted'
    body = {'enabled': True, 'source_action_id': action['id'], 'time': '09:00',
            'evidence': 'Fictional administrator attestation for isolated testing only',
            'confirm': '授权每日最多一条', 'generation_mode': 'timestamp_random_v1'}
    return aid, action, body


def test_daily_ui_and_cli_entrypoints(workbench):
    import sys
    from subprocess import run
    client, _ = workbench
    assert 'daily-publish-form' in client.get('/').text
    assert 'daily-publish/tick' in client.get('/static/app.js').text
    result = run([sys.executable, '-m', 'xianyu_workbench.cli', 'daily-publish', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert '--account-id' in result.stdout


def test_daily_requires_admin_and_verified_source(workbench):
    client, service = workbench
    aid, action = ready(client, service)
    url = f'/api/accounts/{aid}/daily-publish'
    body = {'enabled': True, 'source_action_id': action['id'], 'evidence': 'fictional evidence only',
            'confirm': '授权每日最多一条'}
    assert client.put(url, json=body, headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert client.put(url, json=body).status_code == 409


@pytest.mark.parametrize('operation', ['pause', 'message-observation/takeover'])
def test_stop_revokes_even_if_later_released(workbench, monkeypatch, operation):
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    url = f'/api/accounts/{aid}/daily-publish'
    assert client.put(url, json=body).status_code == 200
    assert client.post(f'/api/accounts/{aid}/{operation}').status_code == 200
    assert client.get(url).json()['enabled'] is False


def test_concurrent_ticks_create_one_new_action(workbench, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    base = transport([])
    def new_item(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.submit':
            value['data']['itemId'] = '778'
        elif operation == 'publish.readback':
            value['data']['itemDO']['itemId'] = 778
        return value
    monkeypatch.setattr(service.provider, '_live', new_item)
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda _: DailyPublish(service).tick(aid, now=at), range(4)))
    assert sum(r.get('state') == 'submitted' for r in results) == 1
    assert len(service.db.all('SELECT * FROM daily_publish_dates')) == 1


def test_daily_same_item_id_is_not_new_publish(workbench, monkeypatch):
    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    assert DailyPublish(service).tick(aid, now=at)['state'] == 'unconfirmed'


def test_revocation_during_upload_stops_submit(workbench, monkeypatch):
    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    events = []
    base = transport(events)
    def revoke(account, operation, payload, **kwargs):
        result = base(account, operation, payload, **kwargs)
        DailyPublish(service).revoke(aid)
        return result
    monkeypatch.setattr(service.provider, '_live', revoke)
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    assert DailyPublish(service).tick(aid, now=at)['state'] == 'unconfirmed'
    assert [op for op, _ in events] == ['publish.upload']


def test_daily_requires_explicit_repeated_template_evidence(workbench, monkeypatch):
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    body['generation_mode'] = 'disabled'
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 409


def test_daily_exact_minute_and_permanent_date_dedupe(workbench, monkeypatch):
    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, action, body = setup(client, service, monkeypatch)
    url = f'/api/accounts/{aid}/daily-publish'
    assert client.put(url, json=body).status_code == 200
    policy = DailyPublish(service)
    at = datetime(2026, 10, 20, 9, 0, 10, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    assert policy.tick(aid, now=at - 60)['reason'] == 'outside_minute'
    base = transport([])
    def new_item(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.submit':
            value['data']['itemId'] = '778'
        elif operation == 'publish.readback':
            value['data']['itemDO']['itemId'] = 778
        return value
    monkeypatch.setattr(service.provider, '_live', new_item)
    result = policy.tick(aid, now=at)
    assert result['state'] == 'submitted', result
    assert result['action_id'] != action['id']
    frozen = service.vault.open(service.db.one('SELECT payload FROM actions WHERE id=?', (result['action_id'],))['payload'])
    assert frozen['_publish_snapshot']['executor']['template']['uniqueCode'] != 'fictional-once'
    sent = frozen['_publish_snapshot']['executor']['template']['uniqueCode']
    assert sent.isdigit()
    frozen['_publish_snapshot']['executor']['template']['uniqueCode'] = 'fictional-once'
    assert frozen == action['payload']
    assert policy.tick(aid, now=at)['reason'] == 'date_used'
    assert client.post(url + '/revoke').status_code == 200
    assert client.put(url, json=body).status_code == 200
    assert policy.tick(aid, now=at)['reason'] == 'date_used'
    assert policy.tick(aid, now=at + 60)['reason'] == 'outside_minute'


@pytest.mark.parametrize('change', ['unknown', 'takeover', 'paused', 'protocol'])
def test_daily_stops_on_unknown_or_changed_authority(workbench, monkeypatch, change):
    from xianyu_workbench.daily_publish import DailyPublish
    client, service = workbench
    aid, action, body = setup(client, service, monkeypatch)
    url = f'/api/accounts/{aid}/daily-publish'
    assert client.put(url, json=body).status_code == 200
    if change == 'unknown':
        monkeypatch.setattr(service.provider, '_live', transport([], 'publish.submit'))
    elif change == 'paused':
        service.db.execute('UPDATE accounts SET paused=1 WHERE id=?', (aid,))
    elif change == 'takeover':
        service.db.execute('INSERT OR REPLACE INTO message_observation(account_id,takeover) VALUES(?,1)', (aid,))
    else:
        service.db.execute('DELETE FROM settings WHERE key=?', ('publish-protocol:' + aid,))
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    policy = DailyPublish(service)
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    result = policy.tick(aid, now=at)
    assert result.get('state') != 'submitted'
    assert policy.tick(aid, now=at + 86400).get('state') != 'submitted'
