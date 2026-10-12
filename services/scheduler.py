"""Small safe scheduler: runs periodic, isolated async jobs without blocking updates."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)
Job = Callable[[], Awaitable[None]]
_tasks: set[asyncio.Task] = set()


async def _loop(name: str, seconds: int, job: Job) -> None:
    while True:
        await asyncio.sleep(seconds)
        try:
            await job()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scheduled task %s failed; it will retry next interval", name)


def start_job(name: str, seconds: int, job: Job) -> None:
    task = asyncio.create_task(_loop(name, seconds, job), name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def stop_jobs() -> None:
    for task in tuple(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
