"""Administrator-only browser discovery. No upstream imports or browser connections."""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


class BrowserError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BrowserChoice:
    kind: str
    executable: str


def _usable(path: str | Path) -> bool:
    return Path(path).is_file() and os.access(path, os.X_OK)


def candidates() -> list[BrowserChoice]:
    found = []
    for kind, names in [('chrome', ('google-chrome', 'google-chrome-stable', 'chrome')),
                        ('chromium', ('chromium', 'chromium-browser'))]:
        paths = [shutil.which(name) for name in names]
        if sys.platform == 'win32':
            suffix = 'Google/Chrome/Application/chrome.exe' if kind == 'chrome' else 'Chromium/Application/chrome.exe'
            paths += [str(Path(os.environ[key]) / suffix) for key in
                      ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMW6432', 'LOCALAPPDATA') if os.environ.get(key)]
        elif sys.platform.startswith('linux'):
            paths += ['/opt/google/chrome/chrome'] if kind == 'chrome' else ['/snap/bin/chromium']
        for path in paths:
            if path and _usable(path) and not any(x.executable == path for x in found):
                found.append(BrowserChoice(kind, path))
    return found


def discover(mode: str = 'auto', executable: str = '') -> BrowserChoice:
    if mode not in ('auto', 'chrome', 'chromium'):
        raise BrowserError('browser_config_invalid')
    if executable:
        if not Path(executable).is_absolute() or not _usable(executable):
            raise BrowserError('browser_path_invalid')
        return BrowserChoice(mode if mode != 'auto' else 'explicit', executable)
    for choice in candidates():
        if mode == 'auto' or choice.kind == mode:
            return choice
    raise BrowserError('browser_not_found')


def diagnostic() -> dict:
    address = os.environ.get('XY_BROWSER_CDP_ENDPOINT', '')
    result = {'mode': 'cdp' if address else 'isolated',
              'discovered': sorted({c.kind for c in candidates()}),
              'selected': None, 'reason': None, 'connection_checked': False}
    try:
        if address:
            from .cdp import endpoint
            endpoint(address)
            if not os.environ.get('XY_BROWSER_CDP_ACCOUNT_ID') or not os.environ.get('XY_BROWSER_CDP_UID', '').isdecimal():
                raise BrowserError('cdp_binding_required')
            result['selected'] = 'existing_browser'
            result['supported_operations'] = ['search']
        else:
            result['selected'] = discover(os.environ.get('XY_BROWSER', 'auto'), os.environ.get('XY_BROWSER_EXECUTABLE', '')).kind
    except (BrowserError, ValueError) as exc:
        result['reason'] = exc.code if isinstance(exc, BrowserError) else 'cdp_config_invalid'
    return result
