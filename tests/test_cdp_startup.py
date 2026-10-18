"""Deterministic startup races; no browser or CDP connection."""
from types import SimpleNamespace

import pytest

from tests import cdp_startup
from tests import test_page_state_probe as probe


@pytest.mark.parametrize('first', ['', '\n', 'not-a-port\n', '0\n', '65536\n', '123', '１２３\n'])
def test_fixture_waits_for_complete_valid_port(tmp_path, monkeypatch, first):
    profile = tmp_path / 'probe-profile'
    profile.mkdir()
    port_file = profile / 'DevToolsActivePort'
    port_file.write_text(first)
    sleeps = []
    stopped = []
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: stopped.append(True), wait=lambda **kw: None)
    monkeypatch.setenv('XY_TEST_CHROMIUM', '/fictional/chromium')
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *a, **k: process)
    def publish_port(seconds):
        sleeps.append(seconds)
        port_file.write_text('43210\n/devtools/browser/fixture\n')
    monkeypatch.setattr(cdp_startup.time, 'sleep', publish_port)
    fixture = probe.isolated_cdp.__wrapped__(tmp_path)
    try:
        assert next(fixture) == 'http://127.0.0.1:43210'
        assert sleeps
    finally:
        fixture.close()
    assert stopped == [True]


@pytest.mark.parametrize('content', [None, '', '123', '65536\n'])
def test_readiness_deadline_is_bounded(tmp_path, monkeypatch, content):
    if content is not None:
        (tmp_path / 'DevToolsActivePort').write_text(content)
    now = [0.0]
    monkeypatch.setattr(cdp_startup.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cdp_startup.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    with pytest.raises(AssertionError, match='deadline'):
        cdp_startup.wait_for_cdp_port(SimpleNamespace(poll=lambda: None), tmp_path, timeout=.25)
    assert now[0] == .25


def test_child_exits_during_port_read(tmp_path, monkeypatch):
    (tmp_path / 'DevToolsActivePort').write_text('43210\n')
    polls = iter([None, 1])
    with pytest.raises(AssertionError, match='exited'):
        cdp_startup.wait_for_cdp_port(SimpleNamespace(poll=lambda: next(polls)), tmp_path)


def test_port_file_appears_after_first_read(tmp_path, monkeypatch):
    def publish(seconds):
        (tmp_path / 'DevToolsActivePort').write_text('43210\n')
    monkeypatch.setattr(cdp_startup.time, 'sleep', publish)
    assert cdp_startup.wait_for_cdp_port(SimpleNamespace(poll=lambda: None), tmp_path) == 43210


def test_fixture_rejects_port_when_child_exited(tmp_path, monkeypatch):
    profile = tmp_path / 'probe-profile'
    profile.mkdir()
    (profile / 'DevToolsActivePort').write_text('43210\n/devtools/browser/fixture\n')
    process = SimpleNamespace(poll=lambda: 1, terminate=lambda: None, wait=lambda **kw: None)
    monkeypatch.setenv('XY_TEST_CHROMIUM', '/fictional/chromium')
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *a, **k: process)
    fixture = probe.isolated_cdp.__wrapped__(tmp_path)
    try:
        with pytest.raises(AssertionError, match='exited'):
            next(fixture)
    finally:
        fixture.close()
