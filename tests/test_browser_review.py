import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from xianyu_workbench.config import Settings
from xianyu_workbench.provider import Problem, Provider


def test_cdp_provider_never_opens_imported_secret(tmp_path, monkeypatch):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode(),
                        browser_cdp_endpoint='http://127.0.0.1:9999', browser_cdp_account_id='fake', browser_cdp_uid='12345')
    vault = MagicMock()
    vault.open.side_effect = AssertionError('must not decrypt')
    process = MagicMock(returncode=0)
    process.communicate.return_value = (json.dumps({'ok': True, 'data': {}}), '')
    def spawn(*args, **kwargs):
        assert 'GOOFISH_COOKIES_PATH' not in kwargs['env']
        assert not list(tmp_path.rglob('cookies.json'))
        return process
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', spawn)
    Provider(settings, MagicMock(), vault)._live({'id': 'fake', 'uid': '12345', 'secret': 'unreadable'}, 'search', {}, write=False)
    vault.open.assert_not_called()


@pytest.mark.parametrize('write', [False, True])
def test_timeout_requests_cleanup_before_kill_and_never_succeeds(tmp_path, monkeypatch, write):
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode())
    vault = MagicMock()
    vault.open.return_value = {'unb': '12345'}
    process = MagicMock(returncode=0)
    captured = {}
    def communicate(*args, **kwargs):
        if not captured.get('timed_out'):
            captured['timed_out'] = True
            raise subprocess.TimeoutExpired('bridge', 120)
        assert Path(captured['env']['XY_BRIDGE_CANCEL_FILE']).exists()
        assert 0 < kwargs['timeout'] <= 10
        return (json.dumps({'ok': True, 'data': {}}), '')
    process.communicate.side_effect = communicate
    def spawn(*args, **kwargs):
        captured['env'] = kwargs['env']
        return process
    monkeypatch.setattr('xianyu_workbench.provider.subprocess.Popen', spawn)
    kill = MagicMock()
    monkeypatch.setattr('xianyu_workbench.provider.os.killpg', kill, raising=False)
    with pytest.raises(Problem) as error:
        Provider(settings, MagicMock(), vault)._live({'id': 'fake', 'uid': '12345', 'secret': 'fake'},
                                                     'message.send' if write else 'search', {}, write=write)
    assert error.value.code == ('uncertain' if write else 'timeout')
    kill.assert_not_called()


def test_bridge_cancelled_result_is_not_success(monkeypatch, capsys):
    import io

    from xianyu_workbench import bridge
    monkeypatch.setattr(bridge.sys, 'stdin', io.StringIO('{"operation":"search","payload":{}}'))
    def cancelled(*args):
        raise asyncio.CancelledError
    monkeypatch.setattr(bridge, 'dispatch', cancelled)
    bridge.main()
    assert json.loads(capsys.readouterr().out) == {'ok': False, 'code': 'timeout'}


@pytest.mark.parametrize('platform', ['posix', 'nt'])
def test_unresponsive_bridge_force_kill_is_bounded(tmp_path, monkeypatch, platform):
    import xianyu_workbench.provider as module
    settings = Settings(tmp_path, 'a'*40, 'b'*40, Fernet.generate_key().decode())
    vault = MagicMock()
    vault.open.return_value = {'unb': '12345'}
    process = MagicMock(pid=123456)
    calls = []
    def communicate(*args, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls) < 3:
            raise subprocess.TimeoutExpired('bridge', kwargs['timeout'])
        return ('', '')
    process.communicate.side_effect = communicate
    # Replace only the provider's os reference; never change global os.name/Path semantics.
    from types import SimpleNamespace
    # Simulate the selected platform's signal API independently of the host.
    # NT deliberately has no SIGKILL; POSIX supplies a token checked below.
    simulated_sigkill = object()
    monkeypatch.setattr(module, 'signal', SimpleNamespace(
        **({'SIGKILL': simulated_sigkill} if platform == 'posix' else {})))
    proxy = SimpleNamespace(**vars(module.os))
    proxy.name = platform
    proxy.killpg = MagicMock()
    monkeypatch.setattr(module, 'os', proxy)
    monkeypatch.setattr(module.subprocess, 'Popen', MagicMock(return_value=process))
    taskkill = MagicMock(side_effect=subprocess.TimeoutExpired('taskkill', 10) if platform == 'nt' else None)
    monkeypatch.setattr(module.subprocess, 'run', taskkill)
    with pytest.raises(Problem) as error:
        Provider(settings, MagicMock(), vault)._live({'id': 'fake', 'uid': '12345', 'secret': 'fake'},
                                                     'message.send', {}, write=True)
    assert error.value.code == 'uncertain'
    assert calls == [120, 8, 5]
    if platform == 'nt':
        taskkill.assert_called_once_with(['taskkill', '/PID', '123456', '/T', '/F'], capture_output=True, timeout=10)
        proxy.killpg.assert_not_called()
    else:
        proxy.killpg.assert_called_once_with(123456, simulated_sigkill)
        taskkill.assert_not_called()


def test_cooperative_cancel_unwinds_owned_page(tmp_path, monkeypatch):
    from xianyu_workbench.cancellation import cancellation_scope
    cancel = tmp_path / 'cancel'
    monkeypatch.setenv('XY_BRIDGE_CANCEL_FILE', str(cancel))
    cleaned = []
    async def run():
        with pytest.raises(asyncio.CancelledError):
            async with cancellation_scope():
                try:
                    cancel.touch()
                    await asyncio.sleep(3)
                finally:
                    cleaned.append(True)
    asyncio.run(run())
    assert cleaned == [True]
