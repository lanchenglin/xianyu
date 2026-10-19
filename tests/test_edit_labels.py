"""Fictional single-category dependency; no platform calls."""
from copy import deepcopy

import pytest

from tests.test_edit_snapshot import ready
from tests.test_edit_transforms import protocol as base_protocol
from tests.test_edit_transforms import transformed_transport
from tests.test_item_edit import execute
from tests.test_workbench import AGENT, account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import digest


@pytest.fixture(autouse=True)
def deterministic_codes(monkeypatch):
    from itertools import count
    codes = count(1700000001000000)
    monkeypatch.setattr('xianyu_workbench.edit_snapshot.unique_code', lambda: str(next(codes)))


def protocol():
    p = base_protocol()
    category = p['before']['edit']['itemCatDTO']
    old = {'valueId': '2', 'channelCateId': '2', 'labelId': '', 'isUserClick': '1', 'labelType': 'category',
           'from': 'fixture', 'text': 'fictional', 'propertyId': '-10000', 'properties': '-10000##类目:2##fictional'}
    td = {'channelCateName': 'fictional', 'valueId': None, 'channelCateId': '2', 'valueName': None,
          'tbCatId': '3', 'subPropertyId': None, 'labelType': 'category', 'subValueId': None,
          'labelId': None, 'propertyName': '类目', 'isUserClick': '1', 'isUserCancel': None,
          'from': 'fixture', 'propertyId': '-10000', 'labelFrom': 'fixture'}
    label = {**td, 'text': 'fictional', 'properties': '-10000##类目:2##fictional'}
    selected = {**{k: category[k] for k in ('catId', 'catName', 'channelCatId', 'tbCatId')},
                'propertyId': '-10000', 'propertyName': '类目', 'labelType': 'category',
                'isClicked': '1', 'isUserClick': '1', 'transportData': td}
    cards = [{'cardData': {'propertyId': '-10000', 'propertyName': '类目', 'valuesList': [selected]}}]
    response = {'ret': ['SUCCESS::调用成功'], 'data': {'cardList': cards}}
    common = {'title': p['before_values']['desc'], 'description': p['before_values']['desc'],
              'imageInfos': deepcopy(p['template']['imageInfoDOList']),
              **{k: category[k] for k in ('catId', 'catName', 'channelCatId')},
              'lockCpv': False, 'multiSKU': False, 'publishScene': 'mainPublish', 'scene': 'newPublishChoice'}
    requests = [{**common, 'currentCardList': [], 'selectedList': [{**old, 'valueName': 'fictional'}], 'uniqueCode': '1700000000000111'},
                {**common, 'currentCardList': [cards[0]['cardData']], 'selectedList': [label], 'uniqueCode': '1700000000000222'}]
    p['before']['edit'].update(itemLabelExtList=[old], itemSkuList=[], itemProperties=[])
    p['template']['itemLabelExtList'] = [label]
    p['original_request'] = deepcopy(p['template'])
    p['before_content_hash'] = digest(p['before'])
    p['label_dependency'] = {'mode': 'single_category_v1', 'requests': requests, 'responses': [response, deepcopy(response)],
                             'unique_code_mode': 'timestamp_random', 'evidence': 'Fictional exact dependency evidence'}
    return p


def label_transport(events, change=None):
    fake = transformed_transport(events)
    def call(account, op, payload, **kwargs):
        if op == 'edit.recommend':
            events.append(op)
            i = events.count(op) - 1
            assert kwargs['write'] is False
            assert payload['api_version'] == '2.0'
            expected = deepcopy(protocol()['label_dependency']['requests'][i])
            expected['uniqueCode'] = payload['template']['uniqueCode']
            assert payload['template'] == expected
            result = deepcopy(protocol()['label_dependency']['responses'][i])
            if change == 'ret':
                result['ret'] = ['FAIL::fixture']
            if change == 'label':
                result['data']['cardList'][0]['cardData']['valuesList'][0]['transportData']['from'] = 'changed'
            if change == 'timeout':
                raise TimeoutError()
            return result
        result = fake(account, op, payload, **kwargs)
        if op == 'edit.read':
            for k in ('itemLabelExtList', 'itemSkuList', 'itemProperties'):
                result['data'][k] = deepcopy(protocol()['before']['edit'][k])
        return result
    return call


def test_label_dependency_revalidated_before_single_edit_and_private(workbench, monkeypatch):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', label_transport(events))
    assert execute(client, action).json()['state'] == 'submitted'
    assert events == ['edit.detail', 'edit.read', 'edit.recommend', 'edit.recommend', 'edit.detail', 'edit.read', 'edit.submit', 'edit.detail', 'edit.read']
    admin = client.get('/api/actions/' + action['id']).json()
    assert len(admin['result']['label_dependency_reads']) == 2
    agent = client.get('/api/actions/' + action['id'], headers={'Authorization': 'Bearer ' + AGENT}).json()
    assert 'label_dependency_reads' not in agent['result']
    assert 'transportData' not in str(agent)


