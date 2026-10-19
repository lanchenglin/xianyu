# ruff: noqa: F811
import time

import pytest
from test_workbench import AGENT, account, workbench  # noqa: F401

from xianyu_workbench.provider import Problem


def test_observation_defaults_and_admin_configuration(workbench):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/message-observation'
    result = client.get(path)
    assert result.status_code == 200
    assert result.json()['enabled'] is False
    assert result.json()['coverage'] == 'conversation_last_message_samples'
    assert result.json()['send_allowed'] is False
    agent = {'Authorization': 'Bearer ' + AGENT}
    assert client.put(path, headers=agent, json={'enabled': True, 'interval_s': 300}).status_code == 403
    assert client.put(path, json={'enabled': True, 'interval_s': 299}).status_code == 422
    assert client.put(path, json={'enabled': True, 'interval_s': 300}).status_code == 200
    assert client.get(path, headers=agent).json()['enabled'] is True
    assert service.db.one('SELECT * FROM message_observation WHERE account_id=?', (ident,))['enabled'] == 1


def test_scheduler_due_persistent_dedup_and_no_send(workbench):
    client, service = workbench
    ident = account(client)
    assert service.observation.run_once() is False
    path = f'/api/accounts/{ident}/message-observation'
    client.put(path, json={'enabled': True, 'interval_s': 300})
    assert service.observation.run_once() is False
    for _ in range(2):
        service.db.execute('UPDATE message_observation SET next_run=0')
        assert service.observation.run_once() is True
    assert len(service.db.all("SELECT * FROM operation_records WHERE kind='messages'")) == 1
    assert len(service.db.all('SELECT * FROM operation_syncs')) == 2
    assert service.db.all('SELECT * FROM actions') == []
    assert service.db.all('SELECT * FROM message_reply_drafts') == []
    state = client.get(path).json()
    assert state['next_run'] > time.time() and state['failures'] == 0


@pytest.mark.parametrize('exception', [Problem('timeout', 'secret', 502), RuntimeError('secret')])
def test_scheduler_backoff_preserves_cache_without_private_errors(workbench, monkeypatch, exception):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/message-observation'
    client.put(path, json={'enabled': True, 'interval_s': 300})
    client.post(f'/api/accounts/{ident}/messages/sync')
    old = service.db.all('SELECT * FROM operation_records')
    def fail(*args, **kwargs):
        raise exception
    monkeypatch.setattr(service.provider, 'call', fail)
    for failures in range(1, 4):
        service.db.execute('UPDATE message_observation SET next_run=0')
        before = time.time()
        assert service.observation.run_once() is True
        state = client.get(path).json()
        assert state['failures'] == failures
        assert state['next_run'] >= before + 300 * 2 ** failures
        assert 'secret' not in str(state)
    assert service.db.all('SELECT * FROM operation_records') == old


def test_takeover_blocks_manual_sync_draft_and_scheduler_until_admin_release(workbench):
    client, service = workbench
    ident = account(client)
    base = f'/api/accounts/{ident}'
    path = base + '/message-observation'
    client.put(path, json={'enabled': True, 'interval_s': 300})
    agent = {'Authorization': 'Bearer ' + AGENT}
    assert client.post(path + '/takeover', headers=agent).status_code == 200
    assert client.get(path).json()['takeover'] is True
    assert client.post(base + '/messages/sync').json()['code'] == 'human_takeover'
    assert client.post(base + '/messages/' + 'a' * 64 + '/reply-draft').json()['code'] == 'human_takeover'
    service.db.execute('UPDATE message_observation SET next_run=0')
    assert service.observation.run_once() is False
    assert client.post(path + '/release', headers=agent).status_code == 403
    client.put(path, json={'enabled': True, 'interval_s': 300})
    assert client.get(path).json()['takeover'] is True
    assert client.post(path + '/release').status_code == 200
    assert client.get(path).json()['takeover'] is False
    assert service.observation.run_once() is False
    assert client.post(base + '/messages/sync').status_code == 200


def test_paused_account_skipped_and_restart_defers_overdue_poll(workbench):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/message-observation'
    client.put(path, json={'enabled': True, 'interval_s': 300})
    service.db.execute('UPDATE message_observation SET next_run=0')
    client.post(f'/api/accounts/{ident}/pause')
    assert service.observation.run_once() is False
    service.recover()
    assert client.get(path).json()['next_run'] > time.time()


def test_worker_invokes_observation_on_existing_thread(workbench, monkeypatch):
    _, service = workbench
    calls = []
    monkeypatch.setattr(service, 'run_once', lambda: calls.append('action'))
    monkeypatch.setattr(service, 'monitor_once', lambda: calls.append('monitor'))
    monkeypatch.setattr(service.observation, 'run_once', lambda: calls.append('observation'))
    monkeypatch.setattr(service.notifications, 'run_once', lambda: calls.append('notification'))
    waits = iter([False, True])
    monkeypatch.setattr(service.stop, 'wait', lambda seconds: next(waits))
    service.loop()
    assert calls == ['action', 'monitor', 'observation', 'notification']


def test_unexpected_collection_failure_marks_last_sample_failed(workbench, monkeypatch):
    client, service = workbench
    ident = account(client)
    base = f'/api/accounts/{ident}'
    client.post(base + '/messages/sync')
    client.put(base + '/message-observation', json={'enabled': True})
    service.db.execute('UPDATE message_observation SET next_run=0')
    def fail(*args, **kwargs):
        raise RuntimeError('private')
    monkeypatch.setattr(service.provider, 'call', fail)
    service.observation.run_once()
    assert client.get(base + '/messages').json()['last_sync']['state'] == 'failed'


def test_takeover_then_immediate_release_never_replays_approval(workbench):
    from test_workbench import approve, message
    client, service = workbench
    ident = account(client)
    action = message(client, ident).json()
    approve(client, action)
    path = f'/api/accounts/{ident}/message-observation'
    client.post(path + '/takeover')
    assert client.get('/api/actions/' + action['id']).json()['state'] == 'blocked'
    client.post(path + '/release')
    assert service.run_once() is False
    assert client.get('/api/actions/' + action['id']).json()['state'] == 'blocked'


def test_provider_checks_takeover_at_operation_boundary(workbench):
    client, service = workbench
    ident = account(client)
    client.post(f'/api/accounts/{ident}/message-observation/takeover')
    for operation, write in [('messages', False), ('message.send', True)]:
        with pytest.raises(Problem) as caught:
            service.provider.call(ident, operation, {}, write=write)
        assert caught.value.code == 'human_takeover'


def test_observation_capability_is_not_autonomous_reply(workbench):
    client, _ = workbench
    caps = client.get('/api/capabilities').json()
    assert caps['message_observation'] is True
    assert caps['message_observation_policy']['default_enabled'] is False
    assert caps['autonomous_reply'] is False


def test_takeover_blocks_previously_approved_message_without_sending(workbench):
    from test_workbench import approve, message
    client, service = workbench
    ident = account(client)
    action = message(client, ident).json()
    approve(client, action)
    client.post(f'/api/accounts/{ident}/message-observation/takeover')
    assert service.run_once() is False
    result = client.get('/api/actions/' + action['id']).json()
    assert result['state'] == 'blocked'
    assert result['result'] is None
    assert client.post('/api/actions', json={'account_id': ident, 'kind': 'message.send',
        'payload': {'cid': 'demo-chat', 'toid': '10001', 'text': 'hi'},
        'idempotency_key': 'takeover-new'}).status_code == 409
