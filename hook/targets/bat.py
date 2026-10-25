"""bat: generated .tmTheme + `--theme` in bat's config, then cache rebuild."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import managed

NAME = "bat"
THEME_NAME = "material-you"


def _dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "bat"


def available(_ctx) -> bool:
    return shutil.which("bat") is not None


def _tmtheme(ctx) -> str:
    p = ctx.palette
    fg, bg = p.fg, p.bg
    a = lambda name: p.ansi_named(name)  # noqa: E731 - short local alias

    def setting(name: str, scope: str, fg_color: str, style: str | None = None) -> str:
        style_xml = (
            f"<key>fontStyle</key><string>{style}</string>" if style else ""
        )
        return (
            "<dict>"
            f"<key>name</key><string>{name}</string>"
            f"<key>scope</key><string>{scope}</string>"
            "<key>settings</key><dict>"
            f"<key>foreground</key><string>{fg_color}</string>"
            f"{style_xml}"
            "</dict></dict>"
        )

    general = (
        "<dict><key>settings</key><dict>"
        f"<key>background</key><string>{bg}</string>"
        f"<key>foreground</key><string>{fg}</string>"
        f"<key>caret</key><string>{p.cursor}</string>"
        f"<key>selection</key><string>{p.selection_bg}</string>"
        f"<key>selectionForeground</key><string>{p.selection_fg}</string>"
        f"<key>lineHighlight</key><string>{p.role('surfaceContainerHigh')}</string>"
        f"<key>gutter</key><string>{p.role('surfaceContainerLow')}</string>"
        f"<key>gutterForeground</key><string>{p.role('outline')}</string>"
        f"<key>findHighlight</key><string>{p.role('secondary')}</string>"
        f"<key>findHighlightForeground</key><string>{bg}</string>"
        "</dict></dict>"
    )

    entries = [
        setting("Comment", "comment, punctuation.definition.comment", p.role("outline"), "italic"),
        setting("String", "string", a("green")),
        setting("String regexp", "string.regexp", a("cyan")),
        setting("String escape", "string constant.character.escape", a("cyan")),
        setting("Number", "constant.numeric", a("yellow")),
        setting("Constant", "constant, support.constant, constant.language", a("magenta")),
        setting("Keyword", "keyword, storage", a("magenta")),
        setting("Storage type", "storage.type, storage.modifier", a("magenta")),
        setting("Variable", "variable", fg),
        setting("Variable parameter", "variable.parameter", p.role("secondary")),
        setting("Function", "entity.name.function, meta.function-call, support.function", a("green")),
        setting("Class", "entity.name.class, entity.name.type, support.class, support.type", a("yellow")),
        setting("Tag", "entity.name.tag", a("red")),
        setting("Attribute", "entity.other.attribute-name", a("yellow")),
        setting("Constant other", "constant.other", a("yellow")),
        setting("Operator", "keyword.operator", p.role("secondary")),
        setting("Punctuation", "punctuation, meta.punctuation", fg),
        setting("Markup heading", "markup.heading", p.role("primary"), "bold"),
        setting("Markup bold", "markup.bold", fg, "bold"),
        setting("Markup italic", "markup.italic", fg, "italic"),
        setting("Markup link", "markup.underline.link", a("cyan"), "underline"),
        setting("Diff inserted", "markup.inserted, meta.diff.header.to-file", a("green")),
        setting("Diff deleted", "markup.deleted, meta.diff.header.from-file", a("red")),
    ]
    invalid = (
        "<dict><key>name</key><string>Invalid</string>"
        "<key>scope</key><string>invalid, invalid.illegal</string>"
        "<key>settings</key><dict>"
        f"<key>background</key><string>{p.role('error')}</string>"
        f"<key>foreground</key><string>{p.role('onError')}</string>"
        "</dict></dict>"
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        f"<key>name</key><string>{THEME_NAME}</string>\n"
        "<key>settings</key><array>\n"
        + "\n".join([general, invalid] + entries)
        + "\n</array></dict></plist>\n"
    )


def apply(ctx) -> None:
    theme = _dir() / "themes" / f"{THEME_NAME}.tmTheme"
    changed = ctx.write(theme, _tmtheme(ctx))
    config = _dir() / "config"
    if not config.exists() or "material-you" in config.read_text(encoding="utf-8"):
        managed.set_arg_line(config, "--theme", THEME_NAME)
        ctx.changed[str(config)] = True
        ctx.track(config)
    if changed and not ctx.dry_run:
        try:
            subprocess.run(
                ["bat", "cache", "--build"],
                capture_output=True,
                check=False,
                timeout=30,
            )
            managed.log().info("bat: cache rebuilt")
        except (OSError, subprocess.TimeoutExpired) as exc:
            managed.log().warning("bat: cache rebuild failed: %s", exc)
