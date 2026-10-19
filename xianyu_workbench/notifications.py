"""Opt-in minimal notifications; no marketplace operations or user content exported."""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

from .security import canonical, strict_json


def validate_url(kind, url):
    if any(ord(c) <= 32 or ord(c) >= 127 for c in url) or '\\' in url:
        raise ValueError('invalid_destination')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError('invalid_destination')
    host = parsed.hostname
    if not re.fullmatch(r'[a-z0-9.-]+', host) or '.' not in host or host.endswith('.'):
        raise ValueError('invalid_destination')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('invalid_destination')
    if kind == 'dingtalk':
        query = parse_qs(parsed.query, strict_parsing=True)
        if (host != 'oapi.dingtalk.com' or parsed.path != '/robot/send'
                or set(query) != {'access_token'} or len(query['access_token']) != 1
                or not re.fullmatch(r'[a-zA-Z0-9]{32,128}', query['access_token'][0])):
            raise ValueError('invalid_destination')
    elif kind != 'webhook' or parsed.query:
        raise ValueError('invalid_destination')
    return parsed


_dns_slot = threading.BoundedSemaphore(1)


def public_address(host, timeout=5):
    # A stalled system resolver must not stall the business worker or spawn unbounded threads.
    if not _dns_slot.acquire(blocking=False):
        raise TimeoutError('resolver_busy')
    ready = threading.Event()
    result = []

    def resolve():
        try:
            result.append(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except Exception:
            result.append(None)
        finally:
            _dns_slot.release()
            ready.set()

    threading.Thread(target=resolve, daemon=True, name='notification-dns').start()
    if not ready.wait(timeout):
        raise TimeoutError('resolver_timeout')
    addresses = result[0]
    if not addresses:
        raise ValueError('invalid_destination')
    for entry in addresses:
        addr = ipaddress.ip_address(entry[4][0])
        if (not addr.is_global or addr.is_multicast
                or (isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped)):
            raise ValueError('invalid_destination')
    return addresses[0][4][0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, 443, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Only the validated numeric address is resolved here; TLS still verifies the original host.
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


DELIVERY_TIMEOUT = 15


def send(config, payload, delivery_id):
    parsed = validate_url(config['kind'], config['url'])
    address = public_address(parsed.hostname)
    stamp = str(int(time.time() * 1000))
    secret = config['secret'].encode()
    path = parsed.path or '/'
    headers = {'Content-Type': 'application/json', 'X-Delivery-ID': delivery_id, 'X-Timestamp': stamp}
    if config['kind'] == 'dingtalk':
        signature = base64.b64encode(hmac.new(secret, stamp.encode() + b'\n' + secret, hashlib.sha256).digest()).decode()
        path += '?' + parsed.query + '&' + urlencode({'timestamp': stamp, 'sign': signature})
        payload = {'msgtype': 'text', 'text': {'content': payload['text'] + ' 通知编号：' + str(payload['notification_id'])}}
    body = canonical(payload).encode()
    headers['X-Signature-SHA256'] = hmac.new(secret, stamp.encode() + b'\n' + body, hashlib.sha256).hexdigest()
    conn = PinnedHTTPS(parsed.hostname, address)
    expired = threading.Event()
    transport_socket = None
    response = None

    def abort():
        expired.set()
        active_socket = transport_socket or conn.sock
        if active_socket:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    deadline = threading.Timer(DELIVERY_TIMEOUT, abort)
    deadline.daemon = True
    deadline.start()
    try:
        conn.request('POST', path, body, headers)
        transport_socket = getattr(conn, 'sock', None)
        response = conn.getresponse()
        data = response.read(65537)
        if expired.is_set():
            raise TimeoutError('delivery_timeout')
        if len(data) > 65536 or not 200 <= response.status < 300:
            raise ValueError('delivery_failed')
        if config['kind'] == 'dingtalk' and strict_json(data).get('errcode') != 0:
            raise ValueError('delivery_failed')
    finally:
        deadline.cancel()
        deadline.join()
        if response is not None:
            response.close()
        conn.close()


class Delivery:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault
        self.lock = threading.RLock()

    def status(self):
        row = self.db.one("SELECT value FROM settings WHERE key='notifications'")
        if not row:
            return {'configured': False, 'enabled': False}
        config = self.vault.open(row['value'])
        return {'configured': True, 'enabled': config['enabled'], 'kind': config['kind']}

    def configure(self, body):
        validate_url(body.kind, body.url)
        with self.lock, self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            high = c.execute('SELECT COALESCE(MAX(id),0) FROM notifications').fetchone()[0]
            config = {**body.model_dump(), 'after_id': high}
            c.execute("INSERT INTO settings(key,value) VALUES('notifications',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (self.vault.seal(config),))
            c.execute("UPDATE notification_deliveries SET state='cancelled' WHERE state IN ('pending','retry')")
        self.db.audit('admin', 'notifications.configured', detail={'enabled': body.enabled, 'kind': body.kind})

    def disable(self):
        with self.lock, self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute("SELECT value FROM settings WHERE key='notifications'").fetchone()
            if row:
                config = self.vault.open(row['value'])
                config['enabled'] = False
                c.execute("UPDATE settings SET value=? WHERE key='notifications'", (self.vault.seal(config),))
            c.execute("UPDATE notification_deliveries SET state='cancelled' WHERE state IN ('pending','retry')")
        self.db.audit('admin', 'notifications.disabled')

    def run_once(self):
        with self.lock:
            row = self.db.one("SELECT value FROM settings WHERE key='notifications'")
            if not row:
                return False
            config = self.vault.open(row['value'])
            if not config['enabled']:
                return False
            now = time.time()
            with self.db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                for notice in c.execute('SELECT id FROM notifications WHERE id>? ORDER BY id LIMIT 100', (config['after_id'],)).fetchall():
                    c.execute("INSERT OR IGNORE INTO notification_deliveries(id,notification_id,state,attempts,next_attempt,updated) VALUES(?,?,'pending',0,0,?)",
                              (uuid.uuid4().hex, notice['id'], now))
                    config['after_id'] = notice['id']
                c.execute("UPDATE settings SET value=? WHERE key='notifications'", (self.vault.seal(config),))
                task = c.execute("SELECT * FROM notification_deliveries WHERE state IN ('pending','retry') AND next_attempt<=? ORDER BY notification_id LIMIT 1", (now,)).fetchone()
                if not task:
                    return False
                c.execute("UPDATE notification_deliveries SET state='sending',attempts=attempts+1,updated=? WHERE id=?", (now, task['id']))
            payload = {'event': 'workbench.notification', 'notification_id': task['notification_id'],
                       'text': '闲鱼工作台有新通知，请在工作台查看。'}
            try:
                send(config, payload, task['id'])
                state, error = 'delivered', None
            except Exception:
                state = 'retry' if task['attempts'] + 1 < 3 else 'failed'
                error = 'delivery_failed'
            self.db.execute('UPDATE notification_deliveries SET state=?,error=?,next_attempt=?,updated=? WHERE id=?',
                            (state, error, time.time() + 60 * 2 ** task['attempts'], time.time(), task['id']))
            return True
