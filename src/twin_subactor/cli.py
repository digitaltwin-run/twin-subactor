from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .model import build_snapshot
from .service import serve

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config/sources.json"


def _emit(value: Any) -> None:
    json.dump(value, sys.stdout, sort_keys=True, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="twin-subactor")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--offline", action="store_true", help="disable GitHub and Control observations")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot")
    commands.add_parser("diagnose")
    commands.add_parser("recommend")
    watch = commands.add_parser("watch")
    watch.add_argument("--interval", type=float, default=15.0)
    watch.add_argument("--once", action="store_true")
    service = commands.add_parser("serve")
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=8188)
    service.add_argument("--ttl", type=float, default=15.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        serve(args.config, args.host, args.port, args.ttl, args.offline)
        return 0
    previous = None
    while True:
        snapshot = build_snapshot(args.config, offline=args.offline)
        if args.command == "snapshot":
            _emit(snapshot)
        elif args.command == "diagnose":
            _emit({"snapshotDigest": snapshot["snapshotDigest"], "findings": snapshot["findings"]})
        elif args.command == "recommend":
            _emit({"snapshotDigest": snapshot["snapshotDigest"], "nextActions": snapshot["nextActions"]})
        elif snapshot["snapshotDigest"] != previous:
            _emit(
                {
                    "capturedAt": snapshot["capturedAt"],
                    "snapshotDigest": snapshot["snapshotDigest"],
                    "repositories": len(snapshot["repositories"]),
                    "findings": len(snapshot["findings"]),
                    "nextActions": len(snapshot["nextActions"]),
                }
            )
            previous = snapshot["snapshotDigest"]
        if args.command != "watch" or args.once:
            break
        time.sleep(max(1.0, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
