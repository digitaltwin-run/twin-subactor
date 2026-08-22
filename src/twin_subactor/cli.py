from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .evolution import load_purpose, next_process_token
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
    evolve = commands.add_parser("evolve")
    evolve.add_argument("--purpose", type=Path, required=True)
    evolve.add_argument("--interval", type=float, default=15.0)
    evolve.add_argument("--once", action="store_true")
    evolve.add_argument("--max-tokens", type=int, default=0, help="0 keeps the event-driven stream alive")
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
    purpose = load_purpose(args.purpose) if args.command == "evolve" else None
    previous = None
    previous_token_digest = None
    emitted = 0
    while True:
        snapshot = build_snapshot(args.config, offline=args.offline)
        if args.command == "snapshot":
            _emit(snapshot)
        elif args.command == "diagnose":
            _emit({"snapshotDigest": snapshot["snapshotDigest"], "findings": snapshot["findings"]})
        elif args.command == "recommend":
            _emit({"snapshotDigest": snapshot["snapshotDigest"], "nextActions": snapshot["nextActions"]})
        elif args.command == "evolve":
            token = next_process_token(
                snapshot,
                purpose,
                sequence=emitted,
                previous_token_digest=previous_token_digest,
            )
            if token["decisionDigest"] != previous:
                _emit(token)
                previous = token["decisionDigest"]
                previous_token_digest = token["tokenDigest"]
                emitted += 1
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
        if args.command not in {"watch", "evolve"} or args.once:
            break
        if args.command == "evolve" and args.max_tokens > 0 and emitted >= args.max_tokens:
            break
        time.sleep(max(1.0, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
