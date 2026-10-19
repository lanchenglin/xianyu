"""Read readiness only from the freshly launched test browser's private profile."""
import asyncio
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


async def wait_for_task_pages_closed(context, original, timeout=3):
    """Observe close events only; a leaked target must fail, never be hidden by cleanup."""
    deadline = asyncio.get_running_loop().time() + timeout
    while context.pages != [original]:
        assert original in context.pages, 'original page lost'
        pages = [page for page in context.pages if page is not original]
        changed = asyncio.Event()
        def closed(*args):
            changed.set()
        for page in pages:
            page.on('close', closed)
        try:
            if context.pages == [original]:
                return
            await asyncio.wait_for(changed.wait(), max(0, deadline - asyncio.get_running_loop().time()))
        except TimeoutError:
            raise AssertionError('task pages still present after close-event deadline') from None
        finally:
            for page in pages:
                page.remove_listener('close', closed)
