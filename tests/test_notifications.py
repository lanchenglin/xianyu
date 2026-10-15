import json

import pytest
from test_workbench import AGENT
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_notification_capabilities_and_schema(workbench):
    client, _ = workbench
    caps = client.get('/api/capabilities').json()
    assert caps['external_notifications'] is True
    assert caps['notification_state'] is True
    assert caps['notification_policy']['default_enabled'] is False
    assert '/api/notifications/{notification_id}/state' in client.get('/api/schema').json()['paths']


def seed(service):
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES(?,?,?)",
                       ('fixture', json.dumps({'query': 'demo', 'items': [], 'mode': 'demo'}), 1))
    return service.db.one('SELECT id FROM notifications')['id']


def test_notification_read_archive_are_local_idempotent(workbench):
    client, service = workbench
    nid = seed(service)
    headers = {'Authorization': 'Bearer ' + AGENT}
    for _ in range(2):
        response = client.post(f'/api/notifications/{nid}/state', headers=headers,
                               json={'read': True, 'archived': True})
        assert response.status_code == 200
    assert client.get('/api/notifications').json() == []
    rows = client.get('/api/notifications?include_archived=true').json()
    assert len(rows) == 1 and rows[0]['read'] == 1 and rows[0]['archived'] == 1
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0
    assert client.post(f'/api/notifications/{nid}/state', json={'read': False, 'archived': False}).status_code == 200
    assert len(client.get('/api/notifications').json()) == 1


@pytest.mark.parametrize('body,status', [({'read': True}, 422), ({'read': True, 'archived': True, 'url': 'x'}, 422),
                                       ({'read': True, 'archived': True}, 404)])
def test_notification_state_rejects_invalid_or_missing(workbench, body, status):
    client, _ = workbench
    assert client.post('/api/notifications/999/state', json=body).status_code == status
    assert client.post('/api/notifications/999/state', json=body,
                       headers={'Authorization': ''}).status_code == 401
