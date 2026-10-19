"""Generation fixtures are isolated; public algorithm is not platform verification."""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.test_daily_publish import setup
from tests.test_workbench import workbench as workbench
from xianyu_workbench.daily_publish import DailyPublish
from xianyu_workbench.provider import Problem
from xianyu_workbench.security import digest


@pytest.mark.parametrize('random_part', [0, 7, 999])
def test_generation_frozen_once_and_restart_never_regenerates(workbench, monkeypatch, random_part):
    client, service = workbench
    aid, source, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    monkeypatch.setattr('xianyu_workbench.daily_publish.time.time', lambda: at)
    draws = []
    def draw(limit):
        draws.append(limit)
        return random_part
    monkeypatch.setattr('xianyu_workbench.daily_publish.secrets.randbelow', draw)
    def interrupted(*args):
        raise RuntimeError('isolated interruption after atomic creation')
    monkeypatch.setattr(service, 'execute_one', interrupted)
    with pytest.raises(RuntimeError):
        DailyPublish(service).tick(aid)
    row = service.db.one('SELECT a.* FROM actions a JOIN daily_publish_dates d ON a.id=d.action_id')
    payload = service.vault.open(row['payload'])
    assert payload['_publish_snapshot']['executor']['template']['uniqueCode'] == str(int(at * 1000)) + str(random_part)
    service.recover()
    assert DailyPublish(service).tick(aid)['reason'] == 'daily_unresolved'
    assert DailyPublish(service).tick(aid, now=at + 86400)['reason'] == 'daily_unresolved'
    assert service.db.one('SELECT payload FROM actions WHERE id=?', (row['id'],))['payload'] == row['payload']
    assert draws == [1000]
    assert DailyPublish(service).comparison_payload(aid, row['id'], payload) == source['payload']
    for field in ('title', 'uniqueCode'):
        bad = copy.deepcopy(payload)
        if field == 'title':
            bad['title'] = 'changed'
        else:
            bad['_publish_snapshot']['executor']['template'][field] = '123'
        with pytest.raises(Problem):
            DailyPublish(service).comparison_payload(aid, row['id'], bad)


@pytest.mark.parametrize('collision_source', ['reservation', 'historical_action'])
def test_collision_no_action_no_date_no_external_write(workbench, monkeypatch, collision_source):
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    monkeypatch.setattr('xianyu_workbench.daily_publish.time.time', lambda: at)
    monkeypatch.setattr('xianyu_workbench.daily_publish.secrets.randbelow', lambda _: 7)
    code = str(int(at * 1000)) + '7'
    if collision_source == 'reservation':
        service.db.execute('INSERT INTO settings VALUES(?,?)', ('publish-code:' + digest(code), service.vault.seal({'reserved': True})))
    else:
        row = service.db.one('SELECT * FROM actions WHERE id=?', (body['source_action_id'],))
        payload = service.vault.open(row['payload'])
        payload['_publish_snapshot']['executor']['template']['uniqueCode'] = code
        service.db.execute('UPDATE actions SET payload=? WHERE id=?', (service.vault.seal(payload), row['id']))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('collision must not write'))
    assert DailyPublish(service).tick(aid)['reason'] == 'generation_collision'
    assert service.db.all('SELECT * FROM daily_publish_dates') == []


def test_old_enabled_reuse_policy_never_implicitly_authorized(workbench, monkeypatch):
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    policy = DailyPublish(service).read(aid)
    policy.pop('generation_mode')
    policy['unique_code_reuse_verified'] = True
    service.db.execute('UPDATE settings SET value=? WHERE key=?', (service.vault.seal(policy), 'daily-publish:' + aid))
    assert DailyPublish(service).tick(aid)['reason'] == 'generation_reauthorization_required'
    assert DailyPublish(service).read(aid)['enabled'] is False
    assert service.db.all('SELECT * FROM daily_publish_dates') == []
