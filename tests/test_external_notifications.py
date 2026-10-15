import json
import socket

import pytest
from test_workbench import AGENT
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_transport_has_absolute_deadline(monkeypatch):
    import threading
    import time

    from xianyu_workbench import notifications
    closed = threading.Event()
    class Connection:
        sock = None
        def __init__(self, *args):
            self.sock = self
        def request(self, *args):
            pass
        def getresponse(self):
            self.sock = None  # HTTPConnection detaches the socket for Connection: close responses.
            return type('Response', (), {'status': 204, 'read': lambda self, n: closed.wait(.5) and b''})()
        def shutdown(self, how):
            closed.set()
        def close(self):
            pass
    monkeypatch.setattr(notifications, 'public_address', lambda host: '93.184.216.34')
    monkeypatch.setattr(notifications, 'PinnedHTTPS', Connection)
    monkeypatch.setattr(notifications, 'DELIVERY_TIMEOUT', .02, raising=False)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        notifications.send({'kind': 'webhook', 'url': 'https://notify.example.com/h', 'secret': 's' * 40}, {}, 'd')
    assert time.monotonic() - start < .4


def test_dns_resolution_has_bounded_wait(monkeypatch):
    import threading

    from xianyu_workbench.notifications import public_address
    done = threading.Event()
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: done.wait(2))
    try:
        with pytest.raises(TimeoutError):
            public_address('notify.example.com', timeout=.01)
    finally:
        done.set()


@pytest.mark.parametrize('status,data,kind', [(302, b'', 'webhook'), (500, b'', 'webhook'),
                                             (200, b'{"errcode":310000}', 'dingtalk'),
                                             (200, b'x' * 65537, 'webhook')])
def test_transport_rejects_redirect_errors_and_oversized_body(monkeypatch, status, data, kind):
    from xianyu_workbench.notifications import send
    class Connection:
        def __init__(self, *args):
            pass
        def request(self, *args):
            pass
        def getresponse(self):
            return type('Response', (), {'status': status, 'read': lambda self, n: data})()
        def close(self):
            pass
    monkeypatch.setattr('xianyu_workbench.notifications.public_address', lambda host: '93.184.216.34')
    monkeypatch.setattr('xianyu_workbench.notifications.PinnedHTTPS', Connection)
    url = 'https://notify.example.com/events' if kind == 'webhook' else 'https://oapi.dingtalk.com/robot/send?access_token=' + 'a' * 64
    with pytest.raises(ValueError):
        send({'kind': kind, 'url': url, 'secret': 's' * 40}, {'text': 'notice', 'notification_id': 1}, 'd')


def test_retry_stops_after_three_attempts(workbench, monkeypatch):
    client, service = workbench
    client.put('/api/notifications/config', json={'kind': 'webhook', 'url': 'https://notify.example.com/h',
                                                'secret': 's' * 40, 'enabled': True})
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('x','{}',1)")
    def fail(*args):
        raise TimeoutError()
    monkeypatch.setattr('xianyu_workbench.notifications.send', fail)
    for _ in range(3):
        service.db.execute('UPDATE notification_deliveries SET next_attempt=0')
        assert service.notifications.run_once()
    service.db.execute('UPDATE notification_deliveries SET next_attempt=0')
    assert not service.notifications.run_once()
    assert service.db.one('SELECT state,attempts FROM notification_deliveries') == {'state': 'failed', 'attempts': 3}


