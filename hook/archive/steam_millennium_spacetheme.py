"""Steam (Millennium): SpaceTheme colours from the KMYC Material You palette.

SpaceTheme (SpaceTheme/Steam) keeps its whole palette in 17 ``--st-*`` variables
declared in ``src/css/root.css`` (``RootColors``); Millennium parses that file,
exposes every variable in its theme colour editor and injects the stored values
as a ``:root`` block into every Steam document - the steamui windows *and* the
in-client store/community pages (``theme_config_store::setup_colors`` /
``get_colors``).  The stored values live here:

    config.json -> themes.themeColors.<theme folder> -> "--st-*": "r, g, b"

Values are RawRGB (``rgb(var(--st-x))`` in the theme), so the hook writes
``"r, g, b"`` triples.  Millennium only seeds a variable when the key is absent,
and it writes the whole config back whenever the user edits a theme setting - so
the hook re-applies its palette whenever KMYC changes, but a Steam restart (or a
theme re-select) is what makes the new colours show up.

Role mapping follows M3 (tonal spot) semantics plus the hook's usual accent
convention (green=primary, yellow=secondary, blue=tertiary, red=error, as in
``mycolors``/Noctalia): ``--st-accent-1`` is the accent, the ``*-hover`` slots
take the next lighter tone of the same hue family.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import managed
from mycolors import parse_hex

NAME = "steam-millennium"

#: SpaceTheme/Steam installed by Millennium under ``<steam>/millennium/themes``.
STEAM_REPO = ("SpaceTheme", "Steam")

STEAM_ROOTS = (
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "steam",
    Path.home() / ".steam" / "root",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
)

#: SpaceTheme variable -> M3 role (KMYC JSON / mycolors role names).
COLORS = {
    # Surfaces: the theme's elevation ladder (background -> color-2, lightest).
    "--st-background": "surface",
    "--st-color-1": "surfaceContainerLow",
    "--st-color-3": "surfaceContainer",
    "--st-color-4": "surfaceContainerHigh",
    "--st-color-2": "surfaceContainerHighest",
    "--st-color-6": "surfaceVariant",
    # Borders, dividers and outlines (color-5 is only ever used for outlines).
    "--st-color-5": "outlineVariant",
    # Accents and status colours.
    "--st-accent-1": "primary",
    "--st-green": "primary",
    "--st-yellow": "secondary",
    "--st-blue": "tertiary",
    "--st-red": "error",
    # Hover states: one tone lighter than the base colour of the same family.
    "--st-accent-2": "primaryFixed",
    "--st-green-hover": "primaryFixed",
    "--st-yellow-hover": "secondaryFixed",
    "--st-blue-hover": "tertiaryFixed",
    "--st-red-hover": "onErrorContainer",
}


def _config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "millennium"


def _is_space_theme(theme: Path) -> bool:
    try:
        metadata = json.loads((theme / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metadata = {}
    owner = metadata.get("owner")
    repo = metadata.get("repo")
    if not owner or not repo:
        try:
            skin = json.loads((theme / "skin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        github = skin.get("github") or {}
        owner, repo = github.get("owner"), github.get("repo_name")
    return (owner, repo) == STEAM_REPO


def _installed() -> list[Path]:
    """Installed SpaceTheme folders (Millennium keys ``themeColors`` by name)."""
    found: list[Path] = []
    for root in STEAM_ROOTS:
        themes = root / "millennium" / "themes"
        if not themes.is_dir():
            continue
        for theme in sorted(themes.iterdir()):
            if theme.is_dir() and theme not in found and _is_space_theme(theme):
                found.append(theme)
    return found


def _active_theme() -> Path | None:
    """The installed SpaceTheme folder Millennium has selected, if any."""
    try:
        config = json.loads((_config_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    active = (config.get("themes") or {}).get("activeTheme")
    for theme in _installed():
        if theme.name == active:
            return theme
    return None


def available(_ctx) -> bool:
    return _active_theme() is not None


def _rgb(hex_color: str) -> str:
    """Millennium's RawRGB format (``convert_from_hex``): ``"102, 108, 255"``."""
    return "{}, {}, {}".format(*parse_hex(hex_color))


def apply(ctx) -> None:
    theme = _active_theme()
    if theme is None:
        managed.log().warning("steam-millennium: SpaceTheme is not the active Millennium theme")
        return

    colors = {name: _rgb(ctx.palette.role(role)) for name, role in COLORS.items()}
    config_path = _config_dir() / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        managed.log().warning("steam-millennium: cannot read %s: %s", config_path, exc)
        return

    themes = data.get("themes")
    if not isinstance(themes, dict):
        managed.log().warning("steam-millennium: %s has no themes object", config_path)
        return
    stored = themes.setdefault("themeColors", {})
    if not isinstance(stored, dict):
        managed.log().warning("steam-millennium: %s has a broken themeColors object", config_path)
        return
    current = stored.setdefault(theme.name, {})
    if not isinstance(current, dict):
        managed.log().warning("steam-millennium: %s has broken colors for %s", config_path, theme.name)
        return

    changed = {name: value for name, value in colors.items() if current.get(name) != value}
    if changed:
        if ctx.dry_run:
            managed.log().info(
                "dry-run would set %s colours in %s", len(changed), config_path
            )
        else:
            current.update(changed)
            managed.backup_once(config_path)
            managed.atomic_write(config_path, json.dumps(data, indent=2))
            managed.log().info(
                "steam-millennium: set %s Material You colour(s) for theme %s",
                len(changed),
                theme.name,
            )
    ctx.track(config_path)
