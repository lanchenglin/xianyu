from concurrent.futures import ThreadPoolExecutor

import pytest
from test_workbench import AGENT, account, upload
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_edit_draft_in_place_preserves_account_and_encryption(workbench):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    body = {'account_id': aid, 'title': 'old', 'images': [image]}
    created = client.post('/api/drafts', json=body).json()
    response = client.put('/api/drafts/' + created['id'], json={**body, 'title': 'private new', 'revision': 1})
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 2
    rows = client.get('/api/drafts').json()
    assert len(rows) == 1
    assert rows[0]['id'] == created['id']
    assert rows[0]['content']['title'] == 'private new'
    assert 'private new' not in service.db.one('SELECT content FROM drafts')['content']


def test_archive_is_local_and_frozen_approval_remains_unchanged(workbench):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    content = {'title': 'frozen title', 'desc': 'facts', 'price': '12.30', 'images': [image]}
    body = {'account_id': aid, **content}
    draft = client.post('/api/drafts', json=body).json()
    proposal = client.post('/api/actions', json={'account_id': aid, 'kind': 'item.publish',
                                               'payload': content, 'idempotency_key': 'frozen-draft-01'}).json()
    assert client.put('/api/drafts/' + draft['id'], json={**body, 'title': 'changed', 'revision': 1}).status_code == 200
    archive = client.post('/api/drafts/' + draft['id'] + '/archive', json={'account_id': aid, 'revision': 2},
                          headers={'Authorization': 'Bearer ' + AGENT})
    assert archive.status_code == 200, archive.text
    assert archive.json()['revision'] == 3
    assert client.get('/api/drafts').json()[0]['archived'] == 1
    assert client.put('/api/drafts/' + draft['id'], json={**body, 'revision': 3}).status_code == 409
    assert client.get('/api/actions/' + proposal['id']).json()['payload'] == proposal['payload']
    assert client.get('/api/assets/' + image).status_code == 200
    assert client.delete('/api/assets/' + image).status_code == 405
    assert client.get('/api/catalog').json() == []
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 1


def test_draft_conflicts_cross_account_assets_and_concurrent_revision(workbench):
    client, _ = workbench
    aid, other = account(client), account(client)
    body = {'account_id': aid, 'title': 'one'}
    draft = client.post('/api/drafts', json=body).json()
    path = '/api/drafts/' + draft['id']
    assert client.put(path, json={**body, 'account_id': other, 'revision': 1}).status_code == 409
    assert client.put(path, json={**body, 'images': [upload(client, other)], 'revision': 1}).status_code == 409
    assert client.post(path + '/archive', json={'account_id': other, 'revision': 1}).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda title: client.put(path, json={**body, 'title': title, 'revision': 1}).status_code,
                                ['two', 'three']))
    assert sorted(results) == [200, 409]
    assert client.put(path, json={**body, 'revision': 1}).status_code == 409
    assert client.post(path + '/archive', json={'account_id': aid, 'revision': 1}).status_code == 409
