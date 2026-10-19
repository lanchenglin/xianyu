"""P0 regression: all live transports require explicit single-action authority."""
from dataclasses import replace

import pytest

from tests.test_message_send_binding import propose, setup_live
from tests.test_workbench import account, approve, message
from tests.test_workbench import workbench as workbench
from xianyu_workbench.provider import Problem
from xianyu_workbench.security import digest


@pytest.mark.parametrize('enabled', [False, True])
def test_no_cdp_live_proposal_rejected(workbench, monkeypatch, enabled):
    client, service = workbench
    aid = account(client, 'live', '{"unb":"11","_m_h5_tk":"fictional_123"}')
    service.s = service.provider.s = replace(service.s, live_enabled=True, message_send_enabled=enabled)
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('outbound forbidden'))
    assert propose(client, aid).status_code == 409


@pytest.mark.parametrize('cdp', [False, True])
@pytest.mark.parametrize('enabled', [False, True])
def test_historical_live_approved_never_worker_claimed(workbench, monkeypatch, cdp, enabled):
    client, service = workbench
    aid = account(client)
    action = message(client, aid).json()
    approve(client, action)
    service.db.execute("UPDATE accounts SET mode='live',uid='11' WHERE id=?", (aid,))
    payload = action['payload']
    signature = digest({'account_id': aid, 'kind': 'message.send', 'payload': payload, 'mode': 'live'})
    service.db.execute("UPDATE actions SET mode='live',digest=? WHERE id=?", (signature, action['id']))
    service.s = service.provider.s = replace(service.s, live_enabled=True, message_send_enabled=enabled,
        browser_cdp_endpoint='http://127.0.0.1:19876' if cdp else '')
    monkeypatch.setattr(service.provider, 'call', lambda *a, **k: pytest.fail('worker must not dispatch'))
    assert service.run_once() is False
    assert service.db.one('SELECT state FROM actions WHERE id=?', (action['id'],))['state'] == 'approved'


@pytest.mark.parametrize('cdp', [False, True])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('supply_binding', [False, True])
def test_direct_provider_cannot_send(workbench, monkeypatch, cdp, enabled, supply_binding):
    from xianyu_workbench.message_send import binding
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    frozen = binding(service, service.provider.account(aid))
    service.s = service.provider.s = replace(service.s, message_send_enabled=enabled,
        browser_cdp_endpoint=service.s.browser_cdp_endpoint if cdp else '')
    with pytest.raises(Problem):
        service.provider.call(aid, 'message.send', {'cid': '123', 'toid': '22', 'text': '您好'},
                              write=True, expected_binding=frozen if supply_binding else None)
    assert calls == []


@pytest.mark.parametrize('cdp', [False, True])
@pytest.mark.parametrize('enabled', [False, True])
def test_selected_legacy_without_binding_never_sends(workbench, monkeypatch, enabled, cdp):
    client, service = workbench
    aid = account(client)
    action = message(client, aid).json()
    approve(client, action)
    service.db.execute("UPDATE accounts SET mode='live',uid='11' WHERE id=?", (aid,))
    signature = digest({'account_id': aid, 'kind': 'message.send', 'payload': action['payload'], 'mode': 'live'})
    service.db.execute("UPDATE actions SET mode='live',digest=? WHERE id=?", (signature, action['id']))
    service.s = service.provider.s = replace(service.s, live_enabled=True, message_send_enabled=enabled,
        browser_cdp_endpoint='http://127.0.0.1:19876' if cdp else '',
        browser_cdp_account_id=aid, browser_cdp_uid='11')
    service.db.execute('UPDATE accounts SET secret=? WHERE id=?',
                       (service.vault.seal({'unb': '11', '_m_h5_tk': 'fictional_123'}), aid))
    calls = []
    def transport(account, operation, payload, *, write):
        calls.append(operation)
        return service.provider.demo(operation, payload)
    monkeypatch.setattr(service.provider, '_live', transport)
    result = service.execute_one(action['id'], signature)
    assert calls == []
    assert result['state'] in ('failed', 'blocked')


def test_valid_cdp_selected_control(workbench, monkeypatch):
    client, service = workbench
    aid, _, calls = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    assert not service.run_once()
    assert service.execute_one(action['id'], action['digest'])['state'] == 'unconfirmed'
    assert [op for op, _ in calls].count('message.send') == 1
