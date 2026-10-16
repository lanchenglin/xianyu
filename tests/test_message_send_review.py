import time
from dataclasses import replace

from tests.test_message_send_binding import propose, setup_live
from tests.test_workbench import approve
from tests.test_workbench import workbench as workbench
from xianyu_workbench.provider import Problem


def test_takeover_release_during_busy_preflight_invalidates_approval(workbench, monkeypatch):
    client, service = workbench
    aid, _, _ = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)

    def busy(*args, **kwargs):
        service.observation.takeover(aid, True, 'admin')
        service.observation.takeover(aid, False, 'admin')
        raise Problem('busy', 'busy', 409)

    monkeypatch.setattr(service.provider, 'call', busy)
    result = service.execute_one(action['id'], action['digest'])
    assert result['state'] == 'blocked'


def test_takeover_release_during_successful_preflight_never_sends(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    original = service.provider._live

    def takeover(account, operation, payload, *, write):
        result = original(account, operation, payload, write=write)
        if operation == 'messages':
            service.observation.takeover(aid, True, 'admin')
            service.observation.takeover(aid, False, 'admin')
        return result

    monkeypatch.setattr(service.provider, '_live', takeover)
    service.execute_one(action['id'], action['digest'])
    assert not any(op == 'message.send' for op, _ in calls)


def test_readback_waits_for_read_slot_without_replaying_write(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    service.s = service.provider.s = replace(service.s, read_interval=0.05)
    service.db.execute('UPDATE accounts SET last_call=0 WHERE id=?', (aid,))
    started = time.monotonic()
    result = service.execute_one(action['id'], action['digest'])
    assert result['state'] == 'unconfirmed'
    assert result['result'].get('readback_failed') is not True
    assert time.monotonic() - started >= .05
    assert [op for op, _ in calls].count('message.send') == 1
    assert [op for op, _ in calls].count('messages') == 3
