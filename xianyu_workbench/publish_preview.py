"""Local-only publish snapshots. No upload, recommendation or platform transport."""
import uuid
from decimal import Decimal

from pydantic import Field

from .models import Model
from .provider import Problem
from .security import digest


class Category(Model):
    cat_id: str = Field(pattern=r'^\d{1,30}$')
    cat_name: str = Field(min_length=1, max_length=100)
    channel_cat_id: str = Field(pattern=r'^\d{1,30}$')
    tb_cat_id: str = Field(pattern=r'^\d{1,30}$')


class Location(Model):
    divisionId: str = Field(pattern=r'^\d{1,30}$')
    prov: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    area: str = Field(min_length=1, max_length=100)
    gps: str = Field(min_length=3, max_length=80, pattern=r'^-?\d{1,3}(\.\d+)?,\-?\d{1,2}(\.\d+)?$')
    poiId: str = Field(min_length=1, max_length=200)
    poiName: str = Field(min_length=1, max_length=200)


class PublishDefaults(Model):
    category: Category
    location: Location
    region_summary: str = Field(min_length=1, max_length=80)


def defaults(service, account_id):
    service.provider.account(account_id)
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('publish-defaults:' + account_id,))
    if not row:
        raise Problem('publish_defaults_missing', '请管理员先录入本地类目/地点快照；不自动上传或推荐', 409)
    return service.vault.open(row['value'])


def save_defaults(service, account_id, body):
    service.provider.account(account_id)
    value = {**body.model_dump(mode='json'), 'revision': uuid.uuid4().hex,
             'source': 'admin_local_unverified'}
    service.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                       ('publish-defaults:' + account_id, service.vault.seal(value)))
    service.db.audit('admin', 'publish.defaults_changed', account_id)
    return value


def freeze(service, account, payload):
    config = defaults(service, account['id'])
    service.validate_assets(account['id'], payload['images'])
    images = [service.db.one('SELECT id,sha256 FROM assets WHERE id=? AND account_id=?',
                             (image, account['id'])) for image in payload['images']]
    fee = {'canFreeShipping': payload['delivery'] == '包邮',
           'supportFreight': payload['delivery'] in ('包邮', '一口价'), 'onlyTakeSelf': False}
    if payload['delivery'] != '包邮':
        fee['templateId'] = '0'
    if payload['delivery'] == '一口价':
        fee['postPriceInCent'] = str(int(Decimal(payload['post_price']) * 100))
    return {**config, 'uid': account['uid'], 'images': images,
            'candidate': {'itemTextDTO': {'title': payload['title'], 'desc': payload['desc'], 'titleDescSeparate': True},
                          'itemPriceDTO': {'priceInCent': str(int(Decimal(payload['price']) * 100))},
                          'itemPostFeeDTO': fee, 'itemAddrDTO': config['location'],
                          'itemCatDTO': dict(zip(('catId', 'catName', 'channelCatId', 'tbCatId'),
                                                (config['category'][k] for k in ('cat_id', 'cat_name', 'channel_cat_id', 'tb_cat_id')))),
                          'onlyTakeSelf': payload['can_self_pickup']},
            'protocol_complete': False, 'live_executor_enabled': False}


def prepare(service, account, payload):
    return {**payload, '_publish_snapshot': freeze(service, account, payload)}


def preflight(service, account, payload):
    frozen = payload.get('_publish_snapshot')
    if not frozen or digest(frozen) != digest(freeze(service, account, payload)):
        raise Problem('publish_snapshot_changed', '图片、账号或默认快照已变化，请重新预览审批', 409)
    if account['mode'] == 'live':
        raise Problem('publish_evidence_required', '本地快照校验通过；真实类目/地点/上传/ACK 证据不足，执行器未开放', 409)


def public_snapshot(snapshot):
    return {key: snapshot[key] for key in ('category', 'region_summary', 'revision', 'source', 'images',
                                          'protocol_complete', 'live_executor_enabled')}
