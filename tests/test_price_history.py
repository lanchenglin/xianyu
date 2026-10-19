import pytest
from test_workbench import account
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_prices_fresh_missing_stale_and_no_business_write(workbench):
    from xianyu_workbench.price_history import observe
    client, service = workbench
    aid = account(client)
    mid = client.post('/api/monitors', json={'account_id': aid, 'query': 'fiction'}).json()['id']
    monitor = service.db.one('SELECT * FROM monitors WHERE id=?', (mid,))
    def sample(price, now):
        observe(service, monitor, {'items': [{'item_id': '123', 'price': price}], 'fetched_at': now, 'mode': 'demo'}, now=now)
    sample('100', 100000)
    sample('90', 100100)
    sample('90', 100100)
    assert service.db.one('SELECT COUNT(*) n FROM notifications')['n'] == 1
    sample(None, 100200)
    sample('80', 100300)
    sample('70', 200000)
    sample('NaN', 200100)
    sample('60', 200200)
    assert service.db.one('SELECT COUNT(*) n FROM notifications')['n'] == 1
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0
    result = client.get(f'/api/accounts/{aid}/price-history?monitor_id={mid}').json()
    assert result['items'][0]['price'] == '60.00'
    other = account(client)
    assert client.get(f'/api/accounts/{other}/price-history?monitor_id={mid}').status_code == 409
    observe(service, monitor, {'items': [], 'fetched_at': 200300, 'mode': 'demo'}, now=200300)
    sample('50', 200400)
    assert service.db.one('SELECT COUNT(*) n FROM notifications')['n'] == 1
    observe(service, monitor, {'items': [{'item_id': '123', 'price': '1'}],
                              'fetched_at': 200500, 'mode': 'demo'}, now=201000)
    assert service.db.one('SELECT COUNT(*) n FROM notifications')['n'] == 1
