# ruff: noqa: F811
import pytest
from test_workbench import AGENT, account, workbench  # noqa: F401

from xianyu_workbench.provider import Problem


def test_partial_messages_encrypted_isolated_idempotent_and_fail_closed(workbench, monkeypatch):
    client, service = workbench
    ident, other = account(client), account(client)
    path = f'/api/accounts/{ident}/messages'
    assert client.post(path + '/sync', headers={'Authorization': 'Bearer ' + AGENT}).status_code == 200
    assert client.post(path + '/sync').status_code == 200
    data = client.get(path).json()
    assert len(data['items']) == 1 and data['partial']
    assert data['items'][0]['body_status'] == 'unavailable'
    assert not data['items'][0]['recipient_verified']
    assert client.get(f'/api/accounts/{other}/messages').json()['items'] == []
    rows = service.db.all("SELECT * FROM operation_records WHERE kind='messages'")
    assert len(rows) == 1 and rows[0]['payload'].startswith('gAAAA')
    assert service.db.one('PRAGMA user_version')['user_version'] == 13
    assert client.post(f'/api/accounts/{other}/messages/sync').status_code == 200
    keys = service.db.all("SELECT record_key FROM operation_records WHERE kind='messages'")
    assert keys[0] != keys[1]
    def fail(*args, **kwargs):
        raise Problem('response_timeout', 'private', 502)
    monkeypatch.setattr(service.provider, 'call', fail)
    assert client.post(path + '/sync').status_code == 502
    stale = client.get(path).json()
    assert stale['last_sync']['state'] == 'failed' and len(stale['items']) == 1
    assert client.post(path + '/sync', headers={'Authorization': ''}).status_code == 401


def test_v6_message_cache_migration_preserves_ciphertext(tmp_path):
    import sqlite3
    from contextlib import closing

    from cryptography.fernet import Fernet

    from xianyu_workbench.db import DB, MIGRATIONS
    from xianyu_workbench.security import Vault
    vault = Vault(Fernet.generate_key().decode())
    sealed = vault.seal({'message_id': '987654', 'body': None})
    with closing(sqlite3.connect(tmp_path / 'workbench.db')) as conn:
        for migration in MIGRATIONS[:6]:
            migration(conn)
        conn.execute('PRAGMA user_version=6')
        conn.execute("INSERT INTO accounts(id,label,mode,created) VALUES('a','fixture','demo',1)")
        conn.execute("INSERT INTO operation_records VALUES('a','messages','key',?,'fixture',1)", (sealed,))
        conn.commit()
    db = DB(tmp_path, vault)
    assert db.one('PRAGMA user_version')['user_version'] == 13
    assert db.one('SELECT payload FROM operation_records')['payload'] == sealed
    assert len(list((tmp_path / 'backups').glob('before-v6-*.db'))) == 1
    with pytest.raises(ValueError, match='密钥'):
        DB(tmp_path, Vault(Fernet.generate_key().decode()))
    assert db.path.stat().st_mode & 0o777 == 0o600


def test_message_capabilities_schema_allowlist_and_unknown_recipient(workbench, monkeypatch):
    client, service = workbench
    caps = client.get('/api/capabilities').json()
    assert caps['partial_messages'] and not caps['autonomous_reply']
    assert 'messages' in caps['browser_policy']['cdp_operations']
    assert '/api/accounts/{account_id}/messages/sync' in client.get('/api/schema').json()['paths']
    ident = account(client)
    with pytest.raises(Problem):
        service.provider.call(ident, 'messages', {'url': 'anything'})
    for key, value in {'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:9998',
                       'XY_BROWSER_CDP_ACCOUNT_ID': 'a', 'XY_OPERATION_ACCOUNT_ID': 'a',
                       'XY_BROWSER_CDP_UID': '11', 'XY_OPERATION_UID': '11'}.items():
        monkeypatch.setenv(key, value)
    from xianyu_workbench.browser_adapter import validate_operation
    validate_operation('messages')
    result = client.post('/api/actions', json={'account_id': ident, 'kind': 'message.send',
        'payload': {'cid': '123', 'toid': '22', 'text': 'no unknown recipient'}, 'idempotency_key': 'unknown-msg'})
    assert result.status_code == 201  # Legacy demo workflow stays available.
    from dataclasses import replace
    service.s = replace(service.s, browser_cdp_endpoint='http://127.0.0.1:9998')
    service.db.execute("UPDATE accounts SET mode='live',uid='11' WHERE id=?", (ident,))
    result = client.post('/api/actions', json={'account_id': ident, 'kind': 'message.send',
        'payload': {'cid': '123', 'toid': '22', 'text': 'no unknown recipient'}, 'idempotency_key': 'blocked-msg'})
    assert result.status_code == 409
    assert result.json()['code'] == 'message_send_disabled'
