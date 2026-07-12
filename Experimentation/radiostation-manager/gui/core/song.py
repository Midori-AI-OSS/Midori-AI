from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Song:
    path: Path
    title: str = ""
    comment: str = ""
    why_made: str = ""
    backstory: str = ""
    radio_reason: str = ""
    music_theme: str = ""
    listener_takeaway: str = ""
    vibe_analysis: str = ""
    vibe_summary: str = ""
    vibe_cached_at_epoch: str = ""
    vibe_cache_schema: str = ""

    @property
    def display_name(self) -> str:
        return str(self.path)

    @property
    def relative_path(self) -> str:
        music_root = self._guess_music_root()
        try:
            return str(self.path.relative_to(music_root))
        except ValueError:
            return str(self.path)

    @property
    def channel(self) -> str:
        try:
            music_root = self._guess_music_root()
            rel = self.path.relative_to(music_root)
            parts = rel.parts
            return parts[0] if len(parts) > 1 else ""
        except (ValueError, IndexError):
            return ""

    @property
    def filename(self) -> str:
        return self.path.name

    def _guess_music_root(self) -> Path:
        parent = self.path.parent
        while parent != parent.parent:
            if (parent / ".luna-studio-root").exists():
                return parent
            parent = parent.parent
        return (
            self.path.parent.parent
            if self.path.parent != self.path
            else self.path.parent
        )
