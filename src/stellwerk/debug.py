from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, List


@dataclass(frozen=True)
class DebugEvent:
    ts: float
    level: str
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ts": self.ts,
            "level": self.level,
            "message": self.message,
        }
        if self.data:
            payload["data"] = self.data
        return payload


class DebugBus:
    def __init__(self, *, max_events: int = 500):
        self._buffer: Deque[DebugEvent] = deque(maxlen=max_events)
        self._subscribers: List[asyncio.Queue[DebugEvent]] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: DebugEvent) -> None:
        async with self._lock:
            self._buffer.append(event)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    # Drop if subscriber is too slow.
                    pass

    async def snapshot(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [e.to_dict() for e in list(self._buffer)]

    async def subscribe(self) -> asyncio.Queue[DebugEvent]:
        q: asyncio.Queue[DebugEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[DebugEvent]) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


_bus = DebugBus(max_events=800)


def _sanitize_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    # Never allow obvious secrets.
    redacted_keys = {"openai_api_key", "api_key", "authorization", "Authorization", "token"}
    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        if k in redacted_keys:
            sanitized[k] = "***"
        else:
            # Keep logs readable; avoid dumping huge blobs.
            if isinstance(v, str) and len(v) > 1000:
                sanitized[k] = v[:1000] + "…(truncated)"
            else:
                sanitized[k] = v
    return sanitized


async def debug_log(level: str, message: str, data: dict[str, Any] | None = None) -> None:
    await _bus.publish(
        DebugEvent(ts=time.time(), level=level, message=message, data=_sanitize_data(data))
    )


async def debug_snapshot() -> list[dict[str, Any]]:
    return await _bus.snapshot()


async def debug_subscribe() -> asyncio.Queue[DebugEvent]:
    return await _bus.subscribe()


async def debug_unsubscribe(q: asyncio.Queue[DebugEvent]) -> None:
    await _bus.unsubscribe(q)


def sse_encode(event: dict[str, Any]) -> str:
    # Simple SSE encoding; keep it compact and robust.
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