@pytest.mark.parametrize('change', ['ret', 'label', 'timeout'])
def test_dependency_failure_never_submits(workbench, monkeypatch, change):
    client, service = workbench
    _, action, _ = ready(client, service, protocol())
    events = []
    monkeypatch.setattr(service.provider, '_live', label_transport(events, change))
    assert execute(client, action).json()['state'] == 'failed'
    assert events.count('edit.recommend') == 1
    assert 'edit.submit' not in events
    audit = service.db.one('SELECT value FROM settings WHERE key=?', ('edit-label-audit:' + action['id'],))
    assert audit
    private = service.vault.open(audit['value'])
    assert private['stage'] == 'failed'
    assert len(private['reads']) == (0 if change == 'timeout' else 1)


def test_recommend_provider_requires_exact_frozen_selected_action(workbench):
    from xianyu_workbench.edit_labels import frozen_requests
    from xianyu_workbench.provider import Problem
    client, service = workbench
    aid, action, _ = ready(client, service, protocol())
    acct = service.provider.account(aid)
    with pytest.raises(Problem):
        service.provider._live(acct, 'edit.recommend', {}, write=False)
    service.db.execute("UPDATE actions SET state='running' WHERE id=?", (action['id'],))
    frozen = service.vault.open(service.db.one('SELECT payload FROM actions WHERE id=?', (action['id'],))['payload'])['_edit_snapshot']
    request = frozen_requests(frozen['protocol'], frozen['label_codes'])[0]
    request['description'] = 'not-approved'
    service.provider._selected.edit_action = action['id']
    with pytest.raises(Problem, match='冻结审批'):
        service.provider._live(acct, 'edit.recommend', {'item_id': '777', 'api_version': '2.0', 'template': request}, write=False)


@pytest.mark.parametrize('bad', ['selected_scalar', 'data_scalar', 'card_scalar', 'category_null', 'missing_image', 'missing_label'])
def test_malformed_dependency_is_422_not_server_error(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    if bad == 'selected_scalar':
        p['label_dependency']['requests'][0]['selectedList'] = [None]
    elif bad == 'data_scalar':
        p['label_dependency']['responses'][0]['data'] = []
    elif bad == 'category_null':
        p['before']['edit']['itemCatDTO'] = None
        p['before_content_hash'] = digest(p['before'])
    elif bad == 'missing_image':
        del p['template']['imageInfoDOList']
        p['original_request'] = deepcopy(p['template'])
    elif bad == 'missing_label':
        del p['template']['itemLabelExtList']
        p['original_request'] = deepcopy(p['template'])
    else:
        p['label_dependency']['responses'][0]['data']['cardList'] = [None]
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


@pytest.mark.parametrize('bad', ['desc', 'image', 'category', 'controls', 'selected', 'code', 'two_labels', 'sku', 'missing_sku', 'transport', 'extra_selected', 'second_cards', 'size'])
def test_dependency_contract_binds_all_sources(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = protocol()
    dep = p['label_dependency']
    if bad == 'desc':
        dep['requests'][0]['title'] = 'short title'
    elif bad == 'image':
        dep['requests'][0]['imageInfos'] = []
    elif bad == 'category':
        dep['requests'][0]['catId'] = '999'
    elif bad == 'controls':
        dep['requests'][0]['multiSKU'] = True
    elif bad == 'selected':
        dep['requests'][0]['selectedList'][0]['valueName'] = 'guessed'
    elif bad == 'code':
        dep['requests'][0]['uniqueCode'] = 'unknown'
    elif bad == 'two_labels':
        p['before']['edit']['itemLabelExtList'] *= 2
    elif bad == 'sku':
        p['before']['edit']['itemSkuList'] = [{'price': '1'}]
    elif bad == 'missing_sku':
        del p['before']['edit']['itemSkuList']
    elif bad == 'transport':
        del dep['responses'][0]['data']['cardList'][0]['cardData']['valuesList'][0]['transportData']['valueId']
    elif bad == 'extra_selected':
        card = dep['responses'][0]['data']['cardList'][0]
        card['cardData']['valuesList'].append(deepcopy(card['cardData']['valuesList'][0]))
    elif bad == 'second_cards':
        dep['requests'][1]['currentCardList'] = []
    else:
        dep['responses'][0]['data']['extra'] = 'x' * 70000
    p['before_content_hash'] = digest(p['before'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422
