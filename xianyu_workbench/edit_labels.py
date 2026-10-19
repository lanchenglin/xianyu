"""Single-category recommendation dependency, not a general recommendation API."""
import copy
import os
import re
import selectors
import signal
import subprocess
import time
from typing import Literal

from pydantic import Field, StrictStr

from .models import Model
from .security import canonical

CONTROLS = {'lockCpv': False, 'multiSKU': False, 'publishScene': 'mainPublish', 'scene': 'newPublishChoice'}
RET = ['SUCCESS::调用成功']
NULL_FIELDS = {'valueId', 'valueName', 'subPropertyId', 'subValueId', 'labelId', 'isUserCancel'}
STRING_FIELDS = {'channelCateName', 'channelCateId', 'tbCatId', 'labelType', 'propertyName',
                 'isUserClick', 'from', 'propertyId', 'labelFrom'}


class LabelDependency(Model):
    mode: Literal['single_category_v1']
    observed_label_type: Literal['common', 'category'] = 'category'
    sku_source_mode: Literal['explicit_empty_arrays', 'missing_with_empty_extra'] = 'explicit_empty_arrays'
    card_source_mode: Literal['identity', 'fill_missing_unselected'] = 'identity'
    requests: list[dict] = Field(min_length=2, max_length=2)
    responses: list[dict] = Field(min_length=2, max_length=2)
    unique_code_mode: Literal['timestamp_random']
    evidence: StrictStr = Field(min_length=10, max_length=2000)


def equal(left, right):
    if canonical(left) != canonical(right):
        raise ValueError('label dependency exact binding mismatch')


def validate_request(request):
    keys = {'title', 'description', 'imageInfos', 'currentCardList', 'selectedList',
            'catId', 'catName', 'channelCatId', 'uniqueCode', *CONTROLS}
    if type(request) is not dict or set(request) != keys or len(canonical(request).encode()) > 60000:
        raise ValueError('bounded recommendation request required')
    equal({k: request[k] for k in CONTROLS}, CONTROLS)
    for key in ('title', 'description', 'catId', 'catName', 'channelCatId', 'uniqueCode'):
        if type(request[key]) is not str or not request[key]:
            raise ValueError('explicit recommendation strings required')
    equal(request['title'], request['description'])
    if not re.fullmatch(r'[0-9]{14,16}', request['uniqueCode']):
        raise ValueError('evidenced timestamp_random code required')
    if type(request['selectedList']) is not list or len(request['selectedList']) != 1:
        raise ValueError('one selected category required')
    if type(request['selectedList'][0]) is not dict or request['selectedList'][0].get('propertyId') != '-10000':
        raise ValueError('category selection required')
    if type(request['imageInfos']) is not list or len(request['imageInfos']) != 1:
        raise ValueError('one evidenced image required')
    if type(request['currentCardList']) is not list or len(request['currentCardList']) > 20:
        raise ValueError('bounded card list required')


def selected_label(response, category, observed_label_type='category'):
    if type(observed_label_type) is not str or observed_label_type not in ('common', 'category'):
        raise ValueError('unsupported observed label type')
    if type(response) is not dict or len(canonical(response).encode()) > 60000 or response.get('ret') != RET:
        raise ValueError('recommendation response contract failed')
    if type(response.get('data')) is not dict:
        raise ValueError('recommendation data object required')
    cards = response['data'].get('cardList')
    if type(cards) is not list or not 1 <= len(cards) <= 20:
        raise ValueError('bounded response cards required')
    selected = []
    for card in cards:
        if type(card) is not dict:
            raise ValueError('recommendation card object required')
        data = card.get('cardData')
        if type(data) is not dict or type(data.get('valuesList')) is not list or len(data['valuesList']) > 100:
            raise ValueError('invalid recommendation card')
        for value in data['valuesList']:
            if type(value) is not dict:
                raise ValueError('invalid recommendation value')
            if value.get('isClicked') == '1':
                if data.get('propertyId') != '-10000' or value.get('propertyId') != '-10000' or value.get('isUserClick') != '1':
                    raise ValueError('only selected category supported')
                selected.append(value)
    if len(selected) != 1:
        raise ValueError('exactly one selected category required')
    value = selected[0]
    for key in ('catId', 'catName', 'channelCatId', 'tbCatId'):
        equal(value.get(key), category[key])
    td = value.get('transportData')
    if type(td) is not dict or set(td) != NULL_FIELDS | STRING_FIELDS:
        raise ValueError('complete evidenced transportData required')
    if any(td[k] is not None for k in NULL_FIELDS) or any(type(td[k]) is not str for k in STRING_FIELDS):
        raise ValueError('transportData types differ from evidence')
    equal(td['propertyId'], '-10000')
    equal(td['isUserClick'], '1')
    equal(td['channelCateId'], category['channelCatId'])
    equal(td['tbCatId'], category['tbCatId'])
    equal(td['propertyName'], value.get('propertyName'))
    equal(value.get('labelType'), observed_label_type)
    equal(td['labelType'], observed_label_type)
    return {**td, 'text': value['catName'],
            'properties': '-10000##' + td['propertyName'] + ':' + value['channelCatId'] + '##' + value['catName']}


def card_source(response, mode):
    cards = copy.deepcopy([c['cardData'] for c in response['data']['cardList']])
    if mode == 'identity':
        return cards
    if mode != 'fill_missing_unselected':
        raise ValueError('unknown card source mode')
    for card in cards:
        for value in card['valuesList']:
            if 'isClicked' not in value:
                if value.get('isUserClick') != '0':
                    raise ValueError('only evidenced unselected missing flag may be filled')
                value['isClicked'] = '0'
            elif type(value['isClicked']) is not str or value['isClicked'] not in ('0', '1'):
                raise ValueError('null or unknown clicked flag forbidden')
    return cards


