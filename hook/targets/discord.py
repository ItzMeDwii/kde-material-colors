"""Discord: Noctalia's Discord themes rendered with KMYC's M3 colours.

All three themes from Noctalia's community templates
(https://github.com/noctalia-dev/community-templates, discord/) are vendored
verbatim and rendered through the hook's template renderer, so the themes stay
the upstream Noctalia themes while every colour comes from the KMYC JSON:

    discord-material.css   -> noctalia-material.theme.css  (fork of Material Discord)
    discord-midnight.css   -> noctalia.theme.css           (fork of Midnight)
    discord-system24.css   -> discord-system24.css         (fork of system24)

Output goes to the theme folders of Discord clients that use the Vencord theme
loader (Vencord / Vesktop / Webcord / Legcord / Equibop). Enable a theme once in
the client: Vencord -> Themes.
"""

from __future__ import annotations

from pathlib import Path

import managed
from template import render

NAME = "discord"

TEMPLATES = (
    ("discord-material.css", "noctalia-material.theme.css"),
    ("discord-midnight.css", "noctalia.theme.css"),
    ("discord-system24.css", "discord-system24.css"),
)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
OBSOLETE_THEME_FILES = ("material-you.theme.css",)

CLIENT_DIRS = (
    Path.home() / ".config" / "Vencord",
    Path.home() / ".config" / "vesktop",
    Path.home() / ".config" / "webcord",
    Path.home() / ".config" / "legcord",
    Path.home() / ".config" / "equibop",
    Path.home() / ".var" / "app" / "dev.vencord.Vesktop" / "config" / "vesktop",
)


def _clients() -> list[Path]:
    return [d for d in CLIENT_DIRS if d.is_dir()]


def available(_ctx) -> bool:
    return bool(_clients())


def _render(ctx, template_name: str) -> str:
    template_text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    rendered, warnings = render(template_text, ctx.raw, ctx.palette.variant)
    if warnings:
        managed.log().warning(
            "discord: %s has %s unresolved expression(s)", template_name, len(warnings)
        )
    header = (
        f"/* Rendered by the {managed.MARKER} (Material You {ctx.palette.variant})\n"
        f" * Source: noctalia-dev/community-templates discord/{template_name} */\n"
    )
    return header + rendered


def _remove_obsolete(directory: Path) -> None:
    for name in OBSOLETE_THEME_FILES:
        stale = directory / name
        if not stale.exists():
            continue
        try:
            if managed.MARKER in stale.read_text(encoding="utf-8"):
                stale.unlink()
                managed.log().info("discord: removed obsolete %s", stale)
        except OSError as exc:
            managed.log().warning("discord: could not remove %s: %s", stale, exc)


def apply(ctx) -> None:
    rendered = {out: _render(ctx, tpl) for tpl, out in TEMPLATES}
    for client in _clients():
        themes = client / "themes"
        for name, content in rendered.items():
            ctx.write(themes / name, content)
        if not ctx.dry_run:
            _remove_obsolete(themes)
