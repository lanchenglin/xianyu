import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.test_workbench import account
from tests.test_workbench import workbench as workbench
from xianyu_workbench.provider import Problem


def test_provider_uses_explicit_independent_cookie_source(workbench, monkeypatch):
    client, service = workbench
    from tests.test_message_send_binding import propose, setup_live
    from tests.test_workbench import approve
    original_live = service.provider._live
    aid, _, _ = setup_live(client, service, monkeypatch)
    action = propose(client, aid).json()
    approve(client, action)
    read_fixture = service.provider._live

    def transport(account, operation, payload, *, write):
        if write:
            return original_live(account, operation, payload, write=write)
        return read_fixture(account, operation, payload, write=write)

    monkeypatch.setattr(service.provider, '_live', transport)
    seen = []

    def popen(command, **kwargs):
        env = kwargs['env']
        assert env['XY_MESSAGE_SEND_ENABLED'] == 'true'
        cookie_file = Path(env['GOOFISH_COOKIES_PATH'])
        assert json.loads(cookie_file.read_text())['unb'] == '11'
        seen.append(cookie_file)
        (cookie_file.parent / 'im_token.json').write_text('{"token":"fictional-private"}')
        process = MagicMock(returncode=0)
        process.communicate.return_value = ('{"ok":true,"data":{"mid":"local-only"}}', '')
        return process

    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', popen)
    result = service.execute_one(action['id'], action['digest'])
    assert result['state'] == 'unconfirmed'
    assert result['result']['mid'] == 'local-only'
    assert len(seen) == 1 and not seen[0].exists()
    assert not (seen[0].parent / 'im_token.json').exists()
    with pytest.raises(Problem):
        service.provider.call(aid, 'item.delete', {'item_id': '123'}, write=True)


def test_provider_checks_frozen_credentials_under_operation_lock(workbench, monkeypatch):
    client, service = workbench
    aid = account(client, 'live', '{"unb":"11","_m_h5_tk":"fictional_123456"}')
    service.provider.s = replace(service.s, live_enabled=True, message_send_enabled=True,
        browser_cdp_endpoint='http://127.0.0.1:19876', browser_cdp_account_id=aid, browser_cdp_uid='11')
    with pytest.raises(Problem, match='绑定'):
        service.provider.call(aid, 'message.send', {'cid': '123', 'toid': '22', 'text': '您好'},
                              write=True, expected_binding={'uid': '11', 'credential_digest': 'stale'})


def test_recover_removes_crashed_send_token_cache(workbench):
    _, service = workbench
    private = service.s.data_dir / 'runtime' / 'fictional' / '.goofish-cli'
    private.mkdir(parents=True)
    token = private / 'im_token.json'
    token.write_text('{"token":"fictional"}')
    service.recover()
    assert not token.exists()


def test_bridge_text_payload_rejects_extra_fields_before_import(monkeypatch):
    from xianyu_workbench.bridge import dispatch
    for key, value in {'XY_BROWSER_CDP_ENDPOINT': 'http://127.0.0.1:19876',
        'XY_BROWSER_CDP_ACCOUNT_ID': 'fictional', 'XY_OPERATION_ACCOUNT_ID': 'fictional',
        'XY_BROWSER_CDP_UID': '11', 'XY_OPERATION_UID': '11', 'XY_MESSAGE_SEND_ENABLED': 'true'}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match='text_send_payload'):
        dispatch('message.send', {'cid': '123', 'toid': '22', 'text': '您好', 'item_id': '456'})
