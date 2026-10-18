"""Selected, single-attempt publishing. Never calls the implicit upstream publish."""
import copy
import re
import time
import uuid
from typing import Literal
from urllib.parse import urlsplit

from filelock import FileLock, Timeout
from pydantic import Field, StrictInt, StrictStr, model_validator

from .models import Model
from .provider import Problem
from .security import canonical, digest


class ReadbackStatus(Model):
    path: list[StrictStr] = Field(min_length=1, max_length=10)
    value_type: Literal['string', 'integer']
    allowed_values: list[StrictStr | StrictInt] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def typed_values(self):
        expected = str if self.value_type == 'string' else int
        if any(type(value) is not expected for value in self.allowed_values) or any(not key for key in self.path):
            raise ValueError('status contract requires exact types and nonempty keys')
        return self


class PublishProtocol(Model):
    template: dict
    success_ret: list[str] = Field(min_length=1, max_length=4)
    readback_success_ret: list[str] = Field(min_length=1, max_length=4)
    readback_status: ReadbackStatus
    evidence: str = Field(min_length=10, max_length=2000)
    upload_authorized: bool


def save_protocol(service, account_id, body):
    service.provider.account(account_id)
    value = body.model_dump(mode='json')
    if (not body.upload_authorized or body.template.get('imageInfoDOList') != []
            or not body.template.get('uniqueCode') or len(canonical(value)) > 60000
            or any(not entry.startswith('SUCCESS::') for entry in body.success_ret + body.readback_success_ret)):
        raise Problem('invalid_protocol', '需要完整已核验模板、空图片占位、明确上传授权及精确成功 ret', 422)
    value['revision'] = uuid.uuid4().hex
    service.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                       ('publish-protocol:' + account_id, service.vault.seal(value)))
    service.db.audit('admin', 'publish.protocol_changed', account_id)
    return {'revision': value['revision']}


def binding(service, account):
    if not account['secret'] or not account['uid']:
        raise Problem('auth_required', '发布需要管理员独立导入同 UID Cookie', 409)
    cookies = service.vault.open(account['secret'])
    if cookies.get('unb') != account['uid']:
        raise Problem('account_mismatch', '发布登录态所属账号不符', 409)
    return {'uid': account['uid'], 'credential_digest': digest(cookies), 'source': 'independent_cookie_http'}


def freeze(service, account, snapshot):
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('publish-protocol:' + account['id'],))
    if not row:
        return None
    protocol = service.vault.open(row['value'])
    try:
        PublishProtocol.model_validate({k: v for k, v in protocol.items() if k != 'revision'})
    except ValueError:
        raise Problem('publish_readback_contract_required', '缺少已取证的回读精确 ret 和状态契约，请重新录入审批', 409)
    template = protocol['template']
    for key, value in snapshot['candidate'].items():
        actual = template.get(key)
        if key == 'itemCatDTO' and isinstance(actual, dict):
            actual = {k: actual.get(k) for k in value}
        if canonical(actual) != canonical(value):
            raise Problem('publish_protocol_mismatch', '已核验模板与草稿/类目/地点不一致，请重新录入', 409)
    return {**protocol, 'binding': binding(service, account)}


def checkpoint(service, action_id, result):
    service.db.execute('UPDATE actions SET result=? WHERE id=? AND state=\'running\'',
                       (service.vault.seal(result), action_id))


def execute(service, action_id):
    """Hold the shared operation lock across upload, submit and readback."""
    try:
        with FileLock(service.provider.lock_path, timeout=0.1):
            return _execute_locked(service, action_id)
    except Timeout:
        raise Problem('busy', '账号操作队列忙，未开始上传', 409)


