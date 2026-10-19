import pytest
from test_workbench import AGENT, account, upload
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_unarchive_revision_and_account(workbench):
    client, _ = workbench
    aid, other = account(client), account(client)
    draft = client.post('/api/drafts', json={'account_id': aid, 'title': 'fiction'}).json()
    path = '/api/drafts/' + draft['id']
    assert client.post(path + '/archive', json={'account_id': aid, 'revision': 1}).status_code == 200
    assert client.post(path + '/unarchive', json={'account_id': other, 'revision': 2}).status_code == 409
    assert client.post(path + '/unarchive', json={'account_id': aid, 'revision': 1}).status_code == 409
    result = client.post(path + '/unarchive', json={'account_id': aid, 'revision': 2})
    assert result.status_code == 200
    assert result.json()['revision'] == 3
    assert result.json()['archived'] is False


def test_asset_recycle_explicit_admin_and_references(workbench):
    client, service = workbench
    aid = account(client)
    image, unused = upload(client, aid), upload(client, aid)
    draft = client.post('/api/drafts', json={'account_id': aid, 'images': [image]}).json()
    client.post('/api/drafts/' + draft['id'] + '/archive', json={'account_id': aid, 'revision': 1})
    rows = client.get('/api/accounts/' + aid + '/assets').json()
    assert {r['id']: r['referenced'] for r in rows} == {image: True, unused: False}
    body = {'account_id': aid, 'sha256': service.db.one('SELECT sha256 FROM assets WHERE id=?', (unused,))['sha256'],
            'confirm': '永久删除未引用本地素材'}
    path = '/api/assets/' + unused + '/recycle'
    assert client.post(path, json=body, headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert client.post(path, json={**body, 'confirm': 'yes'}).status_code == 422
    assert client.post('/api/assets/' + image + '/recycle', json=body).status_code == 409
    assert client.post(path, json=body).status_code == 200
    assert client.get('/api/assets/' + unused).status_code == 404
    assert client.get('/api/assets/' + image).status_code == 200


def test_asset_create_rechecks_inside_transaction(workbench, monkeypatch):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    original = service.validate_assets
    calls = []
    def race(account_id, images):
        if not calls:
            calls.append(True)
            result = original(account_id, images)
            service.db.execute('DELETE FROM assets WHERE id=?', (image,))
            return result
        return original(account_id, images)
    monkeypatch.setattr(service, 'validate_assets', race)
    assert client.post('/api/drafts', json={'account_id': aid, 'images': [image]}).status_code == 409
    assert service.db.one('SELECT COUNT(*) n FROM drafts')['n'] == 0


def test_recycle_rejects_symlink_even_inside_asset_directory(workbench):
    client, service = workbench
    aid = account(client)
    image, other = upload(client, aid), upload(client, aid)
    row = service.db.one('SELECT * FROM assets WHERE id=?', (image,))
    target = service.s.data_dir / 'assets' / row['filename']
    target.unlink()
    target.symlink_to(service.s.data_dir / 'assets' / (other + '.jpg'))
    response = client.post('/api/assets/' + image + '/recycle', json={
        'account_id': aid, 'sha256': row['sha256'], 'confirm': '永久删除未引用本地素材'})
    assert response.status_code == 409
    assert client.get('/api/assets/' + other).status_code == 200


def test_historical_action_protects_asset(workbench):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    result = client.post('/api/actions', json={'account_id': aid, 'kind': 'item.publish',
        'payload': {'title': 'fiction', 'desc': 'fiction', 'price': '5', 'images': [image]},
        'idempotency_key': 'protect-image-01'})
    assert result.status_code == 201
    service.db.execute("UPDATE actions SET state='rejected'")
    row = client.get('/api/accounts/' + aid + '/assets').json()[0]
    assert row['referenced'] is True
    assert client.post('/api/assets/' + image + '/recycle', json={
        'account_id': aid, 'sha256': row['sha256'], 'confirm': '永久删除未引用本地素材'}).status_code == 409
