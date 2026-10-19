"""Fictional bounded snapshots: never usable as platform evidence."""
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.test_item_edit import execute
from tests.test_workbench import account, approve
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import digest


def protocol():
    before = {'detail': {'itemDO': {'itemId': '777', 'title': 'old', 'desc': 'old body',
                                  'price': '12.30', 'status': 'ONLINE'},
                         'sellerDO': {'sellerId': '12345'}, 'images': ['fictional']},
              'edit': {'itemId': '777', 'userId': '99999', 'text': 'old body',
                       'price': '1230', 'images': ['fictional'], 'shipping': False}}
    template = {'itemId': '777', 'itemTextDTO': {'title': 'old body', 'desc': 'old body',
                                              'titleDescSeparate': False},
                'itemPriceDTO': {'priceInCent': '1230'}, 'images': ['fictional'],
                'shipping': False, 'sourceId': 'fictional-source', 'bizcode': 'pcMainPublish',
                'publishScene': 'pcMainPublish', 'uniqueCode': '1700000000000123'}
    return {'schema_version': 3, 'concurrency_mode': 'bounded_snapshot',
            'external_race_acknowledged': True, 'complete_semantics_confirmed': True,
            'evidence': 'Fictional complete request and dual response evidence',
            'item_id': '777', 'uid': '12345', 'api_version': '1.0', 'detail_api_version': '1.0',
            'text_mode': 'web_combined', 'before': before, 'before_content_hash': digest(before),
            'original_request': deepcopy(template), 'template': template,
            'success_ret': ['SUCCESS::fictional-edit'], 'read_success_ret': ['SUCCESS::fictional-read'],
            'detail_success_ret': ['SUCCESS::fictional-detail'],
            'identity_paths': {'item_id': ['detail', 'itemDO', 'itemId'],
                               'uid': ['detail', 'sellerDO', 'sellerId'], 'edit_item_id': ['edit', 'itemId']},
            'status_path': ['detail', 'itemDO', 'status'],
            'content_mappings': [
                {'path': path, 'field': field, 'encoding': encoding}
                for path, field, encoding in [
                    (['detail', 'itemDO', 'title'], 'title', 'identity'),
                    (['detail', 'itemDO', 'desc'], 'desc', 'identity'),
                    (['detail', 'itemDO', 'price'], 'price', 'yuan_string'),
                    (['edit', 'text'], 'desc', 'identity'), (['edit', 'price'], 'price', 'cent_string')]],
            'before_values': {'item_id': '777', 'title': 'old', 'desc': 'old body', 'price': '12.30'},
            'invariant_mappings': [
                {'request_path': req, 'before_path': src, 'evidence': 'Fictional exact mapping evidence'}
                for req, src in [(['itemId'], ['edit', 'itemId']), (['images'], ['edit', 'images']),
                                 (['shipping'], ['edit', 'shipping'])]],
            'fixed_constants': {k: template[k] for k in ('sourceId', 'bizcode', 'publishScene')},
            'unique_code_mode': 'timestamp_random'}


def ready(client, service, p=None):
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    service.s = service.provider.s = replace(service.s, live_enabled=True, edit_enabled=True)
    p = p or protocol()
    r = client.put(f'/api/accounts/{aid}/edit-protocol', json=p)
    assert r.status_code == 200, r.text
    body = {'account_id': aid, 'kind': 'item.edit', 'payload': {'item_id': '777', 'title': 'old',
            'desc': 'new body\nexact', 'price': '13.20'}, 'idempotency_key': 'snapshot-once'}
    r = client.post('/api/item-edit', json=body)
    assert r.status_code == 201, r.text
    approve(client, r.json())
    return aid, r.json(), body


def transport(events, change=None):
    def call(account, operation, payload, **kwargs):
        events.append(operation)
        if operation == 'edit.submit':
            assert payload['template']['itemTextDTO'] == {'title': 'new body\nexact', 'desc': 'new body\nexact', 'titleDescSeparate': False}
            assert payload['template']['itemPriceDTO'] == {'priceInCent': '1320'}
            assert payload['template']['uniqueCode'] != protocol()['template']['uniqueCode']
            if change == 'timeout':
                raise TimeoutError()
            return {'ret': ['SUCCESS::fictional-edit'], 'data': {'itemId': '777'}}
        before = deepcopy(protocol()['before'])
        if 'edit.submit' in events:
            before['detail']['itemDO'].update(title='old', desc='new body\nexact', price='13.20')
            before['edit'].update(text='new body\nexact', price='1320')
            if change == 'after':
                before['edit']['shipping'] = True
        elif change == 'seller':
            before['detail']['sellerDO']['sellerId'] = '99999'
        elif change == 'second' and len(events) > 2:
            before['edit']['shipping'] = True
        key = 'detail' if operation == 'edit.detail' else 'edit'
        return {'ret': ['SUCCESS::fictional-detail' if key == 'detail' else 'SUCCESS::fictional-read'], 'data': before[key]}
    return call


def test_snapshot_dual_read_single_submit_exact_full_readback(workbench, monkeypatch):
    client, service = workbench
    _, action, body = ready(client, service)
    frozen = service.vault.open(service.db.one('SELECT payload FROM actions WHERE id=?', (action['id'],))['payload'])
    code = frozen['_edit_snapshot']['unique_code']
    assert code.isdigit() and 14 <= len(code) <= 16
    assert client.post('/api/item-edit', json=body).json()['id'] == action['id']
    events = []
    fake = transport(events)
    def checked(account, operation, payload, **kwargs):
        if operation == 'edit.submit':
            assert payload['template']['uniqueCode'] == code
        return fake(account, operation, payload, **kwargs)
    monkeypatch.setattr(service.provider, '_live', checked)
    result = execute(client, action).json()
    assert result['state'] == 'submitted', result
    assert events == ['edit.detail', 'edit.read'] * 2 + ['edit.submit', 'edit.detail', 'edit.read']
    stored = service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result'])
    assert stored['after']['edit']['userId'] == '99999'
    assert stored['concurrency_mode'] == 'bounded_snapshot'
    assert stored['after_content_hash'] == digest(stored['after'])


