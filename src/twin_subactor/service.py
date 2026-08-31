from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from .account import query_account_projection
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


def make_handler(cache: SnapshotCache, account_database: Path | None = None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "twin-subactor/0.2"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            routes = {
                "/v1/snapshot": lambda value: value,
                "/v1/diagnoses": lambda value: {"snapshotDigest": value["snapshotDigest"], "findings": value["findings"]},
                "/v1/next-actions": lambda value: {"snapshotDigest": value["snapshotDigest"], "nextActions": value["nextActions"]},
            }
            if parsed.path == "/health":
                self._json(200, {"status": "ok", "acts": False})
                return
            account_prefix = "/v1/account/"
            if parsed.path.startswith(account_prefix):
                if account_database is None:
                    self._json(503, {"error": "account-projection-unconfigured"})
                    return
                resource = parsed.path.removeprefix(account_prefix)
                params = parse_qs(parsed.query)
                filters = {
                    key: params.get(key, [""])[0]
                    for key in ("organization", "project", "status", "source", "q")
                }
                try:
                    value = query_account_projection(
                        account_database,
                        resource,
                        filters=filters,
                        limit=int(params.get("limit", ["200"])[0]),
                        offset=int(params.get("offset", ["0"])[0]),
                    )
                    self._json(200, value)
                except FileNotFoundError:
                    self._json(503, {"error": "account-projection-unavailable"})
                except (TypeError, ValueError):
                    self._json(400, {"error": "account-query-invalid"})
                return
            if parsed.path not in routes:
                self._json(404, {"error": "not-found"})
                return
            try:
                snapshot = cache.get()
                self._json(200, routes[parsed.path](snapshot))
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


def serve(
    config: Path,
    host: str,
    port: int,
    ttl_seconds: float,
    offline: bool,
    account_database: Path | None = None,
) -> None:
    cache = SnapshotCache(lambda: build_snapshot(config, offline=offline), ttl_seconds)
    server = ThreadingHTTPServer((host, port), make_handler(cache, account_database))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
