"""Shared context object passed to every target."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import managed
from mycolors import Palette


@dataclass
class Context:
    palette: Palette
    raw: dict
    dry_run: bool = False
    changed: dict[str, bool] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)

    def write(self, path: Path, content: str) -> bool:
        """Write ``content`` unless identical; track change + hash for state."""
        path = Path(path)
        if self.dry_run:
            try:
                same = path.read_text(encoding="utf-8") == content
            except OSError:
                same = False
            if not same:
                managed.log().info("dry-run would write %s", path)
            self.changed[str(path)] = not same
            return not same
        changed = managed.write_if_changed(path, content)
        if changed:
            managed.log().info("wrote %s", path)
        self.changed[str(path)] = changed
        self.files[str(path)] = managed.file_hash(path)
        return changed

    @property
    def variant(self) -> str:
        return self.palette.variant

    def track(self, path: Path) -> None:
        """Record the current hash of a file edited through managed helpers."""
        if self.dry_run:
            return
        path = Path(path)
        self.files[str(path)] = managed.file_hash(path)

    def any_changed(self) -> bool:
        return any(self.changed.values())