def validate_dependency(protocol):
    dep = protocol.get('label_dependency')
    if not dep:
        return
    edit = protocol['before']['edit']
    if dep.get('sku_source_mode', 'explicit_empty_arrays') == 'explicit_empty_arrays':
        for key in ('itemSkuList', 'itemProperties'):
            equal(edit.get(key), [])
        if 'itemSkuExtra' in edit:
            equal(edit['itemSkuExtra'], {})
    else:
        if any(k in edit for k in ('itemSkuList', 'itemProperties')):
            raise ValueError('missing SKU source mode forbids present arrays')
        equal(edit.get('itemSkuExtra'), {})
        if any(k in protocol['template'] for k in ('itemSkuList', 'itemProperties', 'propertyImageList', 'itemSkuExtra')):
            raise ValueError('SKU request fields forbidden in missing source mode')
    if any(protocol['template'].get(k) not in (None, []) for k in ('itemSkuList', 'propertyImageList')):
        raise ValueError('SKU requests unsupported')
    old = edit.get('itemLabelExtList')
    if type(old) is not list or len(old) != 1 or type(old[0]) is not dict:
        raise ValueError('one original label required')
    old = old[0]
    keys = {'valueId', 'channelCateId', 'labelId', 'isUserClick', 'labelType', 'from', 'text', 'propertyId', 'properties'}
    if set(old) != keys or any(type(v) is not str for v in old.values()):
        raise ValueError('exact original label structure required')
    equal(old['propertyId'], '-10000')
    equal(old['labelType'], dep.get('observed_label_type', 'category'))
    category = edit.get('itemCatDTO')
    if type(category) is not dict or any(type(category.get(k)) is not str or not category[k] for k in ('catId', 'catName', 'channelCatId', 'tbCatId')):
        raise ValueError('complete category source required')
    if 'imageInfoDOList' not in protocol['template'] or 'itemLabelExtList' not in protocol['template']:
        raise ValueError('complete image and label request required')
    parts = old['properties'].split(':')
    if len(parts) != 2 or len(parts[0].split('##')) != 2 or len(parts[1].split('##')) != 2:
        raise ValueError('unambiguous properties required')
    equal(parts[0].split('##')[0], '-10000')
    equal(parts[1].split('##')[0], category['channelCatId'])
    equal(old['channelCateId'], category['channelCatId'])
    text = old['text'] or parts[1].split('##')[1]
    equal(text, category['catName'])
    selected = [{**old, 'text': text, 'valueName': text, 'isUserClick': '1'}]
    common = {**CONTROLS, 'title': protocol['before_values']['desc'], 'description': protocol['before_values']['desc'],
              'imageInfos': protocol['template']['imageInfoDOList'],
              **{k: category[k] for k in ('catId', 'catName', 'channelCatId')}}
    for i in range(2):
        request = dep['requests'][i]
        validate_request(request)
        cards = [] if i == 0 else card_source(dep['responses'][0], dep.get('card_source_mode', 'identity'))
        equal(request, {**common, 'currentCardList': cards, 'selectedList': selected, 'uniqueCode': request['uniqueCode']})
        label = selected_label(dep['responses'][i], category, dep.get('observed_label_type', 'category'))
        equal(label['properties'], old['properties'])
        equal(protocol['template']['itemLabelExtList'], [label])
        selected = [label]


def bounded_response(response):
    """Materialize at most 60 KB for the upstream SDK's normal JSON parser."""
    content = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if len(content) + len(chunk) > 60000:
                raise ValueError('recommendation response limit exceeded')
            content.extend(chunk)
        response._content = bytes(content)
        response._content_consumed = True
        return response
    finally:
        response.close()


def bounded_communicate(process, request, timeout):
    """Linux test/runtime boundary: cap both pipes while consuming, never communicate()."""
    deadline = time.monotonic() + timeout
    output = bytearray()
    counts = {'stdout': 0, 'stderr': 0}
    pending = memoryview(request.encode('utf-8'))
    # Capture ownership before wait() reaps the session leader; never signal our host group.
    owned_group = None
    if os.name != 'nt':
        try:
            if os.getsid(process.pid) == process.pid and os.getpgid(process.pid) == process.pid:
                owned_group = process.pid
        except ProcessLookupError:
            pass
    try:
        with selectors.DefaultSelector() as selector:
            for stream, name, event in ((process.stdin, 'stdin', selectors.EVENT_WRITE),
                                         (process.stdout, 'stdout', selectors.EVENT_READ),
                                         (process.stderr, 'stderr', selectors.EVENT_READ)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(process.args, timeout)
                for key, _ in selector.select(remaining):
                    stream, name = key.fileobj, key.data
                    if name == 'stdin':
                        try:
                            sent = os.write(stream.fileno(), pending[:8192])
                            pending = pending[sent:]
                        except BrokenPipeError:
                            pending = pending[len(pending):]
                        if not pending:
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 8192)
                        if not chunk:
                            selector.unregister(stream)
                            continue
                        counts[name] += len(chunk)
                        if counts[name] > (65000 if name == 'stdout' else 8192):
                            raise ValueError('recommendation output limit exceeded')
                        if name == 'stdout':
                            output.extend(chunk)
            process.wait(timeout=max(.001, deadline - time.monotonic()))
        return output.decode('utf-8', errors='strict')
    finally:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            elif owned_group is not None:
                try:
                    os.killpg(owned_group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()


def frozen_requests(protocol, codes):
    requests = copy.deepcopy(protocol['label_dependency']['requests'])
    if len(codes) != 2 or len(set(codes)) != 2:
        raise ValueError('two distinct frozen read codes required')
    for request, code in zip(requests, codes):
        request['uniqueCode'] = code
        validate_request(request)
    return requests
