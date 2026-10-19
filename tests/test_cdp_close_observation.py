"""Separate CDP observers can receive targetDestroyed after the owner returns."""
import asyncio
from types import SimpleNamespace

import pytest

from tests.cdp_startup import wait_for_task_pages_closed
from tests.test_page_state_probe import isolated_cdp as isolated_cdp


def test_observer_waits_for_close_event_without_closing_any_page():
    async def check():
        handlers = []
        original = object()
        task = SimpleNamespace(on=lambda event, callback: handlers.append(callback),
                               remove_listener=lambda event, callback: handlers.remove(callback))
        context = SimpleNamespace(pages=[original, task])
        waiter = asyncio.create_task(wait_for_task_pages_closed(context, original, timeout=.2))
        await asyncio.sleep(0)
        assert not waiter.done()
        context.pages.remove(task)
        for callback in list(handlers):
            callback()
        await waiter
        assert context.pages == [original]
        assert not handlers
    asyncio.run(check())


def test_real_second_observer_close_ack_and_target_destruction(isolated_cdp):
    import os
    if not os.getenv('XY_TEST_CHROMIUM'):
        pytest.skip('isolated Chromium opt-in')
    from playwright.async_api import async_playwright
    async def check():
        async with async_playwright() as pw:
            owner = await pw.chromium.connect_over_cdp(isolated_cdp, no_defaults=True)
            observer = await pw.chromium.connect_over_cdp(isolated_cdp, no_defaults=True)
            context = observer.contexts[0]
            original = context.pages[0]
            async with context.expect_page() as appeared:
                task = await owner.contexts[0].new_page()
            observed = await appeared.value
            event = asyncio.Event()
            observed.on('close', lambda *a: event.set())
            await task.close()
            # Independent CDP connections have no cross-connection event ordering guarantee.
            await wait_for_task_pages_closed(context, original)
            assert event.is_set()
            assert context.pages == [original] and not original.is_closed()
            session = await observer.new_browser_cdp_session()
            targets = await session.send('Target.getTargets')
            assert len([t for t in targets['targetInfos'] if t['type'] == 'page']) == 1
            await session.detach()
    asyncio.run(check())


def test_actual_leak_times_out_instead_of_force_closing():
    async def check():
        task = SimpleNamespace(on=lambda *a: None, remove_listener=lambda *a: None)
        original = object()
        context = SimpleNamespace(pages=[original, task])
        with pytest.raises(AssertionError, match='task pages'):
            await wait_for_task_pages_closed(context, original, timeout=.01)
        assert context.pages == [original, task]
    asyncio.run(check())
