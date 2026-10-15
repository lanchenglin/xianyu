"""Real stdio JSON-RPC against a disposable API; never uses .env or live services."""
import asyncio
import os
import socket
import sys
import threading

import pytest
import uvicorn
from cryptography.fernet import Fernet
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from xianyu_workbench.app import create_app
from xianyu_workbench.config import Settings


@pytest.fixture
def api_server(tmp_path):
    settings = Settings(tmp_path / 'data', 'admin-' + 'a' * 40, 'agent-' + 'b' * 40,
                        Fernet.generate_key().decode(), worker_enabled=False)
    app = create_app(settings)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    import time
    for _ in range(100):
        if server.started:
            break
        time.sleep(.02)
    assert server.started
    try:
        yield f'http://127.0.0.1:{port}', settings, app.state.service
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()


def test_stdio_discovery_call_and_local_notice_state(api_server, tmp_path):
    url, settings, service = api_server
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('fixture','{}',1)")

    async def check():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'xianyu_workbench.mcp_server'],
                                       cwd=str(tmp_path), env={'PATH': os.environ.get('PATH', ''),
                                       'XY_API_URL': url, 'XY_AGENT_TOKEN': settings.agent_token})
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert {'notifications', 'notification_state', 'notification_deliveries',
                    'sync_message_sample', 'cached_messages'} <= tools
            service.db.execute("INSERT INTO accounts(id,label,mode,created) VALUES('messages','fixture','demo',1)")
            result = await session.call_tool('sync_message_sample', {'account_id': 'messages'})
            assert not result.isError
            result = await session.call_tool('cached_messages', {'account_id': 'messages'})
            assert not result.isError
            assert 'unavailable' in str(result) and 'last_message_samples' in str(result)
            assert 'message_reply_draft' in tools
            from test_message_text import text_frame

            from xianyu_workbench.operations import normalize_messages
            item = normalize_messages(text_frame(), '11')['items'][0]
            service.db.execute("UPDATE operation_records SET payload=? WHERE kind='messages'", (service.vault.seal(item),))
            sample = service.db.one("SELECT record_key FROM operation_records WHERE kind='messages'")['record_key']
            result = await session.call_tool('message_reply_draft', {'account_id': 'messages', 'sample_id': sample})
            assert not result.isError and 'local_template' in str(result)
            assert service.db.all('SELECT * FROM actions') == []
            assert not tools & {'approve', 'shell', 'read_cookie', 'configure_notifications', 'pay', 'refund'}
            result = await session.call_tool('notification_state', {'notification_id': 1, 'read': True, 'archived': True})
            assert not result.isError
            assert service.db.one('SELECT archived FROM notifications')['archived'] == 1
            result = await session.call_tool('notifications', {'include_archived': True})
            assert not result.isError
            result = await session.call_tool('list_accounts', {})
            assert not result.isError
            for tool in (await session.list_tools()).tools:
                assert not {'url', 'base_url', 'token', 'shell', 'script'} & set(tool.inputSchema.get('properties', {}))
            result = await session.call_tool('notification_deliveries', {})
            assert not result.isError
    asyncio.run(check())


def test_stdio_rejects_admin_token(api_server, tmp_path):
    url, settings, _ = api_server

    async def check():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'xianyu_workbench.mcp_server'],
                                       cwd=str(tmp_path), env={'PATH': os.environ.get('PATH', ''),
                                       'XY_API_URL': url, 'XY_AGENT_TOKEN': settings.admin_token})
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool('list_accounts', {})
            assert result.isError
            assert '拒绝管理员令牌' in str(result)
            assert settings.admin_token not in str(result)
    asyncio.run(check())
