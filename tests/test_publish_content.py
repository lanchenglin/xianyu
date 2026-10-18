"""Isolated fixtures based on reported shapes, not platform verification."""
import pytest

from tests.test_publish_executor import execute, ready, transport
from tests.test_workbench import workbench as workbench


def test_candidate_matches_reported_structure(workbench):
    client, service = workbench
    _, action = ready(client, service)
    candidate = action['payload']['_publish_snapshot']['candidate']
    assert 'onlyTakeSelf' not in candidate
    assert type(candidate['itemAddrDTO']['divisionId']) is int


@pytest.mark.parametrize('field,value', [('divisionId', True), ('divisionId', 1.5)])
def test_location_rejects_lossy_numeric_types(workbench, field, value):
    from tests.test_publish_preview import DEFAULTS
    from tests.test_workbench import account
    client, _ = workbench
    aid = account(client)
    body = {**DEFAULTS, 'location': {**DEFAULTS['location'], field: value}}
    assert client.put(f'/api/accounts/{aid}/publish-defaults', json=body).status_code == 422


def test_no_shipping_candidate_has_only_reported_fee_fields(workbench):
    from tests.test_publish_preview import setup_preview
    from tests.test_workbench import account
    client, _ = workbench
    aid = account(client)
    _, body = setup_preview(client, aid)
    body['payload'].update(delivery='无需邮寄', can_self_pickup=True)
    body['idempotency_key'] = 'no-shipping-shape'
    result = client.post('/api/publish-preview', json=body).json()
    assert result['payload']['_publish_snapshot']['candidate']['itemPostFeeDTO'] == {
        'canFreeShipping': False, 'supportFreight': False, 'onlyTakeSelf': True}


@pytest.mark.parametrize('field', ['itemId', 'sellerId'])
def test_readback_ids_require_integer_contract(workbench, monkeypatch, field):
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    def changed(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            obj = value['data']['itemDO' if field == 'itemId' else 'sellerDO']
            obj[field] = str(obj[field])
        return value
    monkeypatch.setattr(service.provider, '_live', changed)
    assert execute(client, action).json()['state'] == 'unconfirmed'


def test_expected_price_cannot_disagree_with_frozen_payload(workbench):
    client, service = workbench
    aid, action = ready(client, service)
    protocol = {k: v for k, v in action['payload']['_publish_snapshot']['executor'].items() if k not in ('binding', 'revision')}
    protocol['readback_content']['expected_price'] = '0.01'
    assert client.put(f'/api/accounts/{aid}/publish-protocol', json=protocol).status_code == 200
    payload = {k: v for k, v in action['payload'].items() if k != '_publish_snapshot'}
    assert client.post('/api/publish-preview', json={'account_id': aid, 'kind': 'item.publish',
        'payload': payload, 'idempotency_key': 'wrong-price-contract'}).status_code == 409


@pytest.mark.parametrize('field,value', [('title', 'changed'), ('desc', '虚构说明\n欢迎咨询'),
                                        ('soldPrice', '12.3'), ('transportFee', 1.23),
                                        ('imageInfos', []), ('title', None)])
def test_changed_readback_content_never_verified(workbench, monkeypatch, field, value):
    observed = value
    client, service = workbench
    _, action = ready(client, service)
    base = transport([])
    def changed(account, operation, payload, **kwargs):
        value = base(account, operation, payload, **kwargs)
        if operation == 'publish.readback':
            value['data']['itemDO'][field] = observed
        return value
    monkeypatch.setattr(service.provider, '_live', changed)
    assert execute(client, action).json()['state'] == 'unconfirmed'
