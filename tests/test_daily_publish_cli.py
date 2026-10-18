"""CLI talks only to the disposable API server fixture."""
import json
import os
import subprocess
import sys

from tests.test_mcp_stdio import api_server as api_server


def test_cli_status_tick_and_revoke_on_isolated_server(api_server):
    import httpx
    url, settings, service = api_server
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}) as client:
        aid = client.post('/api/accounts', json={'label': 'fictional cli', 'mode': 'demo'}).json()['id']
    env = {**os.environ, 'XY_ADMIN_TOKEN': settings.admin_token}
    for operation in ('status', 'tick', 'revoke'):
        result = subprocess.run([sys.executable, '-m', 'xianyu_workbench.cli', 'daily-publish', operation,
                                 '--url', url, '--account-id', aid], env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data.get('enabled') is False or data.get('reason') == 'disabled'
    # An orphaned ledger from damaged legacy storage must be visible through real CLI HTTP.
    import sqlite3
    with sqlite3.connect(service.db.path) as c:
        c.execute('INSERT INTO daily_publish_dates VALUES(?,?,?,?)', (aid, '2026-10-18', 'missing', 'old'))
    for operation in ('status', 'tick'):
        result = subprocess.run([sys.executable, '-m', 'xianyu_workbench.cli', 'daily-publish', operation,
                                 '--url', url, '--account-id', aid], env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        if operation == 'status':
            assert data['effective'] is False
            assert data['blocked_reason'] == 'daily_unresolved'
        else:
            assert data['reason'] == 'daily_unresolved'
    env['XY_ADMIN_TOKEN'] = settings.agent_token
    result = subprocess.run([sys.executable, '-m', 'xianyu_workbench.cli', 'daily-publish', 'tick',
                             '--url', url, '--account-id', aid], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert settings.agent_token not in result.stderr + result.stdout
