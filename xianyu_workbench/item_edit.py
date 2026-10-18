"""Evidence-bound same-ID editing; no inferred platform payloads."""
import copy
import time
import uuid
from decimal import Decimal
from typing import Literal

from filelock import FileLock, Timeout
from pydantic import ConfigDict, Field, StrictStr, model_validator

from .models import Model
from .provider import Problem
from .publish_executor import binding, checkpoint
from .security import canonical, digest


class EditIn(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    item_id: str = Field(pattern=r'^\d{1,30}$')
    title: StrictStr = Field(min_length=1, max_length=60)
    desc: StrictStr = Field(min_length=1, max_length=5000)
    price: StrictStr = Field(pattern=r'^(?:0|[1-9]\d{0,6})\.\d{2}$')

    @model_validator(mode='after')
    def amount(self):
        if not Decimal('0') < Decimal(self.price) <= Decimal('1000000'):
            raise ValueError('invalid amount')
        return self


class InvariantMapping(Model):
    request_path: list[StrictStr] = Field(min_length=1, max_length=10)
    before_path: list[StrictStr] = Field(min_length=1, max_length=10)
    evidence: StrictStr = Field(min_length=10, max_length=2000)


class EditProtocol(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    schema_version: Literal[2]
    original_request: dict
    invariant_mappings: list['InvariantMapping'] = Field(min_length=1, max_length=200)
    item_id: str = Field(pattern=r'^\d{1,30}$')
    uid: str = Field(pattern=r'^\d{1,30}$')
    api_version: str = Field(pattern=r'^\d{1,2}\.\d{1,2}$')
    template: dict
    request_paths: dict[str, list[StrictStr]]
    response_paths: dict[str, list[StrictStr]]
    price_encoding: Literal['yuan_string', 'cent_string']
    before: dict
    success_ret: list[StrictStr] = Field(min_length=1, max_length=4)
    read_success_ret: list[StrictStr] = Field(min_length=1, max_length=4)
    complete_semantics_confirmed: Literal[True]
    evidence: StrictStr = Field(min_length=10, max_length=2000)

    @model_validator(mode='after')
    def contract(self):
        keys = {'item_id', 'uid', 'version', 'status', 'title', 'desc', 'price', 'invariants'}
        if set(self.before) != keys or set(self.response_paths) != keys or set(self.request_paths) != {'title', 'desc', 'price'}:
            raise ValueError('complete semantic contract required')
        if self.before['item_id'] != self.item_id or self.before['uid'] != self.uid or self.template.get('itemId') != self.item_id:
            raise ValueError('identity mismatch')
        EditIn.model_validate({k: self.before[k] for k in ('item_id', 'title', 'desc', 'price')})
        if (type(self.before['version']) not in (str, int) or self.before['version'] == ''
                or type(self.before['status']) not in (str, int) or self.before['status'] == ''
                or not isinstance(self.before['invariants'], dict) or not self.before['invariants']):
            raise ValueError('version/status/invariants required')
        for paths in (self.request_paths, self.response_paths):
            values = list(paths.values())
            for i, path in enumerate(values):
                if not 1 <= len(path) <= 10 or any(not k or len(k) > 100 for k in path):
                    raise ValueError('invalid object path')
                if any(path[:len(other)] == other or other[:len(path)] == path for other in values[i + 1:]):
                    raise ValueError('overlapping semantic paths')
        for key, path in self.request_paths.items():
            if path[0] == 'itemId' or get(self.template, path) != encoded(self, key, self.before[key]):
                raise ValueError('template does not match original values')
        if canonical(self.original_request) != canonical(self.template):
            raise ValueError('template differs from evidenced original request')
        paths = [tuple(p) for p in self.request_paths.values()]
        covered = set()
        for mapping in self.invariant_mappings:
            path = tuple(mapping.request_path)
            source = mapping.before_path
            if source[0] not in {'item_id', 'uid', 'version', 'status', 'invariants'}:
                raise ValueError('fixed fields require identity/status/invariant evidence')
            if any(not key for key in (*path, *source)):
                raise ValueError('empty mapping key')
            if canonical(get(self.template, path)) != canonical(get(self.before, source)):
                raise ValueError('fixed request differs from readback invariant')
            paths.append(path)
            covered.update(leaves(get(self.template, path), path))
        for i, path in enumerate(paths):
            if any(path[:len(other)] == other or other[:len(path)] == path for other in paths[i + 1:]):
                raise ValueError('overlapping request coverage')
        if not any(m.request_path == ['itemId'] and m.before_path == ['item_id'] for m in self.invariant_mappings):
            raise ValueError('same-ID mapping required')
        covered.update(tuple(p) for p in self.request_paths.values())
        if covered != leaves(self.template):
            raise ValueError('unmapped request fields; no fixed metadata exceptions are verified')
        if any(not x.startswith('SUCCESS::') for x in self.success_ret + self.read_success_ret):
            raise ValueError('exact success ret required')
        if len(canonical(self.model_dump())) > 60000:
            raise ValueError('contract too large')
        return self


def leaves(value, path=()):
    """Arrays are indivisible: mapping compares their entire typed recursive value."""
    if isinstance(value, dict) and value:
        return set().union(*(leaves(v, (*path, k)) for k, v in value.items()))
    return {path}


def get(value, path):
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError('missing contract field')
        value = value[key]
    return value


def encoded(protocol, key, value):
    if key == 'price' and protocol.price_encoding == 'cent_string':
        return str(int(Decimal(value) * 100))
    return value


def save_protocol(service, account_id, body):
    account = service.provider.account(account_id)
    if account['mode'] != 'live' or account['uid'] != body.uid:
        raise Problem('account_mismatch', '编辑协议必须绑定同 UID 真实账号', 409)
    value = {**body.model_dump(), 'revision': uuid.uuid4().hex}
    with service.db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        unknown_guard(service, c, account_id, body.item_id)
        c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                  ('edit-protocol:' + account_id, service.vault.seal(value)))
    service.db.audit('admin', 'edit.protocol_changed', account_id)
    return {'revision': value['revision']}


def load_protocol(service, account_id):
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + account_id,))
    if not row:
        raise Problem('edit_protocol_required', '缺少完整同 ID 编辑证据协议', 409)
    value = service.vault.open(row['value'])
    try:
        EditProtocol.model_validate({k: v for k, v in value.items() if k != 'revision'})
    except ValueError:
        raise Problem('edit_protocol_invalid', '旧协议或完整映射无效，请重新取证配置审批；尚未提交', 409)
    return value


