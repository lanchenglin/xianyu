"""Fictional userConvs fixtures; never read real messages."""
import copy

import pytest

from xianyu_workbench import operations


def frame():
    return {'code': 200, 'body': {'hasMore': 0, 'nextCursor': 0, 'userConvs': [
        {'singleChatUserConversation': {
            'singleChatConversation': {'cid': '123@goofish', 'pairFirst': '11@goofish',
                                       'pairSecond': '22@goofish'},
            'lastMessage': {'message': {'cid': '123@goofish', 'messageId': '987654',
                'createAt': 1780000000000, 'sender': {'uid': '22@goofish'},
                'content': {'contentType': 101, 'custom': {'data': 'unknown'}},
                'searchableContent': {'summary': 'NOT BODY'}}}}}]}}


def parse(value):
    return operations.normalize_messages(value, '11')


def test_observed_opaque_id_preserved_exactly():
    data = frame()
    data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']['messageId'] = '1234567890123.AbC'
    assert parse(data)['items'][0]['message_id'] == '1234567890123.AbC'


@pytest.mark.parametrize('value', ['a/b', '../a', 'a\\b', 'x\n', 'x\x00', 'a' * 129, '中文', 'a b'])
def test_unsafe_opaque_id_rejected(value):
    data = frame()
    data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message']['messageId'] = value
    with pytest.raises(ValueError):
        parse(data)


def test_last_message_metadata_never_guesses_body():
    result = parse(frame())
    assert result['partial'] and result['completion'] == 'last_message_samples'
    assert result['items'] == [{'message_id': '987654', 'cid': '123', 'sender_uid': '22',
        'created_at': 1780000000000, 'direction': 'incoming', 'body': None,
        'body_status': 'unavailable', 'recipient_verified': True, 'peer_uid': '22'}]


@pytest.mark.parametrize('field,value', [('messageId', ''), ('messageId', True),
    ('createAt', True), ('createAt', -1), ('createAt', 1780000000), ('createAt', '1780000000000'),
    ('cid', '456@goofish'), ('sender', {}), ('sender', {'uid': 'bad uid'})])
def test_invalid_metadata_is_not_cached(field, value):
    data = frame()
    data['body']['userConvs'][0]['singleChatUserConversation']['lastMessage']['message'][field] = value
    with pytest.raises(ValueError):
        parse(data)


def test_missing_last_message_is_skipped_and_self_is_distinguished():
    data = frame()
    conv = data['body']['userConvs'][0]['singleChatUserConversation']
    conv['lastMessage']['message']['sender']['uid'] = '11@goofish'
    data['body']['userConvs'].append({'singleChatUserConversation': {'singleChatConversation': {'cid': '456'}}})
    assert parse(data)['items'][0]['direction'] == 'outgoing'
    del conv['lastMessage']
    assert parse(data)['items'] == []


def test_duplicate_stable_identity_and_conflict():
    data = frame()
    data['body']['userConvs'] *= 2
    assert len(parse(data)['items']) == 1
    data = copy.deepcopy(frame())
    other = copy.deepcopy(data['body']['userConvs'][0])
    other['singleChatUserConversation']['lastMessage']['message']['createAt'] += 1
    data['body']['userConvs'].append(other)
    with pytest.raises(ValueError, match='duplicate_conflict'):
        parse(data)


def test_bounded_frame_and_failure_status():
    data = frame()
    data['body']['userConvs'] *= 101
    with pytest.raises(ValueError):
        parse(data)
    data = frame()
    data['code'] = 500
    with pytest.raises(ValueError):
        parse(data)
