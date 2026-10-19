"""Agent-facing edit summaries must default-deny raw and future audit fields."""
import asyncio
import json
import os
import sys

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_edit_projection import changing, protocol
from tests.test_edit_snapshot import ready
from tests.test_item_edit import execute
from tests.test_mcp_stdio import api_server as api_server
from tests.test_workbench import AGENT
from tests.test_workbench import workbench as workbench

SECRET = 'PRIVATE-EDIT-AUDIT-MARKER'
SAFE = {'stage': 'verified', 'item_id': '777', 'ownership_verified': True,
        'status_verified': True, 'content_verified': True, 'verified_at': 123.0}


def seed_result(service, action_id, state):
    result = {**SAFE, 'preflight_snapshots': [{'detail': {'desc': SECRET}, 'edit': {'address': SECRET}}],
              'after': {'detail': SECRET}, 'before': {'edit': SECRET}, 'protocol': {'evidence': SECRET},
              'future_private_field': {'nested': [SECRET]}, 'after_projection_hash': SECRET}
    service.db.execute('UPDATE actions SET state=?,result=? WHERE id=?',
                       (state, service.vault.seal(result), action_id))
    return result


@pytest.mark.parametrize('state', ['submitted', 'unconfirmed', 'failed', 'running'])
def test_agent_http_edit_results_use_allowlist_admin_keeps_audit(workbench, state):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    raw = seed_result(service, action['id'], state)
    for route in ('/api/actions', '/api/actions/' + action['id']):
        response = client.get(route, headers={'Authorization': 'Bearer ' + AGENT})
        assert response.status_code == 200
        data = response.json()
        view = next(x for x in data if x['id'] == action['id']) if isinstance(data, list) else data
        assert SECRET not in json.dumps(view)
        assert view['result'] == SAFE
        assert '_edit_snapshot' not in view['payload']
        admin = client.get(route).json()
        admin_view = next(x for x in admin if x['id'] == action['id']) if isinstance(admin, list) else admin
        assert admin_view['result'] == raw
    assert service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result']) == raw


def test_actual_projected_edit_does_not_expose_preflight(workbench, monkeypatch):
    client, service = workbench
    p = protocol()
    p['before']['detail']['audit_only'] = SECRET
    from xianyu_workbench.security import digest
    p['before_content_hash'] = digest(p['before'])
    _, action, _ = ready(client, service, p)
    fake = changing([])
    def call(account, op, payload, **kw):
        result = fake(account, op, payload, **kw)
        if op == 'edit.detail':
            result['data']['audit_only'] = SECRET
        return result
    monkeypatch.setattr(service.provider, '_live', call)
    assert execute(client, action).json()['state'] == 'submitted'
    response = client.get('/api/actions/' + action['id'], headers={'Authorization': 'Bearer ' + AGENT})
    assert SECRET not in response.text
    assert 'preflight_snapshots' not in response.json()['result']
    assert client.get('/api/actions/' + action['id']).json()['result']['preflight_snapshots'][0]['detail']['audit_only'] == SECRET


def test_mcp_list_actions_hides_all_edit_audit_states(api_server, tmp_path):
    url, settings, service = api_server
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}) as client:
        for state in ('submitted', 'unconfirmed', 'failed'):
            _, action, _ = ready(client, service, protocol())
            seed_result(service, action['id'], state)

    async def check():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'xianyu_workbench.mcp_server'],
                                       cwd=str(tmp_path), env={'PATH': os.environ.get('PATH', ''),
                                       'TMPDIR': '/home/lan/.hermes/cache/scratch',
                                       'XY_API_URL': url, 'XY_AGENT_TOKEN': settings.agent_token})
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool('list_actions', {})
            assert not result.isError
            assert SECRET not in str(result)
            assert 'preflight_snapshots' not in str(result)
            assert 'content_verified' in str(result)
    asyncio.run(check())