def prepare(service, account, payload):
    protocol = load_protocol(service, account['id'])
    if account['mode'] != 'live' or protocol['uid'] != account['uid'] or protocol['item_id'] != payload['item_id']:
        raise Problem('account_mismatch', '协议账号或同 ID 不符', 409)
    if all(payload[k] == protocol['before'][k] for k in ('title', 'desc', 'price')):
        raise Problem('edit_no_change', '没有文字或价格变化', 409)
    return {**payload, '_edit_snapshot': {'protocol': protocol, 'binding': binding(service, account)}}


def snapshot(response, protocol):
    if response.get('ret') != protocol['read_success_ret']:
        raise ValueError('read success mismatch')
    value = {key: get(response, path) for key, path in protocol['response_paths'].items()}
    if type(value['version']) not in (str, int) or value['version'] == '':
        raise ValueError('missing version')
    return value


def unknown_guard(service, connection, account_id, item_id):
    """Called inside the same IMMEDIATE transaction as configuration/proposal writes."""
    rows = connection.execute("SELECT * FROM actions WHERE account_id=? AND kind='item.edit'", (account_id,)).fetchall()
    for row in rows:
        previous = service.vault.open(row['payload'])
        if previous.get('item_id') != item_id:
            continue
        if row['state'] in ('running', 'unconfirmed'):
            raise Problem('edit_previous_unknown', '该商品正在执行或存在不确定编辑，禁止重录协议或新申请', 409)
        if row['result']:
            result = service.vault.open(row['result'])
            if (row['state'] != 'submitted' or result.get('stage') != 'verified'
                    or any(result.get(k) is not True for k in ('ownership_verified', 'status_verified', 'content_verified'))
                    or not isinstance(result.get('after'), dict) or not result.get('verified_at')):
                raise Problem('edit_previous_unknown', '该商品有不确定提交，禁止重录协议或新申请', 409)


def history_guard(service, account_id, payload, action_id):
    protocol = payload['_edit_snapshot']['protocol']
    latest = None
    for row in service.db.all("SELECT * FROM actions WHERE account_id=? AND kind='item.edit' AND id!=?", (account_id, action_id)):
        previous = service.vault.open(row['payload'])
        if previous.get('item_id') != payload['item_id']:
            continue
        if not row['result']:
            if row['state'] == 'unconfirmed':
                raise Problem('edit_previous_unknown', '该商品有无法判定的历史编辑，禁止再次提交', 409)
            continue
        result = service.vault.open(row['result'])
        if (row['state'] != 'submitted' or result.get('stage') != 'verified'
                or any(result.get(key) is not True for key in ('ownership_verified', 'status_verified', 'content_verified'))
                or not isinstance(result.get('after'), dict) or not result.get('verified_at')):
            raise Problem('edit_previous_unknown', '该商品有不确定提交，禁止新键或新协议重试', 409)
        if latest is None or result['verified_at'] > latest[0]['verified_at']:
            latest = (result, previous['_edit_snapshot']['protocol'])
    if latest:
        result, previous = latest
        if (protocol['revision'] == previous['revision']
                or canonical(protocol['before']) != canonical(result['after'])
                or canonical(protocol['before']['version']) == canonical(previous['before']['version'])):
            raise Problem('edit_stale_before', '后续编辑需新协议版本及最近 verified after 的精确原值', 409)


