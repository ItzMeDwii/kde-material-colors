#!/usr/bin/env python3
"""KDE Material You -> everywhere.

Hook entry point for kde-material-you-colors (`on_change_hook` in
~/.config/kde-material-you-colors/config.conf). Reads the JSON written by
KMYC and applies the Material You palette to every supported application.

Usage:
    apply.py [--json PATH] [--dry-run] [--force] [--verbose] [--only NAME]... [--list]
"""

from __future__ import annotations

import argparse
import fcntl
import getpass
import hashlib
import json
import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))

import managed  # noqa: E402
from context import Context  # noqa: E402
from mycolors import load_palette  # noqa: E402
import targets  # noqa: E402

STATE_FILE = HOOK_DIR / "state.json"
LOCK_FILE = HOOK_DIR / ".lock"
LOG_FILE = Path.home() / ".local" / "share" / "kde-material-you-colors" / "hook.log"


def kmyc_json_path() -> Path:
    override = os.environ.get("KMYC_JSON")
    if override:
        return Path(override)
    default = Path(tempfile.gettempdir()) / f"kde-material-you-colors-{getpass.getuser()}.json"
    if default.exists():
        return default
    candidates = sorted(
        p
        for p in Path(tempfile.gettempdir()).glob("kde-material-you-colors-*.json")
    )
    if candidates:
        return candidates[0]
    return default


def setup_logging(verbose: bool) -> None:
    logger = logging.getLogger("kmy-hook")
    logger.setLevel(logging.DEBUG)
    managed.rotate_log(LOG_FILE)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if verbose or sys.stderr.isatty():
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        logger.addHandler(stream)


def palette_hash(palette) -> str:
    payload = json.dumps(
        {"variant": palette.variant, "ansi": palette.ansi, "roles": palette.roles},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        managed.atomic_write(STATE_FILE, json.dumps(state, indent=2) + "\n")
    except OSError as exc:
        managed.log().warning("could not write %s: %s", STATE_FILE, exc)


def up_to_date(state: dict, digest: str) -> bool:
    if state.get("palette") != digest:
        return False
    files = state.get("files") or {}
    if not files:
        return False
    for path, old_hash in files.items():
        current = managed.file_hash(Path(path))
        if not current or current != old_hash:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", help="KMYC JSON (default: /tmp/kde-material-you-colors-$USER.json)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    parser.add_argument("--force", action="store_true", help="ignore the up-to-date check")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="run only this target (repeatable)")
    parser.add_argument("--list", action="store_true", help="list targets and exit")
    args = parser.parse_args()

    setup_logging(args.verbose)
    managed.set_dry_run(args.dry_run)
    log = managed.log()

    if args.list:
        for module in targets.ORDER:
            print(module.NAME)
        return 0

    if args.only:
        unknown = [name for name in args.only if targets.by_name(name) is None]
        if unknown:
            log.error("unknown target(s): %s", ", ".join(unknown))
            return 2

    json_path = Path(args.json_path) if args.json_path else kmyc_json_path()
    if not json_path.exists():
        log.error("KMYC JSON not found: %s", json_path)
        return 1
    data = None
    for attempt in range(3):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            if attempt == 2:
                log.error("cannot read %s: %s", json_path, exc)
                return 1
            time.sleep(0.3)
    try:
        palette = load_palette(data)
    except (KeyError, ValueError) as exc:
        log.error("cannot build palette from %s: %s", json_path, exc)
        return 1

    digest = palette_hash(palette)
    state = load_state()
    if not args.force and not args.dry_run and up_to_date(state, digest):
        log.info("palette %s already applied and files unchanged; nothing to do", digest[:12])
        return 0

    ctx = Context(palette=palette, raw=data, dry_run=args.dry_run)
    selected = [targets.by_name(name) for name in args.only] if args.only else targets.ORDER
    failed = 0
    for module in selected:
        try:
            if not module.available(ctx):
                log.debug("skip %s (not installed)", module.NAME)
                continue
            module.apply(ctx)
        except Exception:  # one broken target must not stop the others
            failed += 1
            log.error("target %s failed:\n%s", module.NAME, traceback.format_exc())

    for module in selected:
        if args.dry_run:
            break
        if not module.available(ctx):
            continue
        try:
            reloader = getattr(module, "reload", None)
            if reloader:
                reloader(ctx)
        except Exception:
            failed += 1
            log.error("reload %s failed:\n%s", module.NAME, traceback.format_exc())

    if args.dry_run:
        log.info("dry-run complete (palette %s, %s)", palette.variant, digest[:12])
        return 1 if failed else 0

    if not args.only:
        save_state({"palette": digest, "files": ctx.files, "variant": palette.variant})
    log.info(
        "applied Material You %s palette%s",
        palette.variant,
        " (with errors)" if failed else "",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    lock_handle = open(LOCK_FILE, "w")  # noqa: SIM115 - kept open for the process lifetime
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another hook instance is running; exiting", file=sys.stderr)
        sys.exit(0)
    try:
        sys.exit(main())
    finally:
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
