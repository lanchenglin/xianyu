"""Read readiness only from the freshly launched test browser's private profile."""
import re
import time


def wait_for_cdp_port(process, profile, timeout=15):
    deadline = time.monotonic() + timeout
    port_file = profile / 'DevToolsActivePort'
    while time.monotonic() < deadline:
        assert process.poll() is None, 'isolated Chromium exited before CDP readiness'
        try:
            content = port_file.read_text(encoding='utf-8')
        except (FileNotFoundError, UnicodeError):
            content = ''
        # Require the line terminator: a numeric prefix may still be a partial write.
        match = re.match(r'([0-9]{1,5})\r?\n', content)
        if match and 1 <= int(match[1]) <= 65535:
            assert process.poll() is None, 'isolated Chromium exited before CDP readiness'
            if time.monotonic() < deadline:
                return int(match[1])
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(.1, remaining))
    raise AssertionError('isolated Chromium CDP readiness deadline exceeded')
