import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from xianyu_workbench.config import Settings
from xianyu_workbench.provider import Problem, Provider
from xianyu_workbench.security import Vault


def test_provider_explicit_environment(tmp_path, monkeypatch):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode(),
                        browser='chromium', browser_executable='/test/chromium')
    vault = Vault(settings.vault_key)
    provider = Provider(settings, MagicMock(), vault)
    monkeypatch.setenv('PRIVATE_SECRET', 'never-forward')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-test')
    process = MagicMock(returncode=0)
    process.communicate.return_value = (json.dumps({'ok': True, 'data': {}}), '')
    popen = MagicMock(return_value=process)
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', popen)
    provider._live({'id': 'fake-account', 'uid': '12345', 'secret': vault.seal({'unb': '12345'})}, 'search', {}, write=False)
    env = popen.call_args.kwargs['env']
    assert env['XY_BROWSER'] == 'chromium'
    assert env['XY_BROWSER_EXECUTABLE'] == '/test/chromium'
    assert env['XY_OPERATION_UID'] == '12345'
    assert env['WAYLAND_DISPLAY'] == 'wayland-test'
    assert 'PRIVATE_SECRET' not in env
    assert not (tmp_path / 'runtime/fake-account/.goofish-cli/cookies.json').exists()


@pytest.mark.parametrize('operation,aid,uid', [('item', 'bound', '12345'), ('message.send', 'bound', '12345'),
                                             ('search', 'other', '12345'), ('search', 'bound', '999')])
def test_provider_cdp_denies_before_subprocess(tmp_path, monkeypatch, operation, aid, uid):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode(),
                        browser_cdp_endpoint='http://127.0.0.1:9999', browser_cdp_account_id='bound', browser_cdp_uid='12345')
    provider = Provider(settings, MagicMock(), Vault(settings.vault_key))
    popen = MagicMock()
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', popen)
    with pytest.raises(Problem):
        provider._live({'id': aid, 'uid': uid, 'secret': ''}, operation, {}, write=operation == 'message.send')
    popen.assert_not_called()


def test_doctor_is_offline_and_redacted(monkeypatch, capsys):
    from xianyu_workbench.cli import main
    monkeypatch.setattr('sys.argv', ['cli', 'doctor'])
    monkeypatch.setenv('XY_BROWSER_EXECUTABLE', '/missing/secret-marker')
    main()
    output = capsys.readouterr().out
    assert 'secret-marker' not in output
    value = json.loads(output)
    assert value['browser']['reason'] == 'browser_path_invalid'
    assert value['browser']['mode'] == 'isolated'


def test_browser_failure_diagnostic_is_actionable(tmp_path, monkeypatch):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode())
    vault = Vault(settings.vault_key)
    provider = Provider(settings, MagicMock(), vault)
    process = MagicMock(returncode=0)
    process.communicate.return_value = (json.dumps({'ok': False, 'code': 'browser_not_found'}), '')
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', MagicMock(return_value=process))
    with pytest.raises(Problem, match='Chrome.*Chromium'):
        provider._live({'id': 'fake', 'uid': '12345', 'secret': vault.seal({'unb': '12345'})}, 'search', {}, write=False)


def test_capabilities_declare_cdp_scope_without_admin_config(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_workbench.app import create_app
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode(), worker_enabled=False)
    with TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + 'b'*40}) as client:
        value = client.get('/api/capabilities').json()
    assert value['browser_policy']['cdp_operations'] == ['search']
    assert value['browser_policy']['cdp_writes'] is False
    assert 'endpoint' not in value['browser_policy']


def test_settings_reject_partial_cdp(tmp_path):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        replace(settings, browser_cdp_endpoint='http://127.0.0.1:9999').validate()
