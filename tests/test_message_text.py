import base64
import json

import pytest
from test_messages import frame, parse


def text_frame(text='还有吗？', kind=1):
    data = frame()
    message = data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']
    message['messageId'] = '1234567890123.Abc'
    message['content'] = {'contentType': 101, 'custom': {'type': kind,
        'data': base64.b64encode(json.dumps({'contentType': kind, 'text': {'text': text}}).encode()).decode(),
        'summary': 'never body', 'degrade': 'never body'}}
    return data


@pytest.mark.parametrize('custom_type,decoded_type,outer_type', [(14, 14, 101), (1, 14, 101), (True, 1, 101), (1, True, 101), (1, 1, True)])
def test_only_consistent_integer_plain_text_types(custom_type, decoded_type, outer_type):
    data = text_frame()
    message = data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']
    message['content'] = {'contentType': outer_type, 'custom': {'type': custom_type,
        'data': base64.b64encode(json.dumps({'contentType': decoded_type, 'text': {'text': 'not ordinary'},
                                           'tip': {'tip': 'not ordinary'}}).encode()).decode()}}
    assert parse(data)['items'][0]['body'] is None


def test_plain_text_and_verified_peer():
    item = parse(text_frame())['items'][0]
    assert item['body'] == '还有吗？' and item['body_status'] == 'available'
    assert item['recipient_verified'] and item['peer_uid'] == '22'
    assert 'custom' not in item


@pytest.mark.parametrize('damage', ['tip', 'mismatch', 'bool', 'bad64', 'oversize', 'deep', 'nodes', 'longtext', 'duplicate'])
def test_unknown_or_malformed_body_unavailable(damage):
    data = text_frame()
    content = data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']['content']
    custom = content['custom']
    if damage == 'tip':
        custom['type'] = 14
    elif damage == 'mismatch':
        custom['data'] = base64.b64encode(b'{"contentType":14,"text":{"text":"no"}}').decode()
    elif damage == 'bool':
        custom['type'] = True
    elif damage == 'bad64':
        custom['data'] += '!'
    elif damage == 'oversize':
        custom['data'] = 'A' * 50000
    elif damage == 'longtext':
        data = text_frame('x' * 4001)
    else:
        raw = {'contentType': 1, 'text': {'text': 'no'}}
        if damage == 'deep':
            node = raw
            for _ in range(22):
                node['x'] = {}
                node = node['x']
        elif damage == 'nodes':
            raw['extra'] = [0] * 2100
        encoded = json.dumps(raw).encode() if damage != 'duplicate' else b'{"contentType":14,"contentType":1,"text":{"text":"no"}}'
        custom['data'] = base64.b64encode(encoded).decode()
    item = parse(data)['items'][0]
    assert item['body'] is None and item['body_status'] == 'unavailable'


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity'])
@pytest.mark.parametrize('extra', ['"ignored":%s', '"ignored":{"nested":[%s]}'])
def test_nonstandard_json_constants_make_body_unavailable(constant, extra):
    data = text_frame()
    content = data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']['content']
    raw = '{"contentType":1,"text":{"text":"ordinary"},' + extra % constant + '}'
    content['custom']['data'] = base64.b64encode(raw.encode()).decode()
    item = parse(data)['items'][0]
    assert item['body'] is None
    assert item['body_status'] == 'unavailable'
    assert item['recipient_verified'] and item['peer_uid'] == '22'
    assert item['message_id'] == '1234567890123.Abc'


@pytest.mark.parametrize('pair', [{}, {'pairFirst': '33', 'pairSecond': '22'},
    {'pairFirst': '11', 'pairSecond': '33'}, {'pairFirst': '11', 'pairSecond': '11'}])
def test_unproven_pair_never_authenticates_recipient(pair):
    data = text_frame()
    data['body']['userConvs'][0]['singleChatUserConversation']['singleChatConversation'] = {'cid': '123', **pair}
    item = parse(data)['items'][0]
    assert not item['recipient_verified'] and item.get('peer_uid') is None
