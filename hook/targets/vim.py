"""vim: generated colorscheme + an autoloaded plugin that applies it."""

from __future__ import annotations

import shutil
from pathlib import Path

import managed
from mycolors import (
    ensure_contrast,
    nearest_named,
    oklch_to_rgb,
    parse_hex,
    rgb_to_oklch,
    to_hex,
)

NAME = "vim"

# Syntax colours derived from a palette anchor: OKLCH hue rotation only;
# lightness/chroma default to whatever the palette gives the anchor in this
# variant (per-token overrides allowed), then contrast-checked vs the bg.
# name -> (anchor M3 role, hue, lightness | None, chroma | None)
DERIVED: dict[str, tuple[str, float, float | None, float | None]] = {
    "keyword": ("primary", 296.0, None, 0.08),   # purple
    "string": ("primary", 95.0, 0.78, 0.09),     # warm yellow
    "number": ("error", 48.0, None, None),       # orange (from the error anchor)
    "preproc": ("primary", 128.0, None, 0.07),   # green
    "special": ("primary", 340.0, None, 0.09),   # pink
}

# Highlight groups: (group, fg token, bg role, attrs). Tokens: DERIVED names,
# ANSI slot names, bg/fg/cursor specials, or M3 role names from the KMYC JSON.
GROUPS: list[tuple[str, str | None, str | None, str]] = [
    ("Normal", "fg", "bg", ""),
    ("Comment", "onSurfaceVariant", None, "italic"),
    ("Constant", "number", None, ""),
    ("String", "string", None, ""),
    ("Character", "string", None, ""),
    ("Number", "number", None, ""),
    ("Boolean", "number", None, ""),
    ("Identifier", "fg", None, ""),
    ("Function", "primary", None, "bold"),
    ("Statement", "keyword", None, ""),
    ("Conditional", "keyword", None, ""),
    ("Repeat", "keyword", None, ""),
    ("Label", "keyword", None, ""),
    ("Operator", "onSurfaceVariant", None, ""),
    ("Keyword", "keyword", None, ""),
    ("Exception", "error", None, ""),
    ("PreProc", "preproc", None, ""),
    ("Include", "preproc", None, ""),
    ("Define", "preproc", None, ""),
    ("Macro", "preproc", None, ""),
    ("PreCondit", "preproc", None, ""),
    ("Type", "tertiaryFixedDim", None, ""),
    ("StorageClass", "keyword", None, ""),
    ("Structure", "tertiaryFixedDim", None, ""),
    ("Typedef", "tertiaryFixedDim", None, ""),
    ("Special", "special", None, ""),
    ("SpecialChar", "special", None, ""),
    ("Tag", "special", None, ""),
    ("Delimiter", "onSurfaceVariant", None, ""),
    ("SpecialComment", "onSurfaceVariant", None, "italic"),
    ("Debug", "error", None, ""),
    ("Underlined", None, None, "underline"),
    ("Ignore", "outline", None, ""),
    ("Error", "error", None, ""),
    ("Todo", "keyword", "surfaceVariant", "bold"),
    ("ErrorMsg", "error", "bg", ""),
    ("WarningMsg", "number", None, ""),
    ("ModeMsg", "primary", None, "bold"),
    ("MoreMsg", "primary", None, ""),
    ("Question", "primary", None, ""),
    ("Title", "primary", None, "bold"),
    ("Visual", None, "selection_bg", ""),
    ("VisualNOS", None, "selection_bg", ""),
    ("Search", None, "secondaryContainer", ""),
    ("IncSearch", "bg", "primary", "bold"),
    ("MatchParen", "primary", "surfaceVariant", "bold"),
    ("Cursor", "bg", "primary", ""),
    ("CursorLineNr", "primary", None, "bold"),
    ("LineNr", "outline", None, ""),
    ("VertSplit", "outline", None, ""),
    ("StatusLine", "fg", "surfaceContainerHigh", ""),
    ("StatusLineNC", "outline", "surfaceContainerLow", ""),
    ("Pmenu", "fg", "surfaceContainerHigh", ""),
    ("PmenuSel", "onPrimaryContainer", "primaryContainer", "bold"),
    ("PmenuSbar", None, "surfaceContainerHigh", ""),
    ("PmenuThumb", None, "outline", ""),
    ("TabLine", "outline", "surfaceContainerLow", ""),
    ("TabLineFill", None, "surfaceContainerLow", ""),
    ("TabLineSel", "fg", "surfaceContainerHigh", "bold"),
    ("WildMenu", "onPrimaryContainer", "primaryContainer", "bold"),
    ("Folded", "outline", "surfaceContainerLow", ""),
    ("FoldColumn", "outline", "bg", ""),
    ("SignColumn", "outline", "bg", ""),
    ("ColorColumn", None, "surfaceContainer", ""),
    ("CursorLine", None, "surfaceContainer", ""),
    ("CursorColumn", None, "surfaceContainer", ""),
    ("Directory", "primary", None, ""),
    ("DiffAdd", "preproc", "surfaceContainer", ""),
    ("DiffChange", "string", "surfaceContainer", ""),
    ("DiffDelete", "error", "surfaceContainer", ""),
    ("DiffText", None, "selection_bg", ""),
    ("SpellBad", "error", None, "underline"),
    ("SpellCap", "number", None, "underline"),
    ("SpellRare", "special", None, "underline"),
    ("NonText", "outlineVariant", None, ""),
    ("SpecialKey", "outline", None, ""),
    ("Whitespace", "outlineVariant", None, ""),
]


