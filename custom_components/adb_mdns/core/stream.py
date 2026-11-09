"""Internal stream management for Android TV ADB client."""

from __future__ import annotations

import asyncio


class _AdbStream:
    """Internal multiplexed ADB stream tracker."""

    def __init__(self, local_id: int) -> None:
        self.local_id = local_id
        self.remote_id: int | None = None
        self.opened = asyncio.Event()
        self.done = asyncio.Event()
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()


__all__ = ["_AdbStream"]
