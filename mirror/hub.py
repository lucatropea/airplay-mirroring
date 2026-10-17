from __future__ import annotations

import threading
import time


class FrameHub:
    """Latest JPEG frame from the iPad. Slow clients skip intermediate frames."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._jpeg: bytes | None = None
        self._seq = 0
        self._fps = 0.0
        self._size = (0, 0)
        self._window_started = time.perf_counter()
        self._frames = 0

    def publish(self, jpeg: bytes, size: tuple[int, int]) -> None:
        with self._condition:
            self._jpeg = jpeg
            self._seq += 1
            self._size = size
            self._frames += 1
            now = time.perf_counter()
            elapsed = now - self._window_started
            if elapsed >= 1:
                self._fps = self._frames / elapsed
                self._frames = 0
                self._window_started = now
            self._condition.notify_all()

    def latest(self) -> bytes | None:
        with self._condition:
            return self._jpeg

    def wait_after(self, seq: int, timeout: float) -> tuple[int, bytes] | None:
        with self._condition:
            if self._seq <= seq or self._jpeg is None:
                self._condition.wait(timeout)
            if self._seq <= seq or self._jpeg is None:
                return None
            return self._seq, self._jpeg

    def snapshot(self) -> dict[str, float | int]:
        with self._condition:
            width, height = self._size
            return {
                "fps": round(self._fps, 1),
                "width": width,
                "height": height,
            }
