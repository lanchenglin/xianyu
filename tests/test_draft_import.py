import pytest
from test_workbench import account, upload
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_import_preview_confirm_idempotent_and_progress(workbench):
    client, service = workbench
    aid = account(client)
    body = {'account_id': aid, 'rows': [{'title': 'fiction one'}, {'title': 'fiction two'}],
            'idempotency_key': 'import-fiction-01'}
    preview = client.post('/api/draft-import/preview', json=body)
    assert preview.status_code == 200
    assert service.db.one('SELECT COUNT(*) n FROM drafts')['n'] == 0
    confirmed = client.post('/api/draft-import/confirm', json={**body, 'digest': preview.json()['digest']})
    assert confirmed.status_code == 200
    again = client.post('/api/draft-import/confirm', json={**body, 'digest': preview.json()['digest']})
    assert again.json() == confirmed.json()
    assert service.db.one('SELECT COUNT(*) n FROM drafts')['n'] == 2
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0
    progress = client.get(f"/api/accounts/{aid}/draft-imports/{confirmed.json()['id']}").json()
    assert len(progress['rows']) == 2
    assert all(row['action'] is None for row in progress['rows'])
    changed = {**body, 'rows': [{'title': 'changed'}], 'digest': preview.json()['digest']}
    assert client.post('/api/draft-import/confirm', json=changed).status_code == 409
    other = account(client)
    assert client.get(f"/api/accounts/{other}/draft-imports/{confirmed.json()['id']}").status_code == 409


def test_import_single_proposal_stays_pending_and_tracks_progress(workbench):
    from test_publish_preview import DEFAULTS
    client, service = workbench
    aid = account(client)
    client.put(f'/api/accounts/{aid}/publish-defaults', json=DEFAULTS)
    body = {'account_id': aid, 'rows': [{'title': 'fiction', 'desc': 'fiction', 'price': '10',
            'images': [upload(client, aid)]}], 'idempotency_key': 'import-single-01'}
    preview = client.post('/api/draft-import/preview', json=body).json()
    batch = client.post('/api/draft-import/confirm', json={**body, 'digest': preview['digest']}).json()['id']
    progress_path = f'/api/accounts/{aid}/draft-imports/{batch}'
    row = client.get(progress_path).json()['rows'][0]
    path = f"/api/draft-imports/{batch}/{row['draft_id']}/propose"
    request = {'account_id': aid, 'revision': 1}
    proposed = client.post(path, json=request)
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()['state'] == 'pending'
    assert client.post(path, json=request).json()['id'] == proposed.json()['id']
    assert client.get(progress_path).json()['rows'][0]['action']['id'] == proposed.json()['id']
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 1


def test_import_proposal_rejects_concurrent_edit(workbench, monkeypatch):
    from test_publish_preview import DEFAULTS
    client, service = workbench
    aid = account(client)
    client.put(f'/api/accounts/{aid}/publish-defaults', json=DEFAULTS)
    body = {'account_id': aid, 'rows': [{'title': 'fiction', 'desc': 'fiction', 'price': '10',
            'images': [upload(client, aid)]}], 'idempotency_key': 'import-race-01'}
    preview = client.post('/api/draft-import/preview', json=body).json()
    batch = client.post('/api/draft-import/confirm', json={**body, 'digest': preview['digest']}).json()['id']
    row = client.get(f'/api/accounts/{aid}/draft-imports/{batch}').json()['rows'][0]
    original = service.propose
    def race(*args, **kwargs):
        service.db.execute('UPDATE drafts SET revision=revision+1 WHERE id=?', (row['draft_id'],))
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'propose', race)
    result = client.post(f"/api/draft-imports/{batch}/{row['draft_id']}/propose", json={'account_id': aid, 'revision': 1})
    assert result.status_code == 409
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0


def test_import_bounds_and_asset_ownership(workbench):
    client, _ = workbench
    aid, other = account(client), account(client)
    body = {'account_id': aid, 'rows': [{'images': [upload(client, other)]}], 'idempotency_key': 'import-fiction-02'}
    assert client.post('/api/draft-import/preview', json=body).status_code == 409
    assert client.post('/api/draft-import/preview', json={**body, 'rows': [{}] * 51}).status_code == 422