def _dir() -> Path:
    return Path.home() / ".vim"


def available(_ctx) -> bool:
    return shutil.which("vim") is not None


def _derived(p, anchor: str, hue: float, lightness: float | None, chroma: float | None) -> str:
    base_l, base_c, _base_h = rgb_to_oklch(parse_hex(p.role(anchor)))
    color = to_hex(
        oklch_to_rgb((
            base_l if lightness is None else lightness,
            base_c if chroma is None else chroma,
            hue,
        ))
    )
    return ensure_contrast(color, p.bg, 4.5)


def _resolve(ctx, token: str) -> tuple[str, int]:
    """Return (hex, cterm-index) for a derived / ANSI / special / role token."""
    p = ctx.palette
    if token == "selection_bg":
        token = "surfaceVariant"
    if token in DERIVED:
        color = _derived(p, *DERIVED[token])
    elif token in p.ANSI_NAMES:
        color = p.ansi_named(token)
    elif token in ("bg", "fg", "cursor", "cursor_text", "selection_fg"):
        color = {"bg": p.bg, "fg": p.fg, "cursor": p.cursor, "cursor_text": p.cursor_text,
                 "selection_fg": p.selection_fg}[token]
    else:
        color = p.role(token)
    cterm = _cterm_index(p, color)
    return color, cterm


def _cterm_index(palette, color: str) -> int:
    names = {name: palette.ansi[index] for index, name in enumerate(palette.ANSI_NAMES)}
    return palette.ANSI_NAMES.index(nearest_named(color, names))


def _colorscheme(ctx) -> str:
    p = ctx.palette
    lines = [
        f'" Generated by the {managed.MARKER} (Material You {p.variant})',
        'hi clear',
        'if exists("syntax_on")',
        '  syntax reset',
        'endif',
        "let g:colors_name = 'material-you'",
        f"set background={'dark' if p.is_dark else 'light'}",
        '',
    ]
    for group, fg_tok, bg_tok, attrs in GROUPS:
        parts = []
        if fg_tok:
            color, cterm = _resolve(ctx, fg_tok)
            parts.append(f"guifg={color} ctermfg={cterm}")
        if bg_tok:
            color, cterm = _resolve(ctx, bg_tok)
            parts.append(f"guibg={color} ctermbg={cterm}")
        if attrs:
            parts.append(f"gui={attrs} cterm={attrs}")
        else:
            parts.append("gui=NONE cterm=NONE")
        lines.append("hi " + group + " " + " ".join(parts))
    return "\n".join(lines) + "\n"


def _plugin(ctx) -> str:
    return f"""\" Generated by the {managed.MARKER} (Material You {ctx.palette.variant})
\" Set g:material_you_never_apply = 1 to keep vim's own colours.
if !get(g:, 'material_you_never_apply', 0)
  silent! colorscheme material-you
endif
"""


def apply(ctx) -> None:
    ctx.write(_dir() / "colors" / "material-you.vim", _colorscheme(ctx))
    ctx.write(_dir() / "plugin" / "material-you.vim", _plugin(ctx))
