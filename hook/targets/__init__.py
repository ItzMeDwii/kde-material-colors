"""Target registry: one module per application/surface."""

from __future__ import annotations

from . import (
    alacritty,
    bat,
    btop,
    discord,
    eza,
    fastfetch,
    firefox,
    fish,
    ghostty,
    gtk,
    hayase,
    nvim,
    pear_desktop,
    steam_material_theme,
    vim,
)

# Application order: files first, expensive work (bat cache) last.
ORDER = [
    ghostty,
    alacritty,
    fish,
    btop,
    eza,
    vim,
    nvim,
    gtk,
    fastfetch,
    firefox,
    discord,
    pear_desktop,
    hayase,
    steam_material_theme,
    bat,
]
NAMES = {module.NAME: module for module in ORDER}


def by_name(name: str):
    return NAMES.get(name)
