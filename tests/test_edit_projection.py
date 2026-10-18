"""Fictional responses exercising the three evidenced observational leaves."""
from copy import deepcopy

import pytest

from tests.test_edit_snapshot import protocol as base_protocol
from tests.test_edit_snapshot import ready, transport
from tests.test_item_edit import execute
from tests.test_workbench import account, approve
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import digest

FIELDS = ['browse_count', 'server_time', 'commerce_subtitle']


def observations(snapshot, n):
    snapshot['detail']['itemDO']['browseCnt'] = n
    snapshot['detail']['serverTime'] = str(n)
    snapshot['detail']['commerceDO'] = {'idleItemDetailFloatInfo': {'subTitleTextInfo': {'text': str(n), 'fixed': 'keep'}}}


def protocol():
    p = base_protocol()
    observations(p['before'], 1)
    p['before_content_hash'] = digest(p['before'])
    p.update(comparison_mode='observational_projection', observational_fields=FIELDS.copy())
    return p


def changing(events, mutate=None):
    fake = transport(events)
    def call(account, operation, payload, **kwargs):
        result = fake(account, operation, payload, **kwargs)
        if operation == 'edit.detail':
            wrapper = {'detail': result['data']}
            observations(wrapper, len(events) + 10)
            if mutate:
                mutate(wrapper, 'edit.submit' in events)
        return result
    return call


def test_three_values_change_but_raw_audit_is_kept(workbench, monkeypatch):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', changing(events))
    assert execute(client, action).json()['state'] == 'submitted'
    result = service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result'])
    assert [s['detail']['itemDO']['browseCnt'] for s in result['preflight_snapshots']] == [11, 13]
    assert result['after']['detail']['itemDO']['browseCnt'] == 16
    assert result['after_projection_hash'] != result['after_content_hash']
    assert result['comparison_mode'] == 'observational_projection'


@pytest.mark.parametrize('phase', ['preflight', 'after'])
@pytest.mark.parametrize('bad', ['missing', 'bool', 'string', 'time_type', 'text_type', 'other', 'array'])
def test_projection_never_hides_structure_types_or_other_values(workbench, monkeypatch, bad, phase):
    client, service = workbench
    aid, action, body = ready(client, service, protocol())
    def mutate(s, after):
        if after != (phase == 'after'):
            return
        d = s['detail']
        if bad == 'missing':
            del d['itemDO']['browseCnt']
        elif bad in ('bool', 'string'):
            d['itemDO']['browseCnt'] = True if bad == 'bool' else '11'
        elif bad == 'time_type':
            d['serverTime'] = 123
        elif bad == 'text_type':
            d['commerceDO']['idleItemDetailFloatInfo']['subTitleTextInfo']['text'] = None
        elif bad == 'other':
            d['commerceDO']['idleItemDetailFloatInfo']['subTitleTextInfo']['fixed'] = 'changed'
        else:
            d['images'].append('changed')
    events = []
    monkeypatch.setattr(service.provider, '_live', changing(events, mutate))
    assert execute(client, action).json()['state'] == ('unconfirmed' if phase == 'after' else 'failed')
    assert events.count('edit.submit') == (1 if phase == 'after' else 0)
    if phase == 'after':
        assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol()).status_code == 409
        body['idempotency_key'] = 'projection-new-unknown'
        assert client.post('/api/item-edit', json=body).status_code == 409


