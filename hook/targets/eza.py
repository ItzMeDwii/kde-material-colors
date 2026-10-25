"""eza: generated ~/.config/eza/theme.yml (truecolor hex values)."""

from __future__ import annotations

import shutil
from pathlib import Path

import managed

NAME = "eza"


def _dir() -> Path:
    return Path.home() / ".config" / "eza"


def available(_ctx) -> bool:
    return shutil.which("eza") is not None


def _theme(ctx) -> str:
    p = ctx.palette
    a = lambda name: p.ansi_named(name)  # noqa: E731
    fg = p.fg
    outline = p.role("outline")
    selection_bg = p.role("surfaceVariant")

    def entry(color: str, *, bold=False, dim=False, underline=False, bg=None) -> str:
        parts = [f'foreground: "{color}"']
        if bg:
            parts.append(f'background: "{bg}"')
        if bold:
            parts.append("is_bold: true")
        if dim:
            parts.append("is_dimmed: true")
        if underline:
            parts.append("is_underline: true")
        return "{" + ", ".join(parts) + "}"

    # (section, key) -> style
    simple: dict[tuple[str, str], str] = {
        ("filekinds", "normal"): entry(fg),
        ("filekinds", "directory"): entry(p.role("primary"), bold=True),
        ("filekinds", "symlink"): entry(a("cyan")),
        ("filekinds", "pipe"): entry(a("yellow")),
        ("filekinds", "block_device"): entry(a("yellow"), bold=True),
        ("filekinds", "char_device"): entry(a("yellow"), bold=True),
        ("filekinds", "socket"): entry(a("red"), bold=True),
        ("filekinds", "special"): entry(a("yellow")),
        ("filekinds", "executable"): entry(a("green"), bold=True),
        ("filekinds", "mount_point"): entry(p.role("primary"), bold=True, underline=True),
        ("perms", "user_read"): entry(a("yellow")),
        ("perms", "user_write"): entry(a("red"), bold=True),
        ("perms", "user_execute_file"): entry(a("green"), bold=True),
        ("perms", "user_execute_other"): entry(a("green"), bold=True),
        ("perms", "group_read"): entry(a("yellow")),
        ("perms", "group_write"): entry(a("red")),
        ("perms", "group_execute"): entry(a("green")),
        ("perms", "other_read"): entry(a("yellow")),
        ("perms", "other_write"): entry(a("red")),
        ("perms", "other_execute"): entry(a("green")),
        ("perms", "special_user_file"): entry(a("magenta")),
        ("perms", "special_other"): entry(a("magenta")),
        ("perms", "attribute"): entry(outline),
        ("size", "major"): entry(a("green"), bold=True),
        ("size", "minor"): entry(a("green")),
        ("size", "number_byte"): entry(a("green"), bold=True),
        ("size", "number_kilo"): entry(a("green"), bold=True),
        ("size", "number_mega"): entry(a("green"), bold=True),
        ("size", "number_giga"): entry(a("green"), bold=True),
        ("size", "number_huge"): entry(a("green"), bold=True),
        ("size", "unit_byte"): entry(a("green")),
        ("size", "unit_kilo"): entry(a("green")),
        ("size", "unit_mega"): entry(a("green")),
        ("size", "unit_giga"): entry(a("green")),
        ("size", "unit_huge"): entry(a("green")),
        ("users", "user_you"): entry(a("yellow"), bold=True),
        ("users", "user_root"): entry(fg),
        ("users", "user_other"): entry(fg),
        ("users", "group_yours"): entry(a("yellow"), bold=True),
        ("users", "group_other"): entry(fg),
        ("users", "group_root"): entry(fg),
        ("links", "normal"): entry(a("red"), bold=True),
        ("links", "multi_link_file"): entry(a("red"), bg=a("yellow")),
        ("git", "new"): entry(a("green")),
        ("git", "modified"): entry(p.role("tertiary")),
        ("git", "deleted"): entry(a("red")),
        ("git", "renamed"): entry(a("yellow")),
        ("git", "typechange"): entry(a("magenta")),
        ("git", "ignored"): entry(outline, dim=True),
        ("git", "conflicted"): entry(a("red")),
        ("git_repo", "branch_main"): entry(a("green")),
        ("git_repo", "branch_other"): entry(a("yellow")),
        ("git_repo", "git_clean"): entry(a("green")),
        ("git_repo", "git_dirty"): entry(a("yellow")),
        ("security_context", "colon"): entry(outline, dim=True),
        ("security_context", "user"): entry(p.role("tertiary")),
        ("security_context", "role"): entry(a("green")),
        ("security_context", "typ"): entry(a("yellow")),
        ("security_context", "range"): entry(a("cyan")),
        ("file_type", "image"): entry(a("magenta")),
        ("file_type", "video"): entry(a("magenta"), bold=True),
        ("file_type", "music"): entry(a("cyan")),
        ("file_type", "lossless"): entry(a("cyan"), bold=True),
        ("file_type", "crypto"): entry(a("green"), bold=True),
        ("file_type", "document"): entry(a("green")),
        ("file_type", "compressed"): entry(a("red")),
        ("file_type", "temp"): entry(a("white")),
        ("file_type", "compiled"): entry(a("yellow")),
        ("file_type", "build"): entry(a("yellow"), bold=True, underline=True),
        ("file_type", "source"): entry(a("yellow"), bold=True),
    }
    scalars = {
        "punctuation": entry(p.role("secondary")),
        "date": entry(p.role("tertiary")),
        "inode": entry(a("magenta")),
        "blocks": entry(a("cyan")),
        "header": entry(fg, underline=True),
        "octal": entry(a("magenta")),
        "flags": entry(fg),
        "symlink_path": entry(a("cyan")),
        "control_char": entry(a("red")),
        "broken_symlink": entry(a("red")),
        "broken_path_overlay": entry(fg, underline=True),
    }

    lines = [f"# Generated by the {managed.MARKER} (Material You {p.variant})", ""]
    current = None
    for (section, key), style in simple.items():
        if section != current:
            lines.append(f"{section}:")
            current = section
        lines.append(f"  {key}: {style}")
    lines.append("")
    for key, style in scalars.items():
        lines.append(f"{key}: {style}")
    lines += [
        "",
        "filenames:",
        "  # custom filename overrides go here",
        "extensions:",
        "  # custom extension overrides go here",
        "",
    ]
    return "\n".join(lines)


def apply(ctx) -> None:
    ctx.write(_dir() / "theme.yml", _theme(ctx))