@pytest.mark.parametrize('change,state,writes', [('seller', 'failed', 0), ('second', 'failed', 0),
                                               ('timeout', 'unconfirmed', 1), ('after', 'unconfirmed', 1)])
def test_snapshot_fail_closed(workbench, monkeypatch, change, state, writes):
    client, service = workbench
    aid, action, body = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events, change))
    assert execute(client, action).json()['state'] == state
    assert events.count('edit.submit') == writes
    if state == 'unconfirmed':
        assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 409
        body['idempotency_key'] = 'new-snapshot-key'
        assert client.post('/api/item-edit', json=body).status_code == 409
        assert execute(client, action).status_code == 409


@pytest.mark.parametrize('title,desc', [('different', 'old body'), ('different', 'new body')])
def test_combined_rejects_unproven_title_edit(workbench, title, desc):
    client, service = workbench
    aid, _, body = ready(client, service)
    body['idempotency_key'] = 'unsupported-title-edit'
    body['payload'].update(title=title, desc=desc)
    assert client.post('/api/item-edit', json=body).status_code == 409


def test_snapshot_disabled_execution_never_reads(workbench, monkeypatch):
    client, service = workbench
    _, action, _ = ready(client, service)
    service.s = service.provider.s = replace(service.s, edit_enabled=False)
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('disabled transport'))
    r = execute(client, action)
    assert r.status_code == 409 or r.json()['state'] in ('failed', 'blocked')


def test_snapshot_stale_reedit_never_submits(workbench, monkeypatch):
    client, service = workbench
    aid, action, body = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events))
    assert execute(client, action).json()['state'] == 'submitted'
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 200
    body['idempotency_key'] = 'stale-full-snapshot'
    second = client.post('/api/item-edit', json=body).json()
    approve(client, second)
    assert execute(client, second).json()['state'] == 'failed'
    assert events.count('edit.submit') == 1


def test_unique_code_collision_rejects_new_action(workbench, monkeypatch):
    client, service = workbench
    _, action, body = ready(client, service)
    frozen = service.vault.open(service.db.one('SELECT payload FROM actions WHERE id=?', (action['id'],))['payload'])
    monkeypatch.setattr('xianyu_workbench.edit_snapshot.unique_code', lambda: frozen['_edit_snapshot']['unique_code'])
    body['idempotency_key'] = 'colliding-unique-code'
    assert client.post('/api/item-edit', json=body).status_code == 409


def test_empty_identity_path_is_422(workbench):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    p['identity_paths']['edit_item_id'] = []
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


def test_verified_snapshot_allows_exact_new_before_without_fake_version(workbench, monkeypatch):
    client, service = workbench
    aid, action, body = ready(client, service)
    events = []
    monkeypatch.setattr(service.provider, '_live', transport(events))
    assert execute(client, action).json()['state'] == 'submitted'
    result = service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result'])
    p = protocol()
    p['before'] = result['after']
    p['before_content_hash'] = digest(p['before'])
    p['before_values'] = body['payload'].copy()
    p['template']['itemTextDTO'].update(title='new body\nexact', desc='new body\nexact')
    p['template']['itemPriceDTO']['priceInCent'] = '1320'
    p['original_request'] = deepcopy(p['template'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    body['idempotency_key'] = 'second-approved-snapshot'
    body['payload'].update(title='old', desc='next body', price='14.20')
    second = client.post('/api/item-edit', json=body)
    assert second.status_code == 201, second.text
    approve(client, second.json())
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    def followup(account, op, request, **kwargs):
        events.append(op)
        if op == 'edit.submit':
            assert request['template']['itemTextDTO']['desc'] == 'next body'
            return {'ret': p['success_ret'], 'data': {'itemId': '777'}}
        snap = deepcopy(result['after'])
        if events.count('edit.submit') == 2:
            snap['detail']['itemDO'].update(title='old', desc='next body', price='14.20')
            snap['edit'].update(text='next body', price='1420')
        key = 'detail' if op == 'edit.detail' else 'edit'
        return {'ret': p['detail_success_ret'] if key == 'detail' else p['read_success_ret'], 'data': snap[key]}
    monkeypatch.setattr(service.provider, '_live', followup)
    assert execute(client, second.json()).json()['state'] == 'submitted'
    assert events.count('edit.submit') == 2


@pytest.mark.parametrize('bad', ['ack', 'hash', 'seller', 'unmapped', 'constant', 'expression', 'version', 'image', 'missing_content', 'status'])
def test_snapshot_evidence_gate(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    if bad == 'ack':
        p['external_race_acknowledged'] = False
    elif bad == 'hash':
        p['before_content_hash'] = '0' * 64
    elif bad == 'seller':
        p['identity_paths']['uid'] = ['edit', 'userId']
    elif bad == 'unmapped':
        p['template']['unknown'] = p['original_request']['unknown'] = True
    elif bad == 'constant':
        p['fixed_constants']['shipping'] = False
    elif bad == 'expression':
        p['content_mappings'][0]['encoding'] = 'eval(value)'
    elif bad == 'version':
        p['version'] = 'fake'
    elif bad == 'image':
        p['template']['images'] = p['original_request']['images'] = ['other']
    elif bad == 'status':
        del p['status_path']
    else:
        p['content_mappings'] = p['content_mappings'][1:]
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422