def _execute_locked(service, action_id):
    from .publish_preview import preflight
    provider = service.provider
    row = service.db.one('SELECT * FROM actions WHERE id=?', (action_id,))
    if (not row or row['state'] != 'running' or row['kind'] != 'item.publish'
            or row['mode'] != 'live' or not row['approved_at'] or row['result']):
        raise Problem('publish_authorization_required', '必须指定未执行过的已批准发布 action', 409)
    payload = service.vault.open(row['payload'])
    account = provider.account(row['account_id'])

    def guard():
        current = provider.account(row['account_id'])
        if not service.s.live_enabled or not service.s.publish_enabled:
            raise Problem('publish_disabled', '发布开关关闭，需管理员核验证据并启用', 409)
        if current['paused'] or current['mode'] != 'live' or row['expires'] <= time.time():
            raise Problem('publish_stopped', '账号暂停、模式变化或审批过期', 409)
        if digest({'account_id': current['id'], 'kind': row['kind'], 'payload': payload, 'mode': current['mode']}) != row['digest']:
            raise Problem('integrity_error', '发布审批内容改变', 409)
        preflight(service, current, payload, executing=True)
        return current

    def transport(operation, request, *, write):
        provider._selected.publish_action = action_id
        try:
            return provider._live(account, operation, request, write=write)
        finally:
            provider._selected.publish_action = None

    account = guard()
    frozen = payload['_publish_snapshot']['executor']
    if time.time() - account['last_write'] < service.s.write_interval:
        raise Problem('rate_limited', '发布间隔未到，未开始上传', 429)
    paths = service.validate_assets(account['id'], payload['images'])
    result = {'stage': 'prepared', 'uploaded_count': 0, 'uploads': [], 'ownership_verified': False}
    # Persist before the first external write: crashes never release this action for retry.
    checkpoint(service, action_id, result)
    service.db.execute('UPDATE accounts SET last_write=?,last_call=? WHERE id=?', (time.time(), time.time(), account['id']))
    try:
        images = []
        for path in paths:
            account = guard()
            result['stage'] = 'uploading'
            checkpoint(service, action_id, result)
            asset = payload['_publish_snapshot']['images'][len(images)]
            image = transport('publish.upload', {'path': path, 'sha256': asset['sha256']}, write=True)
            url = urlsplit(image.get('url', ''))
            if (url.scheme != 'https' or not url.hostname or url.username or url.password
                    or not (url.hostname == 'alicdn.com' or url.hostname.endswith('.alicdn.com'))
                    or type(image.get('width')) is not int or type(image.get('height')) is not int
                    or min(image['width'], image['height']) <= 0):
                raise ValueError('invalid upload response')
            images.append({'extraInfo': {'isH': 'false', 'isT': 'false', 'raw': 'false'},
                           'isQrCode': False, 'url': image['url'], 'heightSize': image['height'],
                           'widthSize': image['width'], 'major': True, 'type': 0, 'status': 'done'})
            asset = payload['_publish_snapshot']['images'][len(images) - 1]
            result['uploads'].append({'asset_id': asset['id'], 'sha256': asset['sha256'],
                                      'url': image['url'], 'width': image['width'], 'height': image['height']})
            result['uploaded_count'] = len(images)
            checkpoint(service, action_id, result)
        account = guard()
        request = copy.deepcopy(frozen['template'])
        request['imageInfoDOList'] = images
        result.update(stage='submitting', request_digest=digest(request))
        checkpoint(service, action_id, result)
        raw = transport('publish.submit', request, write=True)
        item_id = raw.get('data', {}).get('itemId')
        if raw.get('ret') != frozen['success_ret'] or not isinstance(item_id, str) or not re.fullmatch(r'[0-9]{1,30}', item_id):
            raise ValueError('unverified publish response')
        result.update(stage='verifying', item_id=item_id)
        checkpoint(service, action_id, result)
        account = guard()
        raw = transport('publish.readback', {'itemId': item_id}, write=False)
        data = raw.get('data', {})
        ret = raw.get('ret')
        if (ret != frozen['readback_success_ret']
                or str(data.get('itemDO', {}).get('itemId', '')) != item_id
                or str(data.get('sellerDO', {}).get('sellerId', '')) != account['uid']):
            raise ValueError('ownership readback failed')
        status_contract = frozen['readback_status']
        observed = raw
        for key in status_contract['path']:
            if not isinstance(observed, dict) or key not in observed:
                raise ValueError('readback status missing')
            observed = observed[key]
        expected_type = str if status_contract['value_type'] == 'string' else int
        if type(observed) is not expected_type or observed not in status_contract['allowed_values']:
            raise ValueError('readback status unknown')
        guard()
        result.update(stage='verified', ownership_verified=True, status_verified=True, ok=True)
        return result
    except Exception:
        result['notice'] = '上传或发布已尝试，结果不确定；禁止自动重试，请人工核对。'
        checkpoint(service, action_id, result)
        return result
