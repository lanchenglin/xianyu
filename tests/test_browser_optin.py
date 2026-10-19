"""Reused fixtures must skip before setup without disabling configured browsers."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_page_state_probe import isolated_cdp


def test_imported_browser_fixture_skips_before_environment_lookup():
    env = {k: v for k, v in os.environ.items()
           if k not in ('PYTHONPATH', 'PYTHONHOME') and not k.startswith(('XY_', 'PYTEST_'))}
    env['TMPDIR'] = '/home/lan/.hermes/cache/scratch'
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rs',
        'tests/test_cdp_close_observation.py::test_real_second_observer_close_ack_and_target_destruction'],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 skipped' in result.stdout
    assert 'KeyError' not in result.stdout


def test_configured_invalid_browser_is_not_silently_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv('XY_TEST_CHROMIUM', str(tmp_path / 'nonexistent-chromium'))
    fixture = isolated_cdp.__wrapped__(tmp_path)
    with pytest.raises(FileNotFoundError):
        next(fixture)
