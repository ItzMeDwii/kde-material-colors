"""Pear Desktop (YouTube Music): Material You theme for the default UI.

Pear Desktop loads user CSS from ``options.themes`` in
``$XDG_CONFIG_HOME/YouTube Music/config.json`` (``initTheme`` ->
``injectCSSAsFile`` in src/index.ts); every listed file is injected into the
renderer when the window is created. The hook writes ``material-you.css`` into
that config directory and keeps its path registered in the themes list, so the
default interface follows the KMYC M3 palette. Restart Pear Desktop to apply a
new palette - themes are read once, at startup.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import managed
from template import render

NAME = "pear-desktop"

TEMPLATE = "pear-desktop.css"
THEME_FILE = "material-you.css"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "YouTube Music"
)


def available(_ctx) -> bool:
    return CONFIG_DIR.is_dir()


def apply(ctx) -> None:
    template = (TEMPLATE_DIR / TEMPLATE).read_text(encoding="utf-8")
    rendered, warnings = render(template, ctx.raw, ctx.palette.variant)
    if warnings:
        managed.log().warning(
            "pear-desktop: %s unresolved expression(s)", len(warnings)
        )
    header = (
        f"/* Rendered by the {managed.MARKER} (Material You {ctx.palette.variant})\n"
        f" * Source: hook/templates/{TEMPLATE} */\n"
    )
    ctx.write(CONFIG_DIR / THEME_FILE, header + rendered)
    _register_theme(ctx)


def _register_theme(ctx) -> None:
    """Ensure ``options.themes`` lists the generated stylesheet (electron-store JSON)."""
    config_path = CONFIG_DIR / "config.json"
    theme_path = str(CONFIG_DIR / THEME_FILE)
    if not config_path.exists():
        managed.log().warning(
            "pear-desktop: %s not found; theme written but not enabled", config_path
        )
        return
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        managed.log().warning("pear-desktop: cannot parse %s: %s", config_path, exc)
        return
    options = data.get("options")
    if not isinstance(options, dict):
        options = {}
        data["options"] = options
    themes = options.get("themes")
    if not isinstance(themes, list):
        themes = []
    if theme_path not in themes:
        if not ctx.dry_run:
            options["themes"] = [*themes, theme_path]
            managed.backup_once(config_path)
            managed.atomic_write(
                config_path, json.dumps(data, indent="\t", ensure_ascii=False)
            )
            managed.log().info("pear-desktop: enabled %s", theme_path)
        else:
            managed.log().info("dry-run would enable %s", theme_path)
    ctx.track(config_path)
