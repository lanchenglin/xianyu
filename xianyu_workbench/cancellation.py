"""Private parent-to-bridge cancellation, portable across Linux and Windows."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path


@asynccontextmanager
async def cancellation_scope():
    filename = os.environ.get('XY_BRIDGE_CANCEL_FILE')
    if not filename:
        yield
        return
    owner = asyncio.current_task()

    async def watch():
        while not Path(filename).exists():
            await asyncio.sleep(0.05)
        owner.cancel()  # Once only: allow finally blocks to await page/transport cleanup.

    watcher = asyncio.create_task(watch())
    try:
        yield
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
