from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .model import build_snapshot


class SnapshotCache:
    def __init__(self, factory: Callable[[], dict[str, Any]], ttl_seconds: float = 15.0) -> None:
        self.factory = factory
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._value: dict[str, Any] | None = None
        self._expires = 0.0

    def get(self) -> dict[str, Any]:
        with self._lock:
            if self._value is None or time.monotonic() >= self._expires:
                self._value = self.factory()
                self._expires = time.monotonic() + self.ttl_seconds
            return self._value


def make_handler(cache: SnapshotCache) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "twin-subactor/0.1"

        def do_GET(self) -> None:  # noqa: N802
            routes = {
                "/v1/snapshot": lambda value: value,
                "/v1/diagnoses": lambda value: {"snapshotDigest": value["snapshotDigest"], "findings": value["findings"]},
                "/v1/next-actions": lambda value: {"snapshotDigest": value["snapshotDigest"], "nextActions": value["nextActions"]},
            }
            if self.path == "/health":
                self._json(200, {"status": "ok", "acts": False})
                return
            if self.path not in routes:
                self._json(404, {"error": "not-found"})
                return
            try:
                snapshot = cache.get()
                self._json(200, routes[self.path](snapshot))
            except Exception as error:  # fail closed at the adapter boundary
                self._json(503, {"error": "snapshot-unavailable", "reason": type(error).__name__})

        def _json(self, status: int, value: Any) -> None:
            body = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(config: Path, host: str, port: int, ttl_seconds: float, offline: bool) -> None:
    cache = SnapshotCache(lambda: build_snapshot(config, offline=offline), ttl_seconds)
    server = ThreadingHTTPServer((host, port), make_handler(cache))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