def execute(service, action_id):
    try:
        with FileLock(service.provider.lock_path, timeout=0.1):
            return _execute(service, action_id)
    except Timeout:
        raise Problem('busy', '操作队列忙，尚未编辑', 409)


def _execute(service, action_id):
    row = service.db.one('SELECT * FROM actions WHERE id=?', (action_id,))
    if not row or row['kind'] != 'item.edit' or row['state'] != 'running' or not row['approved_at'] or row['result']:
        raise Problem('edit_authorization_required', '需要指定未执行过的批准编辑', 409)
    payload = service.vault.open(row['payload'])
    frozen = payload['_edit_snapshot']
    protocol = frozen['protocol']

    def guard():
        account = service.provider.account(row['account_id'])
        service.observation.guard(account['id'])
        if not service.s.live_enabled or not service.s.edit_enabled:
            raise Problem('edit_disabled', '同 ID 编辑默认关闭', 409)
        if account['paused'] or account['mode'] != 'live' or row['mode'] != 'live' or row['expires'] <= time.time():
            raise Problem('edit_stopped', '账号暂停、模式变化或审批过期', 409)
        if (canonical(load_protocol(service, account['id'])) != canonical(protocol)
                or binding(service, account) != frozen['binding']
                or digest({'account_id': account['id'], 'kind': row['kind'], 'payload': payload, 'mode': account['mode']}) != row['digest']):
            raise Problem('edit_changed', '协议/凭据/审批变化，请重新申请', 409)
        return account

    def call(operation, request, write=False):
        service.provider._selected.edit_action = action_id
        try:
            return service.provider._live(account, operation, request, write=write)
        finally:
            service.provider._selected.edit_action = None

    account = guard()
    history_guard(service, account['id'], payload, action_id)
    if time.time() - account['last_write'] < service.s.write_interval:
        raise Problem('rate_limited', '写入间隔未到，尚未编辑', 429)
    request = {'item_id': payload['item_id'], 'api_version': protocol['api_version']}
    try:
        original = snapshot(call('edit.read', request), protocol)
        if canonical(original) != canonical(protocol['before']):
            raise ValueError('original changed')
    except Exception:
        raise Problem('edit_original_changed', '只读原值、版本、归属或状态不符，未提交编辑', 409)
    account = guard()
    template = copy.deepcopy(protocol['template'])
    parsed = EditProtocol.model_validate({k: v for k, v in protocol.items() if k != 'revision'})
    for key, path in protocol['request_paths'].items():
        target = get(template, path[:-1])
        target[path[-1]] = encoded(parsed, key, payload[key])
    unchanged = copy.deepcopy(template)
    for path in protocol['request_paths'].values():
        get(unchanged, path[:-1])[path[-1]] = get(protocol['original_request'], path)
    if canonical(unchanged) != canonical(protocol['original_request']):
        raise Problem('edit_template_changed', '编辑请求包含未批准的固定字段变化', 409)
    result = {'stage': 'submitting', 'item_id': payload['item_id'], 'ownership_verified': False,
              'status_verified': False, 'content_verified': False}
    checkpoint(service, action_id, result)
    service.db.execute('UPDATE accounts SET last_write=?,last_call=? WHERE id=?', (time.time(), time.time(), account['id']))
    try:
        response = call('edit.submit', {**request, 'template': template}, True)
        if response.get('ret') != protocol['success_ret'] or get(response, ['data', 'itemId']) != payload['item_id']:
            raise ValueError('edit acknowledgement mismatch')
        result['stage'] = 'verifying'
        checkpoint(service, action_id, result)
        guard()
        after = snapshot(call('edit.read', request), protocol)
        expected = {**protocol['before'], **{k: payload[k] for k in ('title', 'desc', 'price')}, 'version': after['version']}
        if canonical(after) != canonical(expected):
            raise ValueError('readback mismatch')
        result.update(stage='verified', ownership_verified=True, status_verified=True, content_verified=True,
                      after=after, verified_at=time.time())
    except Exception:
        result['notice'] = '编辑结果不确定，禁止重试；请人工核对同 ID 商品'
    checkpoint(service, action_id, result)
    return result
