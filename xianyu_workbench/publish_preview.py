"""Local-only publish snapshots. No upload, recommendation or platform transport."""
import re
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from .models import Model
from .provider import Problem
from .security import digest


class Category(Model):
    cat_id: str = Field(pattern=r'^\d{1,30}$')
    cat_name: str = Field(min_length=1, max_length=100)
    channel_cat_id: str = Field(pattern=r'^\d{1,30}$')
    tb_cat_id: str = Field(pattern=r'^\d{1,30}$')


class Location(Model):
    divisionId: int = Field(ge=1, strict=True)
    prov: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    area: str = Field(min_length=1, max_length=100)
    gps: str = Field(min_length=3, max_length=80)

    @field_validator('gps', mode='before')
    @classmethod
    def latitude_longitude(cls, value):
        # Validate before Model's whitespace stripping; the wire string is immutable.
        if not isinstance(value, str) or not re.fullmatch(r'-?[0-9]{1,2}(?:\.[0-9]+)?,-?[0-9]{1,3}(?:\.[0-9]+)?', value):
            raise ValueError('gps requires latitude,longitude decimal strings')
        latitude, longitude = map(Decimal, value.split(','))
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError('gps latitude/longitude out of range')
        return value
    poiId: str = Field(min_length=1, max_length=200)
    poiName: str = Field(min_length=1, max_length=200)


TextMode = Literal['separate', 'web_combined']


class PublishDefaults(Model):
    text_mode: TextMode = 'separate'
    category: Category
    location: Location
    region_summary: str = Field(min_length=1, max_length=80)


def defaults(service, account_id):
    service.provider.account(account_id)
    row = service.db.one('SELECT value FROM settings WHERE key=?', ('publish-defaults:' + account_id,))
    if not row:
        raise Problem('publish_defaults_missing', '请管理员先录入本地类目/地点快照；不自动上传或推荐', 409)
    config = service.vault.open(row['value'])
    try:
        Location.model_validate(config.get('location', {}))
    except ValueError:
        raise Problem('publish_location_reapproval_required', '地点需按纬度,经度重新核验录入审批；不自动交换坐标', 409)
    return config


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
    mode = config.get('text_mode', 'separate')
    if mode not in ('separate', 'web_combined'):
        raise Problem('invalid_text_mode', '未知发布文本模式，请管理员重新配置', 409)
    service.validate_assets(account['id'], payload['images'])
    images = [service.db.one('SELECT id,sha256 FROM assets WHERE id=? AND account_id=?',
                             (image, account['id'])) for image in payload['images']]
    fee = {'canFreeShipping': payload['delivery'] == '包邮',
           'supportFreight': payload['delivery'] in ('包邮', '一口价'),
           'onlyTakeSelf': payload['delivery'] == '无需邮寄' and payload['can_self_pickup']}
    if payload['delivery'] == '一口价':
        fee['templateId'] = '0'
        fee['postPriceInCent'] = str(int(Decimal(payload['post_price']) * 100))
    return {**config, 'uid': account['uid'], 'images': images,
            'candidate': {'itemTextDTO': {'title': payload['desc'] if mode == 'web_combined' else payload['title'],
                                          'desc': payload['desc'], 'titleDescSeparate': mode == 'separate'},
                          'itemPriceDTO': {'priceInCent': str(int(Decimal(payload['price']) * 100))},
                          'itemPostFeeDTO': fee, 'itemAddrDTO': config['location'],
                          'itemCatDTO': dict(zip(('catId', 'catName', 'channelCatId', 'tbCatId'),
                                                (config['category'][k] for k in ('cat_id', 'cat_name', 'channel_cat_id', 'tb_cat_id'))))},
            'protocol_complete': False, 'live_executor_enabled': False}


def prepare(service, account, payload):
    snapshot = freeze(service, account, payload)
    if account['mode'] == 'live':
        from .publish_executor import freeze as freeze_executor
        executor = freeze_executor(service, account, snapshot)
        if executor:
            snapshot['executor'] = executor
    return {**payload, '_publish_snapshot': snapshot}


def preflight(service, account, payload, *, executing=False):
    frozen = payload.get('_publish_snapshot')
    current = prepare(service, account, {k: v for k, v in payload.items() if k != '_publish_snapshot'})['_publish_snapshot']
    if not frozen or digest(frozen) != digest(current):
        raise Problem('publish_snapshot_changed', '图片、账号或默认快照已变化，请重新预览审批', 409)
    if account['mode'] == 'live' and not (executing and frozen.get('executor')):
        raise Problem('publish_evidence_required', '本地快照校验通过；真实类目/地点/上传/ACK 证据不足，执行器未开放', 409)


def public_snapshot(snapshot):
    return {key: snapshot[key] for key in ('category', 'region_summary', 'revision', 'source', 'images',
                                          'protocol_complete', 'live_executor_enabled')}
