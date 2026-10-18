"""Wrong-shaped summary values cannot become an Agent audit channel."""
import asyncio
import json
import os
import sys

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_edit_privacy import SAFE, SECRET
from tests.test_edit_projection import protocol
from tests.test_edit_snapshot import ready
from tests.test_mcp_stdio import api_server as api_server
from tests.test_workbench import AGENT
from tests.test_workbench import workbench as workbench

KEYS = [*SAFE, 'notice']
BAD_VALUES = [{'nested': [SECRET]}, [SECRET], SECRET, None]
NOTICE = '编辑结果不确定，禁止重试；请人工核对同 ID 商品'


@pytest.mark.parametrize('key', KEYS)
@pytest.mark.parametrize('bad', BAD_VALUES)
def test_each_summary_field_rejects_nested_and_malformed_http(workbench, key, bad):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    raw = {**SAFE, key: bad}
    service.db.execute('UPDATE actions SET state=?,result=? WHERE id=?',
                       ('unconfirmed', service.vault.seal(raw), action['id']))
    expected = {k: v for k, v in SAFE.items() if k != key}
    for route in ('/api/actions', '/api/actions/' + action['id']):
        r = client.get(route, headers={'Authorization': 'Bearer ' + AGENT})
        assert r.status_code == 200
        data = r.json()
        view = data[0] if isinstance(data, list) else data
        assert SECRET not in json.dumps(view)
        assert view['result'] == expected
        admin = client.get(route).json()
        assert (admin[0] if isinstance(admin, list) else admin)['result'] == raw


@pytest.mark.parametrize('key,bad', [('verified_at', True), ('verified_at', -1),
    ('item_id', '888'), ('item_id', '７７７'), ('item_id', '777\n'), ('item_id', 777),
    ('stage', 'verified\n'), ('notice', NOTICE + SECRET),
    ('ownership_verified', 1), ('status_verified', 0), ('content_verified', 'true')])
def test_summary_rejects_wrong_scalar_formats(workbench, key, bad):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    service.db.execute('UPDATE actions SET result=? WHERE id=?',
                       (service.vault.seal({**SAFE, key: bad}), action['id']))
    view = client.get('/api/actions/' + action['id'], headers={'Authorization': 'Bearer ' + AGENT}).json()
    assert key not in view['result']


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True])
def test_summary_time_defense_without_nonfinite_json(workbench, monkeypatch, bad):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    row = service.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
    original = service.vault.open
    monkeypatch.setattr(service.vault, 'open', lambda value: {**SAFE, 'verified_at': bad} if value == 'fictional-bad-result' else original(value))
    row['result'] = 'fictional-bad-result'
    assert 'verified_at' not in service.action_view(row, 'agent')['result']


@pytest.mark.parametrize('stage', ['submitting', 'verifying', 'verified'])
def test_known_scalar_summary_and_admin_are_preserved(workbench, stage):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    raw = {**SAFE, 'stage': stage, 'notice': NOTICE, 'ownership_verified': False, 'verified_at': 0}
    service.db.execute('UPDATE actions SET result=? WHERE id=?', (service.vault.seal(raw), action['id']))
    for token in (AGENT, service.s.admin_token):
        assert client.get('/api/actions/' + action['id'], headers={'Authorization': 'Bearer ' + token}).json()['result'] == raw


def test_mcp_rejects_bad_values_in_all_allowed_keys(api_server, tmp_path):
    url, settings, service = api_server
    with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + settings.admin_token}) as client:
        actions = [ready(client, service, protocol())[1] for _ in range(3)]
    async def check():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'xianyu_workbench.mcp_server'],
            cwd=str(tmp_path), env={'PATH': os.environ.get('PATH', ''), 'TMPDIR': '/home/lan/.hermes/cache/scratch',
                                   'XY_API_URL': url, 'XY_AGENT_TOKEN': settings.agent_token})
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            for bad in BAD_VALUES:
                for action, state in zip(actions, ('submitted', 'unconfirmed', 'failed')):
                    service.db.execute('UPDATE actions SET state=?,result=? WHERE id=?',
                                       (state, service.vault.seal(dict.fromkeys(KEYS, bad)), action['id']))
                result = await session.call_tool('list_actions', {})
                assert not result.isError
                assert SECRET not in str(result)
    asyncio.run(check())
