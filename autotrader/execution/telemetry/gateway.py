from __future__ import annotations

import json
import queue
import socket
import threading
import time
from urllib import request
from typing import Any, Callable, Dict, Optional


class TelemetryEngine:
    """Non-blocking telemetry dispatcher with bounded queue + drop-oldest policy."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9876,
        queue_maxsize: int = 1000,
        sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host
        self.port = int(port)
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=max(1, int(queue_maxsize)))
        self._sink = sink
        self._sequence_id = 0
        self._dropped_events = 0
        self._running = True
        self._lock = threading.Lock()
        self._socket: Optional[socket.socket] = None
        self._worker = threading.Thread(target=self._run_worker, name="telemetry-gateway", daemon=True)
        self._worker.start()

    @property
    def dropped_events(self) -> int:
        return int(self._dropped_events)

    def publish(self, event_type: str, state: str, payload: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._sequence_id += 1
            sequence_id = self._sequence_id

        event = {
            "event_type": str(event_type),
            "timestamp_ms": int(time.time() * 1000),
            "sequence_id": sequence_id,
            "state": str(state),
        }
        if payload:
            event.update(payload)

        self._enqueue_non_blocking(event)

    def shutdown(self, timeout_s: float = 1.0) -> None:
        self._running = False
        self._enqueue_non_blocking({"event_type": "_shutdown"})
        self._worker.join(timeout=max(0.0, float(timeout_s)))
        self._close_socket()

    def _enqueue_non_blocking(self, event: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(event)
            return
        except queue.Full:
            pass

        try:
            self._queue.get_nowait()
            self._dropped_events += 1
        except queue.Empty:
            pass

        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._dropped_events += 1

    def _run_worker(self) -> None:
        while self._running or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if event.get("event_type") == "_shutdown":
                continue

            try:
                self._dispatch(event)
            except Exception:
                # Telemetry failures are intentionally non-fatal to execution paths.
                continue

    def _dispatch(self, event: Dict[str, Any]) -> None:
        if event.get("event_type") == "WEBHOOK_DISPATCH":
            self._dispatch_webhook(event)
            return

        if self._sink is not None:
            self._sink(event)
            return

        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        payload = json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self._socket.sendto(payload, (self.host, self.port))

    def _dispatch_webhook(self, event: Dict[str, Any]) -> None:
        webhook_url = str(event.get("url") or "")
        if not webhook_url:
            return

        payload = event.get("payload") or {}
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

        req = request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=2.0):
            return

    def _close_socket(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.close()
        finally:
            self._socket = None
