from pathlib import Path

import pytest


def test_discovery_prefers_chrome(monkeypatch):
    from xianyu_workbench import browser_config as b
    monkeypatch.setattr(b.shutil, 'which', lambda name: '/bin/' + name if name in ('google-chrome', 'chromium') else None)
    monkeypatch.setattr(b, '_usable', lambda path: True)
    assert b.discover().kind == 'chrome'


@pytest.mark.parametrize('available,kind', [('chromium', 'chromium'), ('google-chrome', 'chrome')])
def test_only_one_browser(monkeypatch, available, kind):
    from xianyu_workbench import browser_config as b
    monkeypatch.setattr(b.shutil, 'which', lambda name: '/bin/' + name if name == available else None)
    monkeypatch.setattr(b, '_usable', lambda path: str(path) == '/bin/' + available)
    assert b.discover().kind == kind


def test_absent_and_explicit_fail_closed(monkeypatch):
    from xianyu_workbench import browser_config as b
    monkeypatch.setattr(b.shutil, 'which', lambda name: '/bin/chromium' if name == 'chromium' else None)
    monkeypatch.setattr(b, '_usable', lambda path: str(path) == '/bin/chromium')
    for mode, path in [('chrome', ''), ('auto', '/missing/private-path')]:
        with pytest.raises(b.BrowserError) as exc:
            b.discover(mode, path)
        assert 'private-path' not in str(exc.value)
    monkeypatch.setattr(b, '_usable', lambda path: False)
    with pytest.raises(b.BrowserError):
        b.discover()


def test_explicit_path(tmp_path):
    from xianyu_workbench.browser_config import discover
    executable = tmp_path / 'custom chromium'
    executable.touch()
    executable.chmod(0o700)
    assert discover('chromium', str(executable)).executable == str(executable)


def test_windows_standard_paths(monkeypatch):
    from xianyu_workbench import browser_config as b
    monkeypatch.setattr(b.shutil, 'which', lambda name: None)
    monkeypatch.setattr(b.sys, 'platform', 'win32')
    monkeypatch.setenv('PROGRAMFILES', 'C:\\Program Files')
    monkeypatch.setattr(b, '_usable', lambda path: str(path) == str(Path('C:\\Program Files') / 'Google/Chrome/Application/chrome.exe'))
    assert b.discover().kind == 'chrome'