def test_admin_can_disable_without_resubmitting_secret(workbench):
    client, service = workbench
    body = {'kind': 'webhook', 'url': 'https://notify.example.com/events', 'secret': 's' * 40, 'enabled': True}
    client.put('/api/notifications/config', json=body)
    assert client.post('/api/notifications/disable', headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert client.post('/api/notifications/disable').status_code == 200
    assert service.notifications.status()['enabled'] is False


def test_recover_marks_inflight_unknown_and_disable_cancels_retry(workbench):
    client, service = workbench
    body = {'kind': 'webhook', 'url': 'https://notify.example.com/events', 'secret': 's' * 40, 'enabled': True}
    client.put('/api/notifications/config', json=body)
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('x','{}',1)")
    service.db.execute("INSERT INTO notification_deliveries VALUES('d',1,'sending',1,0,1,NULL)")
    service.recover()
    assert service.db.one('SELECT state FROM notification_deliveries')['state'] == 'unknown'
    service.db.execute("UPDATE notification_deliveries SET state='retry'")
    client.put('/api/notifications/config', json={**body, 'enabled': False})
    assert service.db.one('SELECT state FROM notification_deliveries')['state'] == 'cancelled'
    assert not service.notifications.run_once()


def test_worker_runs_notification_delivery(workbench, monkeypatch):
    _, service = workbench
    sent = []
    monkeypatch.setattr(service, 'run_once', lambda: False)
    monkeypatch.setattr(service, 'monitor_once', lambda: False)
    def deliver():
        sent.append(True)
        service.stop.set()
    monkeypatch.setattr(service.notifications, 'run_once', deliver)
    import threading
    worker = threading.Thread(target=service.loop, daemon=True)
    worker.start()
    worker.join(3)
    service.stop.set()
    worker.join(3)
    assert sent == [True]


def test_webhook_policy_rejects_unsafe_destinations():
    from xianyu_workbench.notifications import validate_url
    for url in ('http://example.com/h', 'https://127.0.0.1/h', 'https://[::1]/h',
                'https://user:password@example.com/h', 'https://example.com:8443/h',
                'https://example.com/h#fragment', 'https://example.com/h?token=secret',
                'https://localhost/h', 'https://169.254.169.254/h', 'https://example.com/\n'):
        with pytest.raises(ValueError):
            validate_url('webhook', url)
    assert validate_url('webhook', 'https://notify.example.com/events').hostname == 'notify.example.com'
    assert validate_url('dingtalk', 'https://oapi.dingtalk.com/robot/send?access_token=' + 'a' * 64)
    with pytest.raises(ValueError):
        validate_url('dingtalk', 'https://evil.example/robot/send?access_token=' + 'a' * 64)


def test_signed_delivery_pins_address_and_checks_response(monkeypatch):
    import hashlib
    import hmac

    from xianyu_workbench.notifications import send
    calls = []

    class Connection:
        def __init__(self, host, address):
            assert host == 'notify.example.com' and address == '93.184.216.34'
        def request(self, method, path, body, headers):
            calls.append((method, path, body, headers))
        def getresponse(self):
            return type('Response', (), {'status': 204, 'read': lambda self, n: b''})()
        def close(self):
            pass
    monkeypatch.setattr('xianyu_workbench.notifications.public_address', lambda host: '93.184.216.34')
    monkeypatch.setattr('xianyu_workbench.notifications.PinnedHTTPS', Connection)
    send({'kind': 'webhook', 'url': 'https://notify.example.com/events', 'secret': 's' * 40},
         {'text': 'notice'}, 'delivery-1')
    method, path, body, headers = calls[0]
    assert method == 'POST' and path == '/events'
    assert headers['X-Delivery-ID'] == 'delivery-1'
    expected = hmac.new(b's' * 40, headers['X-Timestamp'].encode() + b'\n' + body, hashlib.sha256).hexdigest()
    assert headers['X-Signature-SHA256'] == expected


def test_dns_all_answers_must_be_public(monkeypatch):
    from xianyu_workbench.notifications import public_address
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))])
    with pytest.raises(ValueError):
        public_address('notify.example.com')


def test_admin_config_encrypted_disabled_by_default_and_never_echoed(workbench):
    client, service = workbench
    assert client.get('/api/notifications/config').json() == {'configured': False, 'enabled': False}
    body = {'kind': 'webhook', 'url': 'https://notify.example.com/events',
            'secret': 's' * 40, 'enabled': True}
    assert client.put('/api/notifications/config', json=body, headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    assert client.get('/api/notifications/config', headers={'Authorization': 'Bearer ' + AGENT}).status_code == 403
    response = client.put('/api/notifications/config', json=body)
    assert response.status_code == 200
    status = client.get('/api/notifications/config').json()
    assert status['enabled'] is True and status['kind'] == 'webhook'
    assert 'url' not in status and 'secret' not in status
    stored = service.db.one("SELECT value FROM settings WHERE key='notifications'")['value']
    assert body['secret'] not in stored and body['url'] not in stored
    assert body['secret'] not in client.get('/api/audit').text


def test_outbox_only_new_notifications_dedup_retry_and_no_business_replay(workbench, monkeypatch):
    from xianyu_workbench.notifications import Delivery
    client, service = workbench
    body = {'kind': 'webhook', 'url': 'https://notify.example.com/events', 'secret': 's' * 40, 'enabled': True}
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('old','{}',1)")
    assert client.put('/api/notifications/config', json=body).status_code == 200
    delivery = Delivery(service.db, service.vault)
    assert delivery.run_once() is False  # Never export historical notifications on enable.
    service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('new',?,2)",
                       (json.dumps({'secret': 'private-chat-address', 'items': [1]}),))
    received = []

    def send(config, payload, delivery_id):
        received.append((payload, delivery_id))
        if len(received) == 1:
            raise TimeoutError('do-not-leak-url-or-secret')
    monkeypatch.setattr('xianyu_workbench.notifications.send', send)
    assert delivery.run_once()
    row = service.db.one('SELECT * FROM notification_deliveries')
    assert row['state'] == 'retry' and row['attempts'] == 1
    assert not delivery.run_once()
    service.db.execute('UPDATE notification_deliveries SET next_attempt=0')
    assert Delivery(service.db, service.vault).run_once()
    assert not delivery.run_once()
    assert len(received) == 2 and received[0] == received[1]
    assert 'private-chat-address' not in json.dumps(received)
    assert service.db.one('SELECT state FROM notification_deliveries')['state'] == 'delivered'
    assert service.db.one('SELECT COUNT(*) n FROM actions')['n'] == 0
    logs = client.get('/api/notifications/deliveries', headers={'Authorization': 'Bearer ' + AGENT})
    assert logs.status_code == 200 and 'do-not-leak' not in logs.text and body['url'] not in logs.text
