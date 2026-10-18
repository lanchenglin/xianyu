"""Historical ledger fail-closed regression, isolated fictional data only."""
import sqlite3

import pytest

from tests.test_daily_publish import setup
from tests.test_workbench import workbench as workbench
from xianyu_workbench.daily_publish import DailyPublish


@pytest.mark.parametrize('state', ['failed', 'blocked', 'rejected', 'expired', 'running', 'unconfirmed', 'pending', 'approved', 'missing', 'submitted'])
def test_history_rule_matches_configuration_status_and_tick(workbench, monkeypatch, state):
    client, service = workbench
    aid, source, body = setup(client, service, monkeypatch)
    url = f'/api/accounts/{aid}/daily-publish'
    assert client.put(url, json=body).status_code == 200
    # Separate historical action; never corrupt the verified authorization source.
    with service.db.connect() as c:
        c.execute("INSERT INTO actions SELECT 'history',account_id,kind,payload,digest,mode,'history',?,created,approved_at,expires,result,error FROM actions WHERE id=?", ('submitted' if state == 'missing' else state, source['id']))
        c.execute('INSERT INTO daily_publish_dates VALUES(?,?,?,?)', (aid, '2026-10-18', 'history', 'old'))
    if state == 'missing':
        with sqlite3.connect(service.db.path) as c:
            c.execute("DELETE FROM actions WHERE id='history'")
    response = client.put(url, json=body)
    status = client.get(url).json()
    if state == 'submitted':
        assert response.status_code == 200
        assert status['effective'] is True
        assert status['blocked_reason'] is None
    else:
        assert response.status_code == 409, response.text
        assert response.json()['code'] == 'daily_unresolved'
        assert status['effective'] is False
        assert status['blocked_reason'] == 'daily_unresolved'
        assert DailyPublish(service).tick(aid)['reason'] == 'daily_unresolved'
        # Disabled configuration is permitted; it cannot clear the historical block.
        assert client.put(url, json={**body, 'enabled': False}).status_code == 200
        assert client.get(url).json()['effective'] is False
        assert len(service.db.all('SELECT * FROM daily_publish_dates')) == 1
