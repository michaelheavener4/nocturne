from __future__ import annotations

import json, time
from pathlib import Path


class LocalTelemetry:
    """Append-only local metrics; no audio or prompt payloads are sent anywhere."""

    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, operation: str, started: float, success: bool, tool_calls: int = 0, tokens: int | None = None, manual_corrections: int = 0) -> None:
        event = {"operation": operation, "latency_ms": round((time.perf_counter()-started)*1000, 2), "success": success, "tool_calls": tool_calls, "tokens": tokens, "manual_corrections": manual_corrections}
        with self.path.open("a") as f: f.write(json.dumps(event) + "\n")
