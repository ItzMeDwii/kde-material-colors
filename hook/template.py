"""Renderer for Noctalia's template syntax.

Supports the expression subset used by the vendored community templates:

    {{ colors.<role>.<mode>.<format> }}     mode: default | dark | light
    {{ mode }}

Role names are Noctalia/M3 snake_case; KMYC's JSON uses camelCase, so names are
converted (``on_surface_variant`` -> ``onSurfaceVariant``). Formats mirror
Noctalia's ``template_engine.cpp`` (hex, hex_stripped, rgb, rgb_csv, rgba, hsl,
hsla, red, green, blue, alpha, hue, saturation, lightness).

Unknown expressions are kept as ``{{UNKNOWN:...}}`` markers (as Noctalia does)
and reported through the returned warnings list.
"""

from __future__ import annotations

import colorsys
import re

import managed
from mycolors import parse_hex

EXPR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

KNOWN_FORMATS = {
    "hex",
    "hex_stripped",
    "rgb",
    "rgb_csv",
    "rgba",
    "hsl",
    "hsla",
    "red",
    "green",
    "blue",
    "alpha",
    "hue",
    "saturation",
    "lightness",
}


def camel(role: str) -> str:
    head, *rest = role.split("_")
    return head + "".join(part.capitalize() for part in rest)


def format_color(hex_color: str, fmt: str, alpha: float = 1.0) -> str:
    red, green, blue = parse_hex(hex_color)
    h, l, s = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    alpha_text = f"{alpha:g}"
    if fmt == "hex":
        return f"#{red:02x}{green:02x}{blue:02x}"
    if fmt == "hex_stripped":
        return f"{red:02x}{green:02x}{blue:02x}"
    if fmt == "rgb":
        return f"rgb({red}, {green}, {blue})"
    if fmt == "rgb_csv":
        return f"{red},{green},{blue}"
    if fmt == "rgba":
        return f"rgba({red}, {green}, {blue}, {alpha_text})"
    if fmt == "hsl":
        return f"hsl({h * 360:.0f}, {s * 100:.0f}%, {l * 100:.0f}%)"
    if fmt == "hsla":
        return f"hsla({h * 360:.0f}, {s * 100:.0f}%, {l * 100:.0f}%, {alpha_text})"
    if fmt == "hue":
        return f"{h * 360:.0f}"
    if fmt == "saturation":
        return f"{s * 100:.0f}"
    if fmt == "lightness":
        return f"{l * 100:.0f}"
    if fmt == "red":
        return str(red)
    if fmt == "green":
        return str(green)
    if fmt == "blue":
        return str(blue)
    if fmt == "alpha":
        return alpha_text
    raise KeyError(fmt)


def render(text: str, data: dict, variant: str) -> tuple[str, list[str]]:
    """Substitute every ``{{ ... }}`` expression; returns (output, warnings)."""
    schemes = data.get("schemes") or {}
    warnings: list[str] = []

    def resolve(expr: str) -> str:
        if expr == "mode":
            return variant
        parts = expr.split(".")
        if len(parts) != 4 or parts[0] != "colors":
            warnings.append(f"unsupported expression: {{{{{expr}}}}}")
            return f"{{{{UNKNOWN:{expr}}}}}"
        _, role, mode, fmt = parts
        if mode == "default":
            mode = variant
        scheme = schemes.get(mode)
        if not isinstance(scheme, dict):
            warnings.append(f"unknown mode {mode!r} in {{{{{expr}}}}}")
            return f"{{{{UNKNOWN:{expr}}}}}"
        value = scheme.get(camel(role))
        if not value:
            warnings.append(f"unknown role {role!r} in {{{{{expr}}}}}")
            return f"{{{{UNKNOWN:{expr}}}}}"
        try:
            return format_color(value, fmt)
        except KeyError:
            warnings.append(f"unknown format {fmt!r} in {{{{{expr}}}}}")
            return f"{{{{UNKNOWN:{expr}}}}}"

    output = EXPR_RE.sub(lambda m: resolve(m.group(1)), text)
    for warning in warnings:
        managed.log().warning("template: %s", warning)
    return output, warnings
