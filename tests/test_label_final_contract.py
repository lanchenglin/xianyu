from copy import deepcopy

import pytest

from tests.test_edit_labels import protocol
from tests.test_workbench import account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.security import digest


def real_shape():
    p = protocol()
    edit = p['before']['edit']
    del edit['itemSkuList'], edit['itemProperties']
    edit['itemSkuExtra'] = {}
    p['before_content_hash'] = digest(p['before'])
    dep = p['label_dependency']
    dep.update(sku_source_mode='missing_with_empty_extra', card_source_mode='fill_missing_unselected')
    for response in dep['responses']:
        response['data']['cardList'][0]['cardData']['valuesList'].append({'isUserClick': '0', 'opaque': 'preserve'})
    dep['requests'][1]['currentCardList'] = [deepcopy(dep['responses'][0]['data']['cardList'][0]['cardData'])]
    dep['requests'][1]['currentCardList'][0]['valuesList'][1]['isClicked'] = '0'
    return p


def test_explicit_real_missing_sku_and_card_fill_are_accepted(workbench):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    r = client.put(f'/api/accounts/{aid}/edit-protocol', json=real_shape())
    assert r.status_code == 200, r.text


@pytest.mark.parametrize('bad', ['extra', 'present', 'null', 'selected_missing', 'mutate', 'mode', 'sku_mode'])
def test_real_modes_reject_contradictory_sources(workbench, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = real_shape()
    dep = p['label_dependency']
    if bad == 'extra':
        p['before']['edit']['itemSkuExtra'] = {'sku': True}
    elif bad == 'present':
        p['before']['edit']['itemSkuList'] = []
    elif bad == 'null':
        dep['responses'][0]['data']['cardList'][0]['cardData']['valuesList'][1]['isClicked'] = None
    elif bad == 'selected_missing':
        dep['responses'][0]['data']['cardList'][0]['cardData']['valuesList'][1]['isUserClick'] = '1'
    elif bad == 'mutate':
        dep['requests'][1]['currentCardList'][0]['valuesList'][1]['opaque'] = 'changed'
    elif bad == 'mode':
        dep['card_source_mode'] = 'identity'
    else:
        dep['sku_source_mode'] = 'explicit_empty_arrays'
    p['before_content_hash'] = digest(p['before'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422
