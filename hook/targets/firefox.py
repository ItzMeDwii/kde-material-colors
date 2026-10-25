"""Firefox (pywalfox): feed the M3 palette to pywalfox with M3 contrast pairings.

pywalfox reads pywal's cache (~/.cache/wal/colors.json), which KMYC exports
before the hook runs, and builds its Firefox theme out of seven ANSI slots and
two derived backgrounds (extension ``dist/background.js``):

    dark   background=color0  backgroundLight=color0*2.25  backgroundExtra=color0*2.85
           text=color15  textFocus=#ffffff  accentPrimary=color10  accentSecondary=color13
    light  background=color7*1.1  backgroundLight=#ffffff  backgroundExtra=color7
           text=color0*2.25  textFocus=color0  accentPrimary=color3  accentSecondary=color5

So ``color0`` is the window frame *and* the colour pywalfox brightens into the
toolbar/URL-bar backgrounds: it has to be the palette's darkest surface, which in
M3 is ``surface`` rather than the terminal's ANSI black (``surfaceVariant``, a mid
tone - it leaves URL-bar text at 4.2:1). The light-theme accents (``color3``/
``color5``) take the M3 **light** scheme's ``primary``/``secondary``: a light
Firefox theme then keeps legible accents instead of the muted dark-scheme
``secondary`` (1.7:1 on white). ANSI white/bright white are already ``onSurface``,
which is what pywalfox uses for its text slots.

pywalfox applies the palette at Firefox start or on ``pywalfox update``, which
talks to the daemon the extension spawns (UNIX socket in the temp dir).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import managed
from mycolors import Palette

NAME = "firefox"

#: pywalfox ANSI slot -> M3 role (dark theme slots / light theme slots).
DARK_SLOTS = {"color0": "surface", "color10": "primary", "color13": "secondary"}
LIGHT_SLOTS = {"color3": "primary", "color5": "secondary"}


def _wal_colors() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "wal" / "colors.json"


def _daemon_socket() -> Path:
    return Path(tempfile.gettempdir()) / f"pywalfox_socket_{os.getuid()}"


def _light_palette(ctx) -> Palette:
    scheme = (ctx.raw.get("schemes") or {}).get("light")
    if not isinstance(scheme, dict) or not scheme:
        return ctx.palette
    return Palette(scheme, "light")


def available(_ctx) -> bool:
    return shutil.which("pywalfox") is not None and _wal_colors().exists()


def apply(ctx) -> None:
    """Rewrite pywal's colors.json with the M3-derived palette."""
    path = _wal_colors()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        managed.log().warning("firefox: cannot read %s: %s", path, exc)
        return

    p = ctx.palette
    light = _light_palette(ctx)
    colors = {f"color{index}": color for index, color in enumerate(p.ansi)}
    for slot, role in DARK_SLOTS.items():
        colors[slot] = p.role(role)
    for slot, role in LIGHT_SLOTS.items():
        colors[slot] = light.role(role)

    data["colors"] = colors
    special = data.setdefault("special", {})
    special["background"] = p.bg
    special["foreground"] = p.fg
    special["cursor"] = p.cursor

    if ctx.dry_run:
        managed.log().info("dry-run: would rewrite %s with M3 colours", path)
        return
    managed.atomic_write(path, json.dumps(data, indent=4) + "\n")
    ctx.changed[str(path)] = True
    ctx.files[str(path)] = managed.file_hash(path)


def reload(ctx) -> None:
    if ctx.dry_run:
        return
    if not _daemon_socket().exists():
        managed.log().info("firefox: pywalfox not running; palette applies on next Firefox start")
        return
    try:
        result = subprocess.run(
            ["pywalfox", "update"], capture_output=True, text=True, check=False, timeout=20
        )
        if result.returncode == 0:
            managed.log().info("firefox: pywalfox palette updated")
        else:
            managed.log().warning("firefox: pywalfox update: %s", result.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        managed.log().warning("firefox: pywalfox update failed: %s", exc)
