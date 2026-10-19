"""Fictional coordinates only; latitude precedes longitude."""
import pytest
from pydantic import ValidationError

from tests.test_publish_preview import DEFAULTS
from tests.test_workbench import account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.provider import Problem
from xianyu_workbench.publish_preview import Location, defaults


@pytest.mark.parametrize('gps', ['30.123456,120.654321', '-90,-180', '90,180', '0,0', '-0.000000,001.2300'])
def test_latlon_preserves_exact_string(gps):
    assert Location.model_validate({**DEFAULTS['location'], 'gps': gps}).gps == gps


@pytest.mark.parametrize('gps', ['120.1,30.2', '90.000001,0', '-90.1,0', '0,180.000001', '0,-181',
                               '000,0', '0,0000', 'NaN,0', '0,Infinity', '1e1,2', '+1,2',
                               '1, 2', ' 1,2', '1,2\n', '.1,2', '1.,2', '1,2,3', '１,２'])
def test_invalid_latlon_rejected(gps):
    with pytest.raises(ValidationError):
        Location.model_validate({**DEFAULTS['location'], 'gps': gps})


def test_api_freezes_original_latlon_without_normalization(workbench):
    from tests.test_publish_preview import setup_preview
    client, service = workbench
    aid = account(client)
    _, body = setup_preview(client, aid)
    gps = '-0.000000,001.2300'
    config = {**DEFAULTS, 'location': {**DEFAULTS['location'], 'gps': gps}}
    response = client.put(f'/api/accounts/{aid}/publish-defaults', json=config)
    assert response.status_code == 200
    assert response.json()['location']['gps'] == gps
    body['idempotency_key'] = 'exact-gps-fixture'
    action = client.post('/api/publish-preview', json=body).json()
    assert action['payload']['_publish_snapshot']['candidate']['itemAddrDTO']['gps'] == gps
    assert defaults(service, aid)['location']['gps'] == gps


def test_legacy_lonlat_action_cannot_upload(workbench, monkeypatch):
    from tests.test_publish_executor import execute, ready
    client, service = workbench
    aid, action = ready(client, service)
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('publish-defaults:' + aid,))
    config = service.vault.open(row['value'])
    config['location']['gps'] = '120.1,30.2'
    service.db.execute('UPDATE settings SET value=? WHERE key=?', (service.vault.seal(config), 'publish-defaults:' + aid))
    monkeypatch.setattr(service.provider, '_live', lambda *a, **k: pytest.fail('invalid legacy coordinates must not upload'))
    assert execute(client, action).json()['state'] == 'failed'


def test_old_persisted_lonlat_rejected_before_freezing(workbench):
    client, service = workbench
    aid = account(client)
    service.db.execute('INSERT INTO settings VALUES(?,?)', ('publish-defaults:' + aid,
        service.vault.seal({**DEFAULTS, 'location': {**DEFAULTS['location'], 'gps': '120.1,30.2'}, 'revision': 'old'})))
    with pytest.raises(Problem) as exc:
        defaults(service, aid)
    assert exc.value.code == 'publish_location_reapproval_required'
