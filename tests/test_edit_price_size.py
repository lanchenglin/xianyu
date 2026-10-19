from copy import deepcopy
from decimal import Decimal

import pytest

from tests.test_edit_labels import protocol as label_protocol
from tests.test_edit_snapshot import protocol
from tests.test_item_edit import execute
from tests.test_workbench import account, approve
from tests.test_workbench import workbench as workbench
from xianyu_workbench.edit_snapshot import SnapshotProtocol, encoded
from xianyu_workbench.security import canonical, digest


def integer_protocol():
    p = protocol()
    p['before_values']['price'] = '2200.00'
    p['before']['detail']['itemDO']['price'] = '2200'
    p['before']['edit']['price'] = '220000'
    p['template']['itemPriceDTO']['priceInCent'] = '220000'
    p['original_request'] = deepcopy(p['template'])
    p['content_mappings'][2]['encoding'] = 'yuan_integer_string'
    p['before_content_hash'] = digest(p['before'])
    return p


@pytest.mark.parametrize('value,want', [('0.00', '0'), ('1.00', '1'), ('2200.00', '2200'), ('1000000.00', '1000000')])
def test_integer_yuan_encoding(value, want):
    assert encoded('price', 'yuan_integer_string', value) == want


@pytest.mark.parametrize('value', ['1.01', '0.10', '2200', '01.00', '-1.00', '1e2', 'NaN', '1000001.00', True])
def test_integer_yuan_rejects_unproved_formats(value):
    with pytest.raises(ValueError):
        encoded('price', 'yuan_integer_string', value)


@pytest.mark.parametrize('readback,state', [('2300', 'submitted'), ('2300.00', 'unconfirmed'), (2300, 'unconfirmed')])
def test_integer_readback_exact_and_large_protocol_frozen(workbench, monkeypatch, readback, state):
    client, service = workbench
    from dataclasses import replace
    service.s = service.provider.s = replace(service.s, live_enabled=True, edit_enabled=True)
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = integer_protocol()
    p['before']['detail']['audit'] = '原始审计' * 10000
    p['before_content_hash'] = digest(p['before'])
    r = client.put(f'/api/accounts/{aid}/edit-protocol', json=p)
    assert r.status_code == 200, r.text
    body = {'account_id': aid, 'kind': 'item.edit', 'payload': {'item_id': '777', 'title': 'old', 'desc': 'old body', 'price': '2300.00'}, 'idempotency_key': 'integer-yuan-once'}
    r = client.post('/api/item-edit', json=body)
    assert r.status_code == 201, r.text
    action = r.json()
    approve(client, action)
    events = []
    def call(account, op, request, **kw):
        events.append(op)
        if op == 'edit.submit':
            assert request['template']['itemPriceDTO']['priceInCent'] == '230000'
            assert len(canonical(request).encode()) < 250000  # full protocol never crosses bridge
            return {'ret': p['success_ret'], 'data': {'itemId': '777'}}
        snap = deepcopy(p['before'])
        if 'edit.submit' in events:
            snap['detail']['itemDO']['price'] = readback
            snap['edit']['price'] = '230000'
        return {'ret': p['detail_success_ret'] if op == 'edit.detail' else p['read_success_ret'], 'data': snap['detail' if op == 'edit.detail' else 'edit']}
    monkeypatch.setattr(service.provider, '_live', call)
    assert execute(client, action).json()['state'] == state
    assert events.count('edit.submit') == 1


def test_fractional_proposal_rejected_before_any_read(workbench):
    client, service = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=integer_protocol()).status_code == 200
    r = client.post('/api/item-edit', json={'account_id': aid, 'kind': 'item.edit', 'payload': {'item_id': '777', 'title': 'old', 'desc': 'old body', 'price': '2300.01'}, 'idempotency_key': 'reject-fractional'})
    assert r.status_code == 422
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0


@pytest.mark.parametrize('over', [False, True])
def test_total_protocol_utf8_exact_boundary(over):
    p = protocol()
    # Include model defaults when measuring the frozen protocol, but not local revision.
    defaults = SnapshotProtocol.model_validate(p).model_dump()
    defaults['before']['detail']['padding'] = ''
    defaults['before_content_hash'] = digest(defaults['before'])
    remaining = 262144 - len(canonical(defaults).encode())
    defaults['before']['detail']['padding'] = '中' * (remaining // 3) + 'x' * (remaining % 3 + int(over))
    defaults['before_content_hash'] = digest(defaults['before'])
    assert len(canonical(defaults).encode()) == 262144 + int(over)
    if over:
        with pytest.raises(ValueError):
            SnapshotProtocol.model_validate(defaults)
    else:
        SnapshotProtocol.model_validate(defaults)


def test_multi_recommendation_container_not_single_response_limit():
    p = label_protocol()
    for response in p['label_dependency']['responses']:
        response['data']['audit'] = '中' * 14000
        assert len(canonical(response).encode()) < 60000
    assert len(canonical(p).encode()) > 60000
    SnapshotProtocol.model_validate(p)
    p['label_dependency']['responses'][0]['data']['audit'] *= 2
    with pytest.raises(ValueError):
        SnapshotProtocol.model_validate(p)


def test_large_protocol_does_not_allow_oversized_single_edit_request():
    p = protocol()
    p['before']['edit']['large'] = 'x' * 60000
    p['template']['large'] = p['before']['edit']['large']
    p['original_request'] = deepcopy(p['template'])
    p['invariant_mappings'].append({'request_path': ['large'], 'before_path': ['edit', 'large'], 'evidence': 'Fictional exact invariant evidence'})
    p['before_content_hash'] = digest(p['before'])
    with pytest.raises(ValueError):
        SnapshotProtocol.model_validate(p)


def test_integer_mapping_price_only_and_zero_action_invalid():
    p = integer_protocol()
    p['content_mappings'][0]['encoding'] = 'yuan_integer_string'
    with pytest.raises(ValueError):
        SnapshotProtocol.model_validate(p)
    from xianyu_workbench.item_edit import EditIn
    with pytest.raises(ValueError):
        EditIn(item_id='777', title='old', desc='body', price='0.00')
    assert str(Decimal('2200').quantize(Decimal('.01'))) == '2200.00'
