"""Observed common is a label type; category semantics remain propertyId=-10000."""
from copy import deepcopy
from itertools import count

import pytest

from tests import test_edit_labels as labels
from tests.test_edit_snapshot import ready
from tests.test_item_edit import execute
from tests.test_workbench import account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.edit_snapshot import SnapshotProtocol
from xianyu_workbench.security import digest


def common_protocol():
    p = labels.protocol()
    dep = p['label_dependency']
    dep['observed_label_type'] = 'common'
    p['before']['edit']['itemLabelExtList'][0]['labelType'] = 'common'
    p['template']['itemLabelExtList'][0]['labelType'] = 'common'
    for response in dep['responses']:
        value = response['data']['cardList'][0]['cardData']['valuesList'][0]
        value['labelType'] = value['transportData']['labelType'] = 'common'
    dep['requests'][0]['selectedList'][0]['labelType'] = 'common'
    dep['requests'][1]['selectedList'][0]['labelType'] = 'common'
    dep['requests'][1]['currentCardList'] = [deepcopy(dep['responses'][0]['data']['cardList'][0]['cardData'])]
    p['original_request'] = deepcopy(p['template'])
    p['before_content_hash'] = digest(p['before'])
    return p


@pytest.mark.parametrize('bad_read', [False, True])
def test_common_roundtrip_and_revalidation(workbench, monkeypatch, bad_read):
    client, service = workbench
    p = common_protocol()
    codes = count(1700000040000000)
    monkeypatch.setattr('xianyu_workbench.edit_snapshot.unique_code', lambda: str(next(codes)))
    _, action, _ = ready(client, service, p)
    monkeypatch.setattr(labels, 'protocol', lambda: deepcopy(p))
    fake = labels.label_transport([])
    events = []
    def call(account, op, payload, **kw):
        events.append(op)
        result = fake(account, op, payload, **kw)
        if bad_read and op == 'edit.recommend':
            result['data']['cardList'][0]['cardData']['valuesList'][0]['labelType'] = 'category'
        return result
    monkeypatch.setattr(service.provider, '_live', call)
    assert execute(client, action).json()['state'] == ('failed' if bad_read else 'submitted')
    assert events.count('edit.submit') == (0 if bad_read else 1)
    frozen = service.vault.open(service.db.one('SELECT payload FROM actions WHERE id=?', (action['id'],))['payload'])
    assert frozen['_edit_snapshot']['protocol']['label_dependency']['observed_label_type'] == 'common'


@pytest.mark.parametrize('where', ['old', 'selected', 'transport', 'request'])
@pytest.mark.parametrize('bad', ['category', 'unknown', None, 1, {'nested': 'common'}])
def test_four_sources_cannot_mix_or_coerce(workbench, where, bad):
    client, _ = workbench
    aid = account(client, 'live', '{"unb":"12345","_m_h5_tk":"fictional_1"}')
    p = common_protocol()
    value = p['label_dependency']['responses'][0]['data']['cardList'][0]['cardData']['valuesList'][0]
    target = {'old': p['before']['edit']['itemLabelExtList'][0], 'selected': value,
              'transport': value['transportData'], 'request': p['template']['itemLabelExtList'][0]}[where]
    target['labelType'] = bad
    p['before_content_hash'] = digest(p['before'])
    p['original_request'] = deepcopy(p['template'])
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=p).status_code == 422


@pytest.mark.parametrize('bad', ['COMMON', '', 'other', None, True, ['common']])
def test_observed_enum_is_closed(bad):
    p = common_protocol()
    p['label_dependency']['observed_label_type'] = bad
    with pytest.raises(ValueError):
        SnapshotProtocol.model_validate(p)


def test_old_category_default_and_explicit_common_required():
    p = labels.protocol()
    parsed = SnapshotProtocol.model_validate(p)
    assert parsed.label_dependency.observed_label_type == 'category'
    p = common_protocol()
    del p['label_dependency']['observed_label_type']
    with pytest.raises(ValueError):
        SnapshotProtocol.model_validate(p)


def test_type_change_invalidates_old_approval(workbench, monkeypatch):
    client, service = workbench
    codes = count(1700000050000000)
    monkeypatch.setattr('xianyu_workbench.edit_snapshot.unique_code', lambda: str(next(codes)))
    aid, action, _ = ready(client, service, labels.protocol())
    assert client.put(f'/api/accounts/{aid}/edit-protocol', json=common_protocol()).status_code == 200
    monkeypatch.setattr(service.provider, '_live', lambda *a, **kw: pytest.fail('stale approval must not read'))
    r = execute(client, action)
    assert r.status_code == 409 or r.json()['state'] == 'failed'
