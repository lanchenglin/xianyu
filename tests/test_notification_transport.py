"""Real local TLS receiver, with only DNS/routing/trust replaced at the network boundary."""
import datetime
import hashlib
import hmac
import http.server
import json
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_isolated_tls_delivery_through_real_worker_service(tmp_path, monkeypatch, workbench):
    from xianyu_workbench import notifications
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'notify.example.com')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('notify.example.com')]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            received.append((self.path, dict(self.headers), body))
            self.send_response(204)
            self.end_headers()
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_connect = socket.create_connection
    original_context = ssl.create_default_context
    targets = []

    def connect(address, timeout):
        targets.append(address)
        assert address == ('93.184.216.34', 443)
        return original_connect(server.server_address, timeout=timeout)
    monkeypatch.setattr(notifications, 'public_address', lambda host: '93.184.216.34')
    monkeypatch.setattr(socket, 'create_connection', connect)
    monkeypatch.setattr(ssl, 'create_default_context', lambda: original_context(cafile=str(cert_file)))
    client, service = workbench
    try:
        response = client.put('/api/notifications/config', json={'kind': 'webhook',
                              'url': 'https://notify.example.com/events', 'secret': 's' * 40, 'enabled': True})
        assert response.status_code == 200
        service.db.execute("INSERT INTO notifications(monitor_id,content,created) VALUES('x',?,1)",
                           (json.dumps({'private': 'not-exported'}),))
        assert service.notifications.run_once()
        assert not service.notifications.run_once()
        assert service.db.one('SELECT state FROM notification_deliveries')['state'] == 'delivered'
        assert targets == [('93.184.216.34', 443)]
        path, headers, body = received[0]
        assert path == '/events' and headers['Host'] == 'notify.example.com'
        assert b'not-exported' not in body
        expected = hmac.new(b's' * 40, headers['X-Timestamp'].encode() + b'\n' + body, hashlib.sha256).hexdigest()
        assert headers['X-Signature-SHA256'] == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
