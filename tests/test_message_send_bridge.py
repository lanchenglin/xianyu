from tests.test_upstream_contract import isolated


def test_cdp_send_bridge_uses_same_uid_without_browser_cookie_fallback(tmp_path):
    result = isolated('''
        import json, os
        from types import SimpleNamespace
        os.environ.update(XY_BROWSER_CDP_ENDPOINT='http://127.0.0.1:19876',
            XY_BROWSER_CDP_ACCOUNT_ID='fictional', XY_OPERATION_ACCOUNT_ID='fictional',
            XY_BROWSER_CDP_UID='11', XY_OPERATION_UID='11', XY_MESSAGE_SEND_ENABLED='true')
        from goofish_cli.core.session import Session
        Session.load = lambda: SimpleNamespace(unb='11')
        import importlib
        module = importlib.import_module('goofish_cli.commands.message.send')
        async def fake_send(session, **kwargs):
            return {'uid': session.unb, 'payload': kwargs, 'mid': 'local-only'}
        module._send = fake_send
        from xianyu_workbench.bridge import dispatch
        print(json.dumps(dispatch('message.send', {'cid':'123','toid':'22','text':'hello'})))
    ''', tmp_path)
    assert result['uid'] == '11'
    assert result['payload'] == {'cid': '123', 'toid': '22', 'text': 'hello', 'kind': 'text',
                                 'image_url': '', 'image_width': 0, 'image_height': 0, 'item_id': ''}
    assert result.get('delivery_confirmed') is not True
