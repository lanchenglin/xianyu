"""Fictional failures only; no platform or private snapshot access."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.test_daily_publish import setup
from tests.test_publish_executor import execute, ready, transport
from tests.test_workbench import AGENT
from tests.test_workbench import workbench as workbench
from xianyu_workbench.daily_publish import DailyPublish
from xianyu_workbench.provider import Problem

MARKER = 'PRIVATE_MARKER_cookie_token_https://private.invalid/request'


@pytest.mark.parametrize('code', [
    'unknown_historical', 'upload_contract_failed', 'ack_contract_failed',
    'readback_contract_failed', 'local_exception',
])
def test_problem_cannot_claim_local_or_historical_diagnostic(code):
    from xianyu_workbench.publish_diagnostics import failure_summary
    assert failure_summary(Problem(code, MARKER), 'submitting') == {
        'code': 'upstream_error', 'stage': 'submitting',
    }


@pytest.mark.parametrize('contract', ['unknown_historical', 'risk_control', MARKER])
def test_contract_channel_rejects_non_contract_codes(contract):
    from xianyu_workbench.publish_diagnostics import failure_summary
    assert failure_summary(ValueError(MARKER), 'verifying', contract) == {
        'code': 'local_exception', 'stage': 'verifying',
    }


@pytest.mark.parametrize('failure', [None, {'code': 'unknown_historical', 'stage': 'submitting'}])
def test_new_execution_missing_or_historical_code_never_persists_history(workbench, monkeypatch, failure):
    client, service = workbench
    _, action = ready(client, service)
    monkeypatch.setattr('xianyu_workbench.publish_executor.execute', lambda *a: {
        'stage': 'submitting', 'failure': failure, 'ownership_verified': False,
    })
    value = execute(client, action).json()
    assert value['result']['failure'] == {'code': 'upstream_error', 'stage': 'submitting'}
    row = service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
    assert 'unknown_historical' not in json.dumps(service.vault.open(row['result']))
    audit = service.db.all("SELECT detail FROM audit WHERE event='publish.executed'")
    assert json.loads(audit[-1]['detail']) == {'state': 'unconfirmed', 'failure_code': 'upstream_error'}
    assert execute(client, action).status_code == 409


@pytest.mark.parametrize(('error', 'code'), [
    (Problem('risk_control', MARKER), 'risk_control'),
    (Problem('auth_required', MARKER), 'auth_required'),
    (Problem('timeout', MARKER), 'timeout'),
    (Problem('uncertain', MARKER), 'uncertain'),
    (Problem('upstream_error', MARKER), 'upstream_error'),
    (Problem(MARKER, MARKER), 'upstream_error'),
    *[(Problem(code, MARKER), 'upstream_error') for code in (
        'unknown_historical', 'upload_contract_failed', 'ack_contract_failed',
        'readback_contract_failed', 'local_exception',
    )],
    (TimeoutError(MARKER), 'timeout'),
    (type(MARKER, (Exception,), {})(MARKER), 'local_exception'),
])
def test_failure_survives_execution_without_sensitive_details(workbench, monkeypatch, error, code):
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    def call(account, operation, payload, **kwargs):
        if operation == 'publish.submit':
            raise error
        return base(account, operation, payload, **kwargs)
    monkeypatch.setattr(service.provider, '_live', call)
    value = execute(client, action).json()
    assert value['result'].get('failure') == {'code': code, 'stage': 'submitting'}
    assert value['state'] == 'unconfirmed'
    assert value['error'] and MARKER not in json.dumps(value)
    row = service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
    stored = service.vault.open(row['result'])
    assert stored['failure'] == {'code': code, 'stage': 'submitting'}
    assert 'unknown_historical' not in json.dumps(stored)
    assert MARKER not in json.dumps(stored)
    for headers in ({}, {'Authorization': 'Bearer ' + AGENT}):
        response = client.get(f"/api/actions/{action['id']}", headers=headers)
        assert response.json()['result']['failure'] == stored['failure']
        assert MARKER not in response.text
    audit = service.db.all("SELECT detail FROM audit WHERE event='publish.executed'")
    assert json.loads(audit[-1]['detail']) == {'state': 'unconfirmed', 'failure_code': code}
    assert MARKER not in json.dumps(service.db.all('SELECT * FROM audit'))
    assert not service.run_once()
    assert execute(client, action).status_code == 409


@pytest.mark.parametrize(('operation', 'bad', 'code', 'stage'), [
    ('publish.upload', {}, 'upload_contract_failed', 'uploading'),
    ('publish.submit', {'ret': [MARKER], 'data': {}}, 'ack_contract_failed', 'submitting'),
    ('publish.submit', {'data': None}, 'ack_contract_failed', 'submitting'),
    ('publish.readback', {'ret': [MARKER], 'data': {}}, 'readback_contract_failed', 'verifying'),
    ('publish.readback', None, 'readback_contract_failed', 'verifying'),
])
def test_contract_failures_are_not_guessed_upstream_causes(workbench, monkeypatch, operation, bad, code, stage):
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    monkeypatch.setattr(service.provider, '_live', lambda a, op, p, **kw: bad if op == operation else base(a, op, p, **kw))
    value = execute(client, action).json()
    assert value['result'].get('failure') == {'code': code, 'stage': stage}
    assert value['state'] == 'unconfirmed' and value['error']
    assert MARKER not in json.dumps(value)


@pytest.mark.parametrize('failure', [
    {'code': 'timeout', 'stage': 'submitting', 'message': MARKER, 'raw': {'secret': MARKER}},
    {'code': {'secret': MARKER}, 'stage': ['submitting', MARKER]},
    {'code': MARKER, 'stage': MARKER},
    [MARKER], MARKER, None,
])
def test_action_projection_only_exposes_known_failure_scalars(workbench, failure):
    client, service = workbench
    _, action = ready(client, service)
    saved = {'stage': 'submitting', 'uploaded_count': 1, 'failure': failure}
    service.db.execute("UPDATE actions SET state='unconfirmed',result=? WHERE id=?", (service.vault.seal(saved), action['id']))
    before = service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
    for headers in ({}, {'Authorization': 'Bearer ' + AGENT}):
        response = client.get(f"/api/actions/{action['id']}", headers=headers)
        assert MARKER not in response.text
        projected = response.json()['result']['failure']
        assert projected == ({'code': 'timeout', 'stage': 'submitting'} if isinstance(failure, dict) and failure.get('code') == 'timeout'
                             else {'code': 'unknown_historical', 'stage': 'submitting'})
    assert service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],)) == before


def test_historical_action_read_only_unknown_and_success_has_no_failure(workbench, monkeypatch):
    client, service = workbench
    _, action = ready(client, service)
    monkeypatch.setattr(service.provider, '_live', transport([]))
    value = execute(client, action).json()
    assert value['error'] is None and 'failure' not in value['result']
    saved = {'stage': 'submitting', 'uploaded_count': 1}
    service.db.execute("UPDATE actions SET state='unconfirmed',result=?,error=NULL WHERE id=?", (service.vault.seal(saved), action['id']))
    before = service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('diagnostic must be local'))
    value = client.get(f"/api/actions/{action['id']}").json()
    assert value['result'].get('failure') == {'code': 'unknown_historical', 'stage': 'submitting'}
    assert service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],)) == before
    assert execute(client, action).status_code == 409


@pytest.mark.parametrize('code', ['risk_control', 'auth_required', 'timeout', 'upstream_error'])
def test_real_provider_pause_and_daily_ledger_remain_closed(workbench, monkeypatch, code):
    client, service = workbench
    aid, _, body = setup(client, service, monkeypatch)
    policy = DailyPublish(service)
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 200
    # Restore the real Provider boundary, replacing only the child process.
    monkeypatch.undo()
    base = transport([])
    class Process:
        returncode = 0
        def communicate(self, text, timeout):
            request = json.loads(text)
            if request['operation'] == 'publish.submit':
                return json.dumps({'ok': False, 'code': code, 'message': MARKER}), ''
            return json.dumps({'ok': True, 'data': base(None, request['operation'], request['payload'])}), ''
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', lambda *a, **kw: Process())
    at = datetime(2026, 10, 20, 9, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    value = policy.tick(aid, now=at)
    row = service.db.one('SELECT * FROM actions WHERE id=?', (value['action_id'],))
    assert service.vault.open(row['result']).get('failure') == {'code': code, 'stage': 'submitting'}
    assert row['state'] == 'unconfirmed'
    assert bool(service.provider.account(aid)['paused']) == (code in ('risk_control', 'auth_required'))
    dates = service.db.all('SELECT * FROM daily_publish_dates')
    assert len(dates) == 1
    assert client.get(f'/api/accounts/{aid}/daily-publish').json()['enabled'] is False
    assert policy.tick(aid, now=at + 86400).get('state') != 'submitted'
    assert client.put(f'/api/accounts/{aid}/daily-publish', json=body).status_code == 409
    assert service.db.all('SELECT * FROM daily_publish_dates') == dates
    assert execute(client, row).status_code == 409
