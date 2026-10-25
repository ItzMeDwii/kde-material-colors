"""Steam (Millennium): Material-Theme colours from the KMYC Material You palette.

Target file follows the theme's own instruction (``matugentemplate.css``): matugen
writes ``~/.steam/steam/millennium/themes/Material-Theme/css/main/colors/matugen.css``
(``STEAM_ROOTS`` below resolves that symlink to the same file); verified live in a
running client - the theme repaints within ~2 s, no Steam restart needed.

With ``Color: Matugen`` selected, Material-Theme's ``js/main/colors/matugen.js``
fetches ``css/main/colors/matugen.css`` out of the installed theme folder every
1.5 s and injects it verbatim, so writing that file is enough to recolour Steam
live (no Steam restart).  matugen itself would render it from
``matugentemplate.css``; this target renders the same token set from the KMYC
palette instead, so no matugen installation is needed.

The theme's other colour source is ``--custom-accent-color``
(``css/main/root-colors.css``, exposed as a Millennium ``themeColors`` override,
consumed by ``js/main/colors/custom.js`` for ``Color: Custom/Dynamic``); it gets
the palette's key colour so both modes follow Material You.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import managed
from mycolors import parse_hex, to_hex

NAME = "steam-material-theme"

#: Material-Theme installed by Millennium under ``<steam>/millennium/themes``.
THEME_REPO = ("kuska1", "Material-Theme")
THEME_NAME = "Material-Theme"

#: matugen output path inside the theme (``matugentemplate.css``).
MATUGEN_CSS = Path("css") / "main" / "colors" / "matugen.css"

STEAM_ROOTS = (
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "steam",
    Path.home() / ".steam" / "root",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
)

#: ``--md-sys-color-*`` token (matugen naming, matugen's output order)
#: -> KMYC/M3 role.  ``source-color`` is matugen's seed colour; KMYC exposes the
#: equivalent as the primary tonal palette's key colour.
COLORS = {
    "background": "background",
    "error": "error",
    "error-container": "errorContainer",
    "inverse-on-surface": "inverseOnSurface",
    "inverse-primary": "inversePrimary",
    "inverse-surface": "inverseSurface",
    "on-background": "onBackground",
    "on-error": "onError",
    "on-error-container": "onErrorContainer",
    "on-primary": "onPrimary",
    "on-primary-container": "onPrimaryContainer",
    "on-primary-fixed": "onPrimaryFixed",
    "on-primary-fixed-variant": "onPrimaryFixedVariant",
    "on-secondary": "onSecondary",
    "on-secondary-container": "onSecondaryContainer",
    "on-secondary-fixed": "onSecondaryFixed",
    "on-secondary-fixed-variant": "onSecondaryFixedVariant",
    "on-surface": "onSurface",
    "on-surface-variant": "onSurfaceVariant",
    "on-tertiary": "onTertiary",
    "on-tertiary-container": "onTertiaryContainer",
    "on-tertiary-fixed": "onTertiaryFixed",
    "on-tertiary-fixed-variant": "onTertiaryFixedVariant",
    "outline": "outline",
    "outline-variant": "outlineVariant",
    "primary": "primary",
    "primary-container": "primaryContainer",
    "primary-fixed": "primaryFixed",
    "primary-fixed-dim": "primaryFixedDim",
    "scrim": "scrim",
    "secondary": "secondary",
    "secondary-container": "secondaryContainer",
    "secondary-fixed": "secondaryFixed",
    "secondary-fixed-dim": "secondaryFixedDim",
    "shadow": "shadow",
    "source-color": "primaryPaletteKeyColor",
    "surface": "surface",
    "surface-bright": "surfaceBright",
    "surface-container": "surfaceContainer",
    "surface-container-high": "surfaceContainerHigh",
    "surface-container-highest": "surfaceContainerHighest",
    "surface-container-low": "surfaceContainerLow",
    "surface-container-lowest": "surfaceContainerLowest",
    "surface-dim": "surfaceDim",
    "surface-tint": "surfaceTint",
    "surface-variant": "surfaceVariant",
    "tertiary": "tertiary",
    "tertiary-container": "tertiaryContainer",
    "tertiary-fixed": "tertiaryFixed",
    "tertiary-fixed-dim": "tertiaryFixedDim",
}


def _config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "millennium"


def _config() -> dict:
    try:
        return json.loads((_config_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _is_material_theme(theme: Path) -> bool:
    try:
        metadata = json.loads((theme / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metadata = {}
    owner, repo = metadata.get("owner"), metadata.get("repo")
    if not owner or not repo:
        try:
            skin = json.loads((theme / "skin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        github = skin.get("github") or {}
        owner, repo = github.get("owner"), github.get("repo_name")
    return (owner, repo) == THEME_REPO


def _installed() -> list[Path]:
    found: list[Path] = []
    for root in STEAM_ROOTS:
        themes = root / "millennium" / "themes"
        if not themes.is_dir():
            continue
        for theme in sorted(themes.iterdir()):
            path = Path(os.path.realpath(theme))
            if path.is_dir() and path not in found and _is_material_theme(path):
                found.append(path)
    return found


def _active_theme() -> Path | None:
    active = (_config().get("themes") or {}).get("activeTheme")
    for theme in _installed():
        if theme.name == active:
            return theme
    return None


def available(_ctx) -> bool:
    theme = _active_theme()
    return theme is not None and (theme / MATUGEN_CSS).parent.is_dir()


def _css(palette) -> str:
    """The theme's matugen stylesheet, rendered byte-similar to matugen's output."""
    blocks = [':root {\n    --theme-color: "Matugen";\n    --hue-rotate: 0deg;\n']
    for token, role in COLORS.items():
        red, green, blue = parse_hex(palette.role(role))
        blocks.append(f"    --md-sys-color-{token}: rgb({red}, {green}, {blue});\n")
    return "\n".join(blocks) + "\n}\n"


def _apply_accent(ctx) -> None:
    """``--custom-accent-color`` (Custom/Dynamic mode) = palette key colour."""
    config_path = _config_dir() / "config.json"
    data = _config()
    themes = data.get("themes")
    if not isinstance(themes, dict):
        managed.log().warning("steam-material-theme: %s has no themes object", config_path)
        return
    stored = themes.setdefault("themeColors", {}).setdefault(THEME_NAME, {})
    if not isinstance(stored, dict):
        managed.log().warning("steam-material-theme: %s has broken colors for %s", config_path, THEME_NAME)
        return
    accent = to_hex(parse_hex(ctx.palette.role("primaryPaletteKeyColor")))
    if stored.get("--custom-accent-color") != accent:
        if ctx.dry_run:
            managed.log().info("dry-run would set %s in %s", accent, config_path)
        else:
            stored["--custom-accent-color"] = accent
            managed.backup_once(config_path)
            managed.atomic_write(config_path, json.dumps(data, indent=2))
            managed.log().info("steam-material-theme: set --custom-accent-color %s", accent)
    ctx.track(config_path)


def _warn_on_color_mode() -> None:
    mode = (
        (_config().get("themes") or {}).get("conditions", {}).get(THEME_NAME, {}).get("Color")
    )
    if mode != "Matugen":
        managed.log().warning(
            "steam-material-theme: Color is %r, not 'Matugen'; matugen.css is only loaded in Matugen mode",
            mode,
        )


def apply(ctx) -> None:
    theme = _active_theme()
    if theme is None:
        managed.log().warning("steam-material-theme: Material-Theme is not the active Millennium theme")
        return
    _warn_on_color_mode()
    ctx.write(theme / MATUGEN_CSS, _css(ctx.palette))
    _apply_accent(ctx)
