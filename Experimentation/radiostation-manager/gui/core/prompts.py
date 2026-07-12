from __future__ import annotations

import json
import tomllib
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class FeedbackEntry:
    rating: int
    output: str
    prompt_template: str
    song_title: str
    song_context: str
    note: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "rating": self.rating,
            "output": self.output,
            "prompt_template": self.prompt_template,
            "song_title": self.song_title,
            "song_context": self.song_context,
            "note": self.note,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FeedbackEntry:
        return cls(
            rating=int(d.get("rating", 3)),
            output=str(d.get("output", "")),
            prompt_template=str(d.get("prompt_template", "")),
            song_title=str(d.get("song_title", "")),
            song_context=str(d.get("song_context", "")),
            note=str(d.get("note", "")),
            timestamp=str(d.get("timestamp", "")),
        )


class PromptStore:
    def __init__(self, active_path: Path, base_path: Path):
        self.active_path = active_path
        self.base_path = base_path
        self._data: dict[str, dict[str, str]] = {}
        self._ensure_active_exists()

    def _ensure_active_exists(self):
        if not self.active_path.exists():
            if self.base_path.exists():
                shutil.copy(self.base_path, self.active_path)
            else:
                self.active_path.write_text("")

    def load(self) -> dict[str, dict[str, str]]:
        if self.active_path.exists():
            self._data = tomllib.loads(self.active_path.read_text())
        return self._data

    def save(self):
        self.active_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for name, info in self._data.items():
            desc = info.get("description", "")
            prompt = info.get("prompt", "")
            lines.append(f"[{name}]")
            lines.append(f'description = "{desc}"')
            lines.append(f'prompt = """')
            lines.append(prompt)
            lines.append('"""')
            lines.append("")
        self.active_path.write_text("\n".join(lines))

    def get_prompt(self, name: str) -> str:
        if name in self._data:
            return self._data[name].get("prompt", "")
        return ""

    def set_prompt(self, name: str, prompt: str):
        if name in self._data:
            self._data[name]["prompt"] = prompt

    def get_description(self, name: str) -> str:
        if name in self._data:
            return self._data[name].get("description", "")
        return ""

    def reset_to_base(self):
        if self.base_path.exists():
            shutil.copy(self.base_path, self.active_path)
            self._data = tomllib.loads(self.active_path.read_text())

    @property
    def template_names(self) -> list[str]:
        return list(self._data.keys())


class FeedbackQueue:
    def __init__(self, queue_path: Path):
        self.queue_path = queue_path

    def load_all(self) -> list[FeedbackEntry]:
        if not self.queue_path.exists():
            return []
        try:
            data = json.loads(self.queue_path.read_text())
            if isinstance(data, list):
                return [FeedbackEntry.from_dict(item) for item in data]
        except (json.JSONDecodeError, Exception):
            pass
        return []

    def save_all(self, entries: list[FeedbackEntry]):
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_path.write_text(
            json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False)
        )

    def append(self, entry: FeedbackEntry):
        entries = self.load_all()
        entries.append(entry)
        self.save_all(entries)

    def remove(self, index: int):
        entries = self.load_all()
        if 0 <= index < len(entries):
            entries.pop(index)
            self.save_all(entries)

    def clear(self):
        self.queue_path.write_text("[]")

    @property
    def count(self) -> int:
        return len(self.load_all())
