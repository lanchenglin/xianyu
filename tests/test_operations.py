"""Fictional fixtures matching the observed response structure, not platform values."""
import copy

import pytest


def orders():
    return {'ret': ['SUCCESS::OK'], 'data': {'items': [{
        'commonData': {'itemId': '1001', 'orderIdStr': '9001', 'tradeStatusEnum': 'SAMPLE',
                       'peerUserId': 'private-peer'},
        'head': {'data': {'createTime': 'fictional-time', 'statusViewMsg': 'fictional-status',
                          'userInfo': {'userNick': 'PRIVATE-NICK', 'phone': 'PRIVATE-PHONE'}}},
        'content': {'data': {'address': 'PRIVATE-ADDRESS'}}}],
        'nextPage': 'UNVERIFIED', 'lastEndRow': 'private-cursor', 'totalCount': '1'}}


def inventory():
    return {'ret': ['SUCCESS::OK'], 'data': {'cardList': [{'cardData': {
        'id': '1001', 'itemStatus': 7, 'priceInfo': {'price': '12.30', 'preText': 'ignore'},
        'title': 'Fictional item', 'trackParams': {'secret': 'PRIVATE'}}}],
        'nextPage': False, 'totalCount': 1}}


def test_order_minimal_fields_and_unknown_pagination():
    from xianyu_workbench.operations import normalize
    result = normalize('orders', orders())
    assert result['items'] == [{'order_id': '9001', 'item_id': '1001', 'status': 'SAMPLE',
                                'created_at': 'fictional-time', 'status_text': 'fictional-status'}]
    assert result['partial'] is True and result['completion'] == 'single_page'
    assert result['cursor_error'] == 'pagination_semantics_unknown'
    assert result['has_more'] is None
    assert 'PRIVATE' not in str(result) and 'private-cursor' not in str(result)


def test_inventory_whitelist_and_sample_not_full_inventory():
    from xianyu_workbench.operations import normalize
    result = normalize('inventory', inventory())
    assert result['items'] == [{'item_id': '1001', 'status': 7, 'price': '12.30', 'title': 'Fictional item'}]
    assert result['partial'] is True and result['has_more'] is False
    assert result['completion'] == 'single_page' and result['cursor_error'] is None


@pytest.mark.parametrize('next_page', [None, 0, 'false', {}, []])
def test_inventory_unknown_cursor_preserves_sample_not_completion(next_page):
    from xianyu_workbench.operations import normalize
    value = inventory()
    value['data']['nextPage'] = next_page
    result = normalize('inventory', value)
    assert len(result['items']) == 1 and result['has_more'] is None
    assert result['cursor_error'] == 'pagination_type_invalid' and result['partial']


@pytest.mark.parametrize('value', [{}, {'ret': ['FAIL::private'], 'data': {}},
    {'ret': [], 'data': {}}, {'ret': ['SUCCESS::OK', 'FAIL::bad'], 'data': {}},
    {'ret': ['SUCCESS::OK'], 'data': {'items': None}}])
def test_failed_or_malformed_response_is_not_empty_success(value):
    from xianyu_workbench.operations import normalize
    with pytest.raises(ValueError):
        normalize('orders', value)


def test_valid_empty_page_is_explicit_and_does_not_claim_complete():
    from xianyu_workbench.operations import normalize
    value = orders()
    value['data']['items'] = []
    result = normalize('orders', value)
    assert result['items'] == [] and result['partial'] and result['cursor_error']


@pytest.mark.parametrize('path,value', [('itemId', 123), ('orderIdStr', ''), ('tradeStatusEnum', [])])
def test_invalid_order_fields_reject_entire_page(path, value):
    from xianyu_workbench.operations import normalize
    body = orders()
    body['data']['items'][0]['commonData'][path] = value
    with pytest.raises(ValueError):
        normalize('orders', body)


@pytest.mark.parametrize('field,value', [('lastEndRow', None), ('totalCount', 'unknown'), ('totalCount', -1)])
def test_invalid_order_pagination_fields_are_audited(field, value):
    from xianyu_workbench.operations import normalize
    body = orders()
    body['data'][field] = value
    result = normalize('orders', body)
    assert result['cursor_error'] == 'pagination_type_invalid'
    assert result['partial'] and len(result['items']) == 1


def test_page_limits_and_duplicate_ids():
    from xianyu_workbench.operations import normalize
    body = orders()
    body['data']['items'] *= 101
    with pytest.raises(ValueError):
        normalize('orders', body)
    body['data']['items'] = body['data']['items'][:2]
    assert len(normalize('orders', body)['items']) == 1
    body['data']['items'][1] = copy.deepcopy(body['data']['items'][1])
    body['data']['items'][1]['commonData']['itemId'] = '9999'
    with pytest.raises(ValueError):
        normalize('orders', body)
