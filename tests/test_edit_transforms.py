"""Finite transform fixtures are fictional, not platform activation evidence."""
from copy import deepcopy

import pytest

from tests.test_edit_snapshot import protocol as base_protocol
from tests.test_edit_snapshot import ready, transport
from tests.test_item_edit import execute
from tests.test_workbench import AGENT, account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import digest


def protocol():
    p = base_protocol()
    source = {
        'freebies': 'false', 'defaultPrice': 'true',
        'imageInfoDOList': [{'url': 'fictional-image', 'extraInfo': {'raw': 'false', 'isT': 'false', 'isH': 'false'},
                             'widthSize': '640', 'heightSize': '480', 'major': 'true', 'type': '0'}],
        'itemPostFeeDTO': {'canFreeShipping': 'true', 'supportFreight': 'true', 'onlyTakeSelf': 'false',
                           'templateId': '0', 'idleTemplateId': '0', 'postPriceInCent': '0'},
        'itemCatDTO': {'catId': '1', 'catName': 'fictional', 'channelCatId': '2', 'tbCatId': '3', 'sugShow': 'false'},
    }
    expected = {
        'freebies': False, 'defaultPrice': True,
        'imageInfoDOList': [{'url': 'fictional-image', 'extraInfo': {'raw': 'false', 'isT': 'false', 'isH': 'false'},
                             'widthSize': 640, 'heightSize': 480, 'major': True, 'type': 0,
                             'isQrCode': False, 'labels': [], 'templateIndex': '0', 'thumbnail': 'fictional-image', 'status': 'done'}],
        'itemPostFeeDTO': {'canFreeShipping': True, 'supportFreight': True, 'onlyTakeSelf': False, 'templateId': '0'},
        'itemCatDTO': {'catId': '1', 'catName': 'fictional', 'channelCatId': '2', 'tbCatId': '3'},
    }
    p['before']['edit'].update(source)
    p['template'].update(expected)
    for field, transform in [('freebies', 'bool_string'), ('defaultPrice', 'bool_string'),
                              ('imageInfoDOList', 'single_image_v1'), ('itemPostFeeDTO', 'free_shipping_v1'),
                              ('itemCatDTO', 'category_v1')]:
        p['invariant_mappings'].append({'request_path': [field], 'before_path': ['edit', field],
                                        'transform': transform, 'evidence': 'Fictional finite transform evidence'})
    p['original_request'] = deepcopy(p['template'])
    p['before_content_hash'] = digest(p['before'])
    return p


def transformed_transport(events, change=None):
    fake = transport(events)
    def call(account, op, payload, **kw):
        if op == 'edit.submit':
            for field in ('freebies', 'defaultPrice', 'imageInfoDOList', 'itemPostFeeDTO', 'itemCatDTO'):
                assert payload['template'][field] == protocol()['template'][field]
        result = fake(account, op, payload, **kw)
        if op == 'edit.read':
            for field in ('freebies', 'defaultPrice', 'imageInfoDOList', 'itemPostFeeDTO', 'itemCatDTO'):
                result['data'][field] = deepcopy(protocol()['before']['edit'][field])
            if change and ('edit.submit' in events) == (change == 'after'):
                result['data']['imageInfoDOList'][0]['extraInfo']['raw'] = 'changed'
        return result
    return call


