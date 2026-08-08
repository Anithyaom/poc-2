"""Celery ⟷ Tortoise bridge.

Celery's prefork worker is sync; Tortoise is async-only. Each task owns its own
event loop AND its own ORM lifecycle — `Tortoise.init` / `close_connections` go
*inside* the task, never at worker startup. A prefork child that inherits a loop
or an asyncpg pool across the fork fails with "attached to a different loop".
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

from tortoise import Tortoise

from src.config.database import TORTOISE_ORM


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _wrapped() -> T:
        await Tortoise.init(config=TORTOISE_ORM)
        try:
            return await coro
        finally:
            await Tortoise.close_connections()

    return asyncio.run(_wrapped())
