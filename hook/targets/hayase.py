"""Hayase: Material You colours for its built-in "custom" theme.

Hayase's UI (``hayase-app/interface``, shipped inside the Electron app) keeps
its settings in localStorage - ``persist('settings', …)`` from
``svelte-persisted-store`` - so the custom theme is the ``customThemeColors``
map of 19 ``--custom-*`` variables inside the ``settings`` record of the
``https://hayase.app`` Local Storage LevelDB.  That record is exactly what
Settings -> Interface -> Export writes to a file (and Import reads back):
``{theme: 'custom', customThemeColors: {…}}``; the app applies the variables to
``document.documentElement`` on every change and the ``theme-custom`` CSS block
binds them to its ``--background``/``--primary``/… tokens.

The hook renders ``templates/hayase-custom-theme.json`` from the M3 palette into
the app's config directory (same format, so it can still be imported by hand)
and patches the LevelDB record in place: ``theme`` becomes ``"custom"``,
``customThemeColors`` gets the rendered roles and every other setting is kept.
Chromium holds the database open while Hayase runs, so the patch only happens
with Hayase closed - restart it to pick up a new palette.

Role choice follows the app's own defaults: the neutral set maps onto the M3
surface containers (``background``/``card``/``muted``/``popover``/``accent``
walk ``surface`` -> ``surfaceContainerLowest``…``Highest``), ``border`` is
``outlineVariant`` while the stronger ``input`` is ``outline``, filled
``secondary`` is ``secondaryContainer`` (M3's tonal button) and the destructive
pair is ``errorContainer``/``onErrorContainer``, matching Hayase's dark-red
destructive buttons with light text.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import localstorage
import managed
from template import render

NAME = "hayase"

TEMPLATE = "hayase-custom-theme.json"
#: Rendered copy of the app's export format, importable through its own dialog.
THEME_FILE = "material-you-custom-theme.json"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "hayase"
LEVELDB_DIR = CONFIG_DIR / "Local Storage" / "leveldb"
#: Chromium's local storage map key: ``"_" + <serialized storage key> + <map
#: separator> + <script key>`` for origin https://hayase.app, as found in the
#: app's own database.
STORAGE_KEY = b"_https://hayase.app\x00\x01settings"
SETTINGS_KEY = "settings"


def available(_ctx) -> bool:
    return LEVELDB_DIR.is_dir()


def _colors(ctx) -> tuple[dict[str, str], list[str]]:
    template = (TEMPLATE_DIR / TEMPLATE).read_text(encoding="utf-8")
    rendered, warnings = render(template, ctx.raw, ctx.palette.variant)
    return json.loads(rendered), warnings


def _decode(raw: bytes) -> dict:
    """Settings record; Chromium tags the value with its string encoding."""
    tag, body = raw[:1], raw[1:]
    encodings = ("utf-16-le", "latin-1") if tag == b"\x00" else ("latin-1", "utf-16-le")
    for encoding in encodings:
        try:
            return json.loads(body.decode(encoding))
        except (UnicodeDecodeError, ValueError):
            continue
    raise localstorage.StorageError("settings record is not readable JSON")


def _encode(settings: dict) -> bytes:
    """Store as ASCII (valid in every encoding Chromium tags with 0x01)."""
    return b"\x01" + json.dumps(settings, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _backup(directory: Path) -> None:
    """Keep a copy of the database before the first write into it."""
    dest = managed.BACKUP_DIR / str(directory).lstrip("/")
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(directory, dest)
    managed.log().info("backup: %s -> %s", directory, dest)


def _patch(ctx, colors: dict[str, str]) -> None:
    store = localstorage.LocalStorage(LEVELDB_DIR)
    raw = store.read(STORAGE_KEY)
    if raw is None:
        settings: dict = {}
        managed.log().warning(
            "hayase: no %r record in %s yet; only the custom theme is written",
            SETTINGS_KEY,
            LEVELDB_DIR,
        )
    else:
        settings = _decode(raw)

    if settings.get("theme") == "custom" and settings.get("customThemeColors") == colors:
        managed.log().debug("hayase: theme already applied; nothing to patch")
        return

    settings["theme"] = "custom"
    settings["customThemeColors"] = colors
    value = _encode(settings)

    if ctx.dry_run:
        managed.log().info("dry-run would patch %s in %s", SETTINGS_KEY, LEVELDB_DIR)
        return

    if store.locked():
        managed.log().warning(
            "hayase: %s is open (database locked); close Hayase and run the hook again "
            "to apply the palette",
            CONFIG_DIR.name,
        )
        return

    _backup(LEVELDB_DIR)
    store.write(STORAGE_KEY, value)
    store.verify(STORAGE_KEY, value)
    managed.log().info(
        "hayase: theme 'custom' + %d colours, %d settings kept",
        len(colors),
        len(settings),
    )


def apply(ctx) -> None:
    colors, warnings = _colors(ctx)
    if warnings:
        managed.log().warning("hayase: %s unresolved expression(s)", len(warnings))
    ctx.write(CONFIG_DIR / THEME_FILE, json.dumps(colors, indent=2) + "\n")
    _patch(ctx, colors)