def test_finite_transforms_execute_with_exact_original_and_raw_readback(workbench, monkeypatch):
    client, service = workbench
    aid, action, body = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', transformed_transport(events))
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=protocol(), headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert client.post('/api/item-edit', json=body, headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert execute(client, action).json()['state'] == 'submitted'
    assert events.count('edit.submit') == 1


def test_transform_change_revokes_approval_and_v2_rejects_transform(workbench, monkeypatch):
    client, service = workbench
    aid, action, _ = ready(client, service, protocol())
    p = protocol()
    p['before']['edit']['freebies'] = False
    p['invariant_mappings'][-5]['transform'] = 'identity'
    p['before_content_hash'] = digest(p['before'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 200
    monkeypatch.setattr(service.provider, '_live', lambda *a, **kw: pytest.fail('changed approval cannot read'))
    r = execute(client, action)
    assert r.status_code == 409 or r.json()['state'] == 'failed'
    from tests.test_item_edit import protocol as version_protocol
    v2 = version_protocol()
    v2['invariant_mappings'][0]['transform'] = 'identity'
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=v2).status_code == 422


@pytest.mark.parametrize('change,state', [('before', 'failed'), ('after', 'unconfirmed')])
def test_transformed_source_changes_never_normalized_away(workbench, monkeypatch, change, state):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', transformed_transport(events, change))
    assert execute(client, action).json()['state'] == state


@pytest.mark.parametrize('bad', ['bool_type', 'bool_case', 'unknown', 'wrong_path', 'image_empty', 'image_many',
    'image_extra', 'extra_info_extra', 'dimension_zero', 'dimension_int', 'dimension_float', 'dimension_unicode',
    'major_bool', 'image_type', 'shipping_fee', 'shipping_idle', 'shipping_template', 'shipping_extra',
    'shipping_flags', 'category_true', 'category_extra', 'category_type', 'request_mismatch', 'identity', 'labels'])
def test_transform_evidence_rejects_unproved_shapes(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    source = p['before']['edit']
    image = source['imageInfoDOList'][0]
    if bad == 'bool_type':
        source['freebies'] = False
    elif bad == 'bool_case':
        source['freebies'] = 'False'
    elif bad == 'unknown':
        p['invariant_mappings'][-1]['transform'] = 'eval(source)'
    elif bad == 'wrong_path':
        p['invariant_mappings'][-1]['request_path'] = ['images']
    elif bad == 'image_empty':
        source['imageInfoDOList'] = []
    elif bad == 'image_many':
        source['imageInfoDOList'].append(deepcopy(image))
    elif bad == 'image_extra':
        image['unknown'] = 'do not drop'
    elif bad == 'extra_info_extra':
        image['extraInfo']['unknown'] = 'do not drop'
    elif bad == 'dimension_zero':
        image['widthSize'] = '0'
    elif bad == 'dimension_int':
        image['widthSize'] = 640
    elif bad == 'dimension_float':
        image['widthSize'] = '640.0'
    elif bad == 'dimension_unicode':
        image['widthSize'] = '６４０'
    elif bad == 'major_bool':
        image['major'] = True
    elif bad == 'image_type':
        image['type'] = '1'
    elif bad == 'shipping_fee':
        source['itemPostFeeDTO']['postPriceInCent'] = '1'
    elif bad == 'shipping_idle':
        source['itemPostFeeDTO']['idleTemplateId'] = '1'
    elif bad == 'shipping_template':
        source['itemPostFeeDTO']['templateId'] = '1'
    elif bad == 'shipping_extra':
        source['itemPostFeeDTO']['unknown'] = 'do not drop'
    elif bad == 'shipping_flags':
        source['itemPostFeeDTO']['onlyTakeSelf'] = 'true'
    elif bad == 'category_true':
        source['itemCatDTO']['sugShow'] = 'true'
    elif bad == 'category_extra':
        source['itemCatDTO']['unknown'] = 'do not drop'
    elif bad == 'category_type':
        source['itemCatDTO']['catId'] = 1
    elif bad == 'request_mismatch':
        p['template']['imageInfoDOList'][0]['thumbnail'] = 'other'
    elif bad == 'identity':
        p['invariant_mappings'][-1]['transform'] = 'identity'
    else:
        p['template']['itemLabelExtList'] = [{'unproved': None}]
        source['itemLabelExtList'] = [{'unproved': ''}]
        p['invariant_mappings'].append({'request_path': ['itemLabelExtList'], 'before_path': ['edit', 'itemLabelExtList'],
                                        'transform': 'labels_v1', 'evidence': 'Unproved fictional label mapping'})
    p['original_request'] = deepcopy(p['template'])
    p['before_content_hash'] = digest(p['before'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422