@pytest.mark.parametrize('bad', ['arbitrary', 'wildcard', 'duplicate', 'full_with_fields', 'empty', 'missing', 'type', 'content', 'status', 'request', 'ancestor'])
def test_projection_configuration_gate(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    if bad in ('arbitrary', 'wildcard'):
        p['observational_fields'] = ['detail.itemDO' if bad == 'arbitrary' else '*']
    elif bad == 'duplicate':
        p['observational_fields'].append('browse_count')
    elif bad == 'full_with_fields':
        p['comparison_mode'] = 'full_snapshot'
    elif bad == 'empty':
        p['observational_fields'] = []
    elif bad == 'missing':
        del p['before']['detail']['serverTime']
    elif bad == 'type':
        p['before']['detail']['itemDO']['browseCnt'] = True
    elif bad == 'content':
        p['before']['detail']['serverTime'] = 'old'
        p['content_mappings'][0]['path'] = ['detail', 'serverTime']
    elif bad == 'status':
        p['status_path'] = ['detail', 'serverTime']
    else:
        p['invariant_mappings'][1]['before_path'] = ['detail', 'itemDO'] if bad == 'ancestor' else ['detail', 'itemDO', 'browseCnt']
    p['before_content_hash'] = digest(p['before'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


def test_legacy_full_comparison_still_blocks_observations(workbench, monkeypatch):
    client, service = workbench
    p = protocol()
    del p['comparison_mode'], p['observational_fields']
    _, action, _ = ready(client, service, p)
    events = []
    monkeypatch.setattr(service.provider, '_live', changing(events))
    assert execute(client, action).json()['state'] == 'failed'
    assert 'edit.submit' not in events


def test_mode_change_invalidates_approved_action(workbench, monkeypatch):
    client, service = workbench
    aid, action, _ = ready(client, service, protocol())
    p = protocol()
    p.update(comparison_mode='full_snapshot', observational_fields=[])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    monkeypatch.setattr(service.provider, '_live', lambda *a, **kw: pytest.fail('stale approval read'))
    r = execute(client, action)
    assert r.status_code == 409 or r.json()['state'] == 'failed'


@pytest.mark.parametrize('change', ['stable_value', 'selection'])
def test_verified_projection_rejects_reconfiguration_that_hides_drift(workbench, monkeypatch, change):
    client, service = workbench
    aid, action, _ = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', changing(events))
    assert execute(client, action).json()['state'] == 'submitted'
    p = protocol()
    if change == 'selection':
        p.update(comparison_mode='full_snapshot', observational_fields=[])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 409


def test_verified_reedit_compares_same_projection_and_new_raw_before(workbench, monkeypatch):
    client, service = workbench
    aid, action, body = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', changing(events))
    assert execute(client, action).json()['state'] == 'submitted'
    result = service.vault.open(service.db.one('SELECT result FROM actions WHERE id=?', (action['id'],))['result'])
    p = protocol()
    p['before'] = deepcopy(result['after'])
    observations(p['before'], 100)
    p['before_content_hash'] = digest(p['before'])
    p['before_values'] = deepcopy(body['payload'])
    p['template']['itemTextDTO'].update(title=body['payload']['desc'], desc=body['payload']['desc'])
    p['template']['itemPriceDTO']['priceInCent'] = '1320'
    p['original_request'] = deepcopy(p['template'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    body['idempotency_key'] = 'projection-second-action'
    body['payload'].update(desc='next body', price='14.20')
    second = client.post('/api/item-edit', json=body)
    assert second.status_code == 201, second.text
    approve(client, second.json())
    service.db.execute('UPDATE accounts SET last_write=0 WHERE id=?', (aid,))
    def followup(account, op, request, **kw):
        events.append(op)
        if op == 'edit.submit':
            return {'ret': p['success_ret'], 'data': {'itemId': '777'}}
        snap = deepcopy(p['before'])
        observations(snap, len(events) + 200)
        if events.count('edit.submit') == 2:
            snap['detail']['itemDO'].update(desc='next body', price='14.20')
            snap['edit'].update(text='next body', price='1420')
        return {'ret': p['detail_success_ret'] if op == 'edit.detail' else p['read_success_ret'],
                'data': snap['detail' if op == 'edit.detail' else 'edit']}
    monkeypatch.setattr(service.provider, '_live', followup)
    assert execute(client, second.json()).json()['state'] == 'submitted'
    assert events.count('edit.submit') == 2
