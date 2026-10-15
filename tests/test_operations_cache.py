# ruff: noqa: F811
import json

import pytest
from test_workbench import AGENT, account, workbench  # noqa: F401

from xianyu_workbench.app import create_app
from xianyu_workbench.provider import Problem


@pytest.mark.parametrize('kind', ['orders', 'inventory'])
def test_sync_encrypted_idempotent_account_scoped_and_restart(workbench, kind):
    client, service = workbench
    first, other = account(client), account(client)
    path = f'/api/accounts/{first}/{kind}'
    response = client.post(path + '/sync', headers={'Authorization': 'Bearer ' + AGENT})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['partial'] and result['completion'] == 'single_page' and result['demo']
    assert len(result['items']) == 1
    assert client.post(path + '/sync').status_code == 200
    cached = client.get(path).json()
    assert len(cached['items']) == 1 and cached['last_sync']['fetched_at'] > 0
    assert cached['last_sync']['has_more'] is None
    assert cached['last_sync']['reported_total'] is None
    assert client.get(f'/api/accounts/{other}/{kind}').json()['items'] == []
    rows = service.db.all('SELECT * FROM operation_records')
    assert len(rows) == 1 and rows[0]['payload'].startswith('gAAAA')
    assert '900001' not in json.dumps(rows)  # order ID also encrypted, lookup key is HMAC


def test_restart_deduplicates(tmp_path):
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
    from test_workbench import ADMIN

    from xianyu_workbench.config import Settings
    settings = Settings(tmp_path, ADMIN, AGENT, Fernet.generate_key().decode(), worker_enabled=False)
    with TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + ADMIN}) as client:
        ident = account(client)
        assert client.post(f'/api/accounts/{ident}/orders/sync').status_code == 200
    with TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + AGENT}) as client:
        assert client.post(f'/api/accounts/{ident}/orders/sync').status_code == 200
        assert len(client.get(f'/api/accounts/{ident}/orders').json()['items']) == 1


def test_failure_keeps_old_records_and_audits_safe_error(workbench, monkeypatch):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/orders'
    assert client.post(path + '/sync').status_code == 200
    def fail(*args, **kwargs):
        raise Problem('response_timeout', 'PRIVATE-RAW-ERROR', 502)
    monkeypatch.setattr(service.provider, 'call', fail)
    assert client.post(path + '/sync').status_code == 502
    result = client.get(path).json()
    assert len(result['items']) == 1 and result['last_sync']['state'] == 'failed'
    assert result['last_sync']['error'] == 'response_timeout'
    assert 'PRIVATE' not in json.dumps(service.db.all('SELECT * FROM operation_syncs'))


def test_read_sync_auth_schema_capabilities_and_no_transactions(workbench):
    client, service = workbench
    ident = account(client)
    assert client.post(f'/api/accounts/{ident}/orders/sync', headers={'Authorization': ''}).status_code == 401
    assert client.post('/api/accounts/unknown/orders/sync').status_code == 404
    caps = client.get('/api/capabilities').json()
    assert caps['partial_orders'] and caps['partial_inventory']
    assert not caps['full_inventory_sync'] and not caps['payment']
    assert set(caps['browser_policy']['cdp_operations']) == {'search', 'orders', 'inventory'}
    schema = client.get('/api/schema').json()
    assert '/api/accounts/{account_id}/orders/sync' in schema['paths']
    for op in ['pay', 'refund', 'orders.write']:
        with pytest.raises(Problem):
            service.provider.call(ident, op, {})


def test_empty_success_does_not_purge_cached_records(workbench, monkeypatch):
    client, service = workbench
    ident = account(client)
    path = f'/api/accounts/{ident}/orders'
    client.post(path + '/sync')
    from xianyu_workbench.provider import Provider
    empty = Provider.demo('orders', {})
    empty['items'] = []
    monkeypatch.setattr(service.provider, 'call', lambda *args, **kwargs: empty)
    assert client.post(path + '/sync').json()['items'] == []
    cached = client.get(path).json()
    assert len(cached['items']) == 1
    assert cached['last_sync']['item_count'] == 0


def test_v5_migration_and_wrong_key_protect_private_cache(tmp_path):
    import sqlite3
    from contextlib import closing

    from cryptography.fernet import Fernet

    from xianyu_workbench.db import DB, MIGRATIONS
    from xianyu_workbench.security import Vault
    vault = Vault(Fernet.generate_key().decode())
    with closing(sqlite3.connect(tmp_path / 'workbench.db')) as conn:
        for migration in MIGRATIONS[:5]:
            migration(conn)
        conn.execute('PRAGMA user_version=5')
        conn.execute("INSERT INTO accounts(id,label,mode,created) VALUES('old','preserve','demo',1)")
        conn.commit()
    db = DB(tmp_path, vault)
    assert db.one('PRAGMA user_version')['user_version'] == 6
    assert db.one('SELECT label FROM accounts')['label'] == 'preserve'
    assert len(list((tmp_path / 'backups').glob('before-v5-*.db'))) == 1
    db.execute('INSERT INTO operation_records VALUES(?,?,?,?,?,?)',
               ('old', 'orders', 'key', vault.seal({'order_id': '123456'}), 'fixture', 1))
    with pytest.raises(ValueError, match='密钥'):
        DB(tmp_path, Vault(Fernet.generate_key().decode()))
    assert vault.open(db.one('SELECT payload FROM operation_records')['payload']) == {'order_id': '123456'}
    assert db.path.stat().st_mode & 0o777 == 0o600


def test_cdp_allowlist_and_no_payload_surface(monkeypatch):
    from xianyu_workbench.browser_adapter import validate_operation
    for key, value in {'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:9998',
                       'XY_BROWSER_CDP_ACCOUNT_ID': 'a', 'XY_OPERATION_ACCOUNT_ID': 'a',
                       'XY_BROWSER_CDP_UID': '12345', 'XY_OPERATION_UID': '12345'}.items():
        monkeypatch.setenv(key, value)
    validate_operation('orders')
    validate_operation('inventory')
    from xianyu_workbench.browser_config import BrowserError
    with pytest.raises(BrowserError):
        validate_operation('item.delete')
