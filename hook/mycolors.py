"""Color math and Material You palette extraction for the KMYC hook.

Source of truth: the JSON written by kde-material-you-colors
(``schemes.light`` / ``schemes.dark``, full M3 role set).

The ANSI/terminal slot mapping follows Noctalia's
``synthesizeTerminalPaletteTokens()`` (src/theme/fixed_palette.cpp): M3 roles
mapped onto the 16 ANSI slots with a WCAG 4.5:1 contrast fix against the
terminal background applied to the six chromatic slots only.
"""

from __future__ import annotations

import math
import re

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")

# --- sRGB <-> OKLab <-> OKLCH ------------------------------------------------


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def parse_hex(value: str) -> tuple[int, int, int]:
    m = HEX_RE.match(value.strip())
    if not m:
        raise ValueError(f"not a #rrggbb color: {value!r}")
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _rgb_to_oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c / 255.0) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v >= 0 else -((-v) ** (1 / 3)) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_linear(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def _in_gamut(rgb: tuple[float, float, float]) -> bool:
    return all(-1e-4 <= c <= 1.0 + 1e-4 for c in rgb)


def rgb_to_oklch(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    L, a, b = _rgb_to_oklab(rgb)
    C = math.hypot(a, b)
    H = math.degrees(math.atan2(b, a)) % 360.0
    return L, C, H


def oklch_to_rgb(lch: tuple[float, float, float]) -> tuple[int, int, int]:
    """OKLCH -> sRGB with a chroma-only gamut clamp (hue preserved)."""
    L, C, H = lch
    rad = math.radians(H)
    rgb = _oklab_to_linear((L, C * math.cos(rad), C * math.sin(rad)))
    if not _in_gamut(rgb):
        lo, hi = 0.0, C
        for _ in range(20):
            mid = (lo + hi) / 2
            rgb = _oklab_to_linear((L, mid * math.cos(rad), mid * math.sin(rad)))
            if _in_gamut(rgb):
                lo = mid
            else:
                hi = mid
        rgb = _oklab_to_linear((L, lo * math.cos(rad), lo * math.sin(rad)))
    return tuple(
        max(0, min(255, int(round(_linear_to_srgb(max(0.0, min(1.0, c))) * 255)))) for c in rgb
    )


# --- WCAG contrast -----------------------------------------------------------


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb_to_linear(c / 255.0) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def is_dark(rgb: tuple[int, int, int]) -> bool:
    """Noctalia: relative luminance < 0.179 counts as dark."""
    return relative_luminance(rgb) < 0.179


def ensure_contrast(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    """Raise/lower OKLCH lightness of ``fg`` until WCAG contrast vs ``bg`` >= min_ratio.

    Mirrors Noctalia's ``ensureContrast()``: hue is kept, chroma is only
    reduced by the gamut clamp.
    """
    fg_rgb, bg_rgb = parse_hex(fg), parse_hex(bg)
    if contrast_ratio(fg_rgb, bg_rgb) >= min_ratio:
        return to_hex(fg_rgb)

    L, C, H = rgb_to_oklch(fg_rgb)
    lighten = is_dark(bg_rgb)
    end = 1.0 if lighten else 0.0

    end_rgb = oklch_to_rgb((end, C, H))
    if contrast_ratio(end_rgb, bg_rgb) < min_ratio:
        # Even the endpoint misses the ratio: pick whichever endpoint is better.
        other = 0.0 if lighten else 1.0
        other_rgb = oklch_to_rgb((other, C, H))
        best = end_rgb if contrast_ratio(end_rgb, bg_rgb) >= contrast_ratio(other_rgb, bg_rgb) else other_rgb
        return to_hex(best)

    lo, hi = L, end  # lo unknown but monotonic toward end
    best = end_rgb
    for _ in range(20):
        mid = (lo + hi) / 2
        rgb = oklch_to_rgb((mid, C, H))
        if contrast_ratio(rgb, bg_rgb) >= min_ratio:
            best = rgb
            hi = mid
        else:
            lo = mid
    return to_hex(best)


def nearest_named(hex_color: str, names: dict[str, str]) -> str:
    """Return the key of ``names`` whose value is closest to ``hex_color`` (Oklab)."""
    target = _rgb_to_oklab(parse_hex(hex_color))
    best, best_d = None, float("inf")
    for name, value in names.items():
        lab = _rgb_to_oklab(parse_hex(value))
        d = sum((a - b) ** 2 for a, b in zip(target, lab))
        if d < best_d:
            best, best_d = name, d
    return best


def nearest_hue(hex_color: str, names: dict[str, str]) -> str:
    """Nearest by OKLCH hue (chroma/lightness ignored: named accents are mid-tone)."""
    _, target_c, target_h = rgb_to_oklch(parse_hex(hex_color))
    best, best_d = None, float("inf")
    for name, value in names.items():
        _, chroma, hue = rgb_to_oklch(parse_hex(value))
        dh = abs(hue - target_h) % 360.0
        dh = min(dh, 360.0 - dh)
        # Low-chroma targets (near-grey M3 primaries) still need a sane pick.
        weight = 0.0 if target_c < 0.02 else 1.0
        d = (dh * weight) + (abs(chroma - target_c) * 10)
        if d < best_d:
            best, best_d = name, d
    return best


# --- Palette -----------------------------------------------------------------

FALLBACK_ROLES = {
    # Extra safety net if a role is missing from the JSON.
    "surface": "background",
    "onBackground": "onSurface",
    "primaryFixedDim": "primary",
    "secondaryFixedDim": "secondary",
    "primaryFixed": "primary",
    "secondaryFixed": "secondary",
    "surfaceContainerLowest": "surface",
    "surfaceContainerLow": "surface",
    "surfaceContainer": "surface",
    "surfaceContainerHigh": "surfaceVariant",
    "surfaceContainerHighest": "surfaceVariant",
}


class Palette:
    """M3 palette for one variant (dark or light) plus derived ANSI slots."""

    def __init__(self, scheme: dict[str, str], variant: str):
        self.variant = variant  # "dark" | "light"
        self.roles: dict[str, str] = {k: v for k, v in scheme.items() if isinstance(v, str)}

        self.bg = self.role("background")
        self.fg = self.role("onSurface")
        self.cursor = self.fg
        self.cursor_text = self.bg
        self.selection_bg = self.role("surfaceVariant")
        self.selection_fg = self.role("onSurfaceVariant")

        def fix(color: str) -> str:
            return ensure_contrast(color, self.bg, 4.5)

        # Noctalia mapping; brights deliberately reuse the normal hues.
        normal = [
            self.role("surfaceVariant"),  # black
            fix(self.role("error")),  # red
            fix(self.role("primary")),  # green
            fix(self.role("secondary")),  # yellow
            fix(self.role("tertiary")),  # blue
            fix(self.role("primaryFixedDim")),  # magenta
            fix(self.role("secondaryFixedDim")),  # cyan
            self.fg,  # white
        ]
        bright = [
            self.role("outline"),  # bright black
            *normal[1:7],
            self.fg,  # bright white
        ]
        self.ansi: list[str] = normal + bright

    def role(self, name: str) -> str:
        value = self.roles.get(name)
        if value:
            return value
        fallback = FALLBACK_ROLES.get(name)
        if fallback and fallback in self.roles:
            return self.roles[fallback]
        raise KeyError(f"M3 role {name!r} missing from the KMYC JSON")

    @property
    def is_dark(self) -> bool:
        return self.variant == "dark"

    def ansi_named(self, name: str) -> str:
        return self.ansi[self.ANSI_NAMES.index(name)]

    ANSI_NAMES = (
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "br_black",
        "br_red",
        "br_green",
        "br_yellow",
        "br_blue",
        "br_magenta",
        "br_cyan",
        "br_white",
    )


def load_palette(data: dict) -> Palette:
    variant = "light" if data.get("light") else "dark"
    schemes = data.get("schemes") or {}
    scheme = schemes.get(variant)
    if not isinstance(scheme, dict) or not scheme:
        raise ValueError(f"no schemes.{variant} in KMYC JSON")
    return Palette(scheme, variant)
