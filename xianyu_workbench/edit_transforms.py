"""Named, evidence-bounded editDetail conversions; never evaluate expressions."""
import copy
import re
from typing import Literal

from .item_edit import InvariantMapping


class SnapshotInvariantMapping(InvariantMapping):
    transform: Literal['identity', 'bool_string', 'single_image_v1', 'free_shipping_v1', 'category_v1'] = 'identity'


def bool_string(value):
    if type(value) is not str or value not in ('true', 'false'):
        raise ValueError('strict boolean string required')
    return value == 'true'


def exact_keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('complete exact source keys required')


def positive_integer(value):
    if type(value) is not str or not re.fullmatch(r'[1-9][0-9]{0,9}', value):
        raise ValueError('bounded positive integer string required')
    return int(value)


def transform_invariant(mapping, value):
    name = mapping.transform
    if name == 'identity':
        return value
    fields = {'bool_string': {'freebies', 'defaultPrice'}, 'single_image_v1': {'imageInfoDOList'},
              'free_shipping_v1': {'itemPostFeeDTO'}, 'category_v1': {'itemCatDTO'}}
    if (len(mapping.request_path) != 1 or mapping.request_path[0] not in fields[name]
            or mapping.before_path != ['edit', mapping.request_path[0]]):
        raise ValueError('transform restricted to evidenced source and destination')
    if name == 'bool_string':
        return bool_string(value)
    if name == 'single_image_v1':
        if type(value) is not list or len(value) != 1:
            raise ValueError('only one evidenced image supported')
        image = value[0]
        exact_keys(image, ('url', 'extraInfo', 'widthSize', 'heightSize', 'major', 'type'))
        exact_keys(image['extraInfo'], ('raw', 'isT', 'isH'))
        if (type(image['url']) is not str or not image['url']
                or any(type(v) is not str for v in image['extraInfo'].values())
                or type(image['type']) is not str or image['type'] != '0'):
            raise ValueError('unsupported image source')
        return [{'url': image['url'], 'extraInfo': copy.deepcopy(image['extraInfo']),
                 'widthSize': positive_integer(image['widthSize']), 'heightSize': positive_integer(image['heightSize']),
                 'major': bool_string(image['major']), 'type': 0, 'isQrCode': False, 'labels': [],
                 'templateIndex': '0', 'thumbnail': image['url'], 'status': 'done'}]
    if name == 'free_shipping_v1':
        exact_keys(value, ('canFreeShipping', 'supportFreight', 'onlyTakeSelf', 'templateId', 'idleTemplateId', 'postPriceInCent'))
        if any(type(value[k]) is not str or value[k] != '0' for k in ('templateId', 'idleTemplateId', 'postPriceInCent')):
            raise ValueError('only zero fee and zero templates evidenced')
        flags = {k: bool_string(value[k]) for k in ('canFreeShipping', 'supportFreight', 'onlyTakeSelf')}
        if flags != {'canFreeShipping': True, 'supportFreight': True, 'onlyTakeSelf': False}:
            raise ValueError('only evidenced free shipping combination supported')
        return {**flags, 'templateId': '0'}
    exact_keys(value, ('catId', 'catName', 'channelCatId', 'tbCatId', 'sugShow'))
    if any(type(v) is not str for v in value.values()) or value['sugShow'] != 'false':
        raise ValueError('only explicit sugShow false may be omitted')
    return {k: value[k] for k in ('catId', 'catName', 'channelCatId', 'tbCatId')}
