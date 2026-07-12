from __future__ import annotations

import subprocess
from pathlib import Path

from gui.core.song import Song

MIDORI_TAG_WHY_MADE = "midori_ai_why_made"
MIDORI_TAG_BACKSTORY = "midori_ai_backstory"
MIDORI_TAG_RADIO_REASON = "midori_ai_radio_reason"
MIDORI_TAG_MUSIC_THEME = "midori_ai_music_theme"
MIDORI_TAG_LISTENER_TAKEAWAY = "midori_ai_listener_takeaway"
MIDORI_TAG_VIBE_ANALYSIS = "midori_ai_vibe_analysis"
MIDORI_TAG_VIBE_SUMMARY = "midori_ai_vibe_summary"
MIDORI_TAG_VIBE_CACHED_AT_EPOCH = "midori_ai_vibe_cached_at_epoch"
MIDORI_TAG_VIBE_CACHE_SCHEMA = "midori_ai_vibe_cache_schema"


def _get_tag(file_path: Path, key: str) -> str:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format_tags",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        tag_lines = [line for line in lines if line.startswith("TAG:")]
        for line in tag_lines:
            pair = line.removeprefix("TAG:")
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            if k.lower() == key.lower():
                return v.strip()
        return ""
    except Exception:
        return ""


def get_song_title(file_path: Path) -> str:
    title = _get_tag(file_path, "title")
    if title:
        return title
    return file_path.stem


def get_song_comment(file_path: Path) -> str:
    return _get_tag(file_path, "comment")


def read_song(file_path: Path) -> Song:
    return Song(
        path=file_path,
        title=get_song_title(file_path),
        comment=get_song_comment(file_path),
        why_made=_get_tag(file_path, MIDORI_TAG_WHY_MADE),
        backstory=_get_tag(file_path, MIDORI_TAG_BACKSTORY),
        radio_reason=_get_tag(file_path, MIDORI_TAG_RADIO_REASON),
        music_theme=_get_tag(file_path, MIDORI_TAG_MUSIC_THEME),
        listener_takeaway=_get_tag(file_path, MIDORI_TAG_LISTENER_TAKEAWAY),
        vibe_analysis=_get_tag(file_path, MIDORI_TAG_VIBE_ANALYSIS),
        vibe_summary=_get_tag(file_path, MIDORI_TAG_VIBE_SUMMARY),
        vibe_cached_at_epoch=_get_tag(file_path, MIDORI_TAG_VIBE_CACHED_AT_EPOCH),
        vibe_cache_schema=_get_tag(file_path, MIDORI_TAG_VIBE_CACHE_SCHEMA),
    )


def scan_library(music_root: Path, exclude_blocked: bool = False) -> list[Path]:
    if not music_root.exists():
        return []
    paths: list[Path] = []
    for mp3 in sorted(music_root.rglob("*.mp3")):
        if exclude_blocked and (mp3.parent / ".blocked").exists():
            continue
        paths.append(mp3)
    for mp3 in sorted(music_root.rglob("*.MP3")):
        if exclude_blocked and (mp3.parent / ".blocked").exists():
            continue
        paths.append(mp3)
    return list(dict.fromkeys(paths))


def scan_downloads(downloads_dir: Path) -> list[Path]:
    if not downloads_dir.exists():
        return []
    paths: list[Path] = []
    for mp3 in sorted(
        downloads_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        paths.append(mp3)
    for mp3 in sorted(
        downloads_dir.glob("*.MP3"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        if mp3 not in paths:
            paths.append(mp3)
    return paths


def is_outdated_comment(comment: str) -> bool:
    lower = comment.lower()
    triggers = ["made with suno", "produced with suno", "from midori ai radio"]
    return any(t in lower for t in triggers)


def recommend_channel(filename: str, channels: list[str]) -> str | None:
    rules = [
        ("lofi", "lofi"),
        ("chill", "chill"),
        ("indie", "indie"),
        ("vibe", "vibes"),
        ("vibes", "vibes"),
        ("waiting", "vibes"),
        ("lunar", "lunar-mix"),
        ("moon", "lunar-mix"),
        ("space", "lunar-mix"),
        ("8bit", "bits-tech"),
        ("gba", "bits-tech"),
        ("tech", "bits-tech"),
        ("bit", "bits-tech"),
    ]
    lower_name = filename.lower()
    channel_lower = {c.lower(): c for c in channels}
    for key, target in rules:
        if key in lower_name and target in channel_lower:
            return channel_lower[target]
    for channel in channels:
        if channel.lower() in lower_name:
            return channel
        tokens = "".join(c if c.isalnum() else " " for c in channel.lower()).split()
        for token in tokens:
            if len(token) >= 3 and token in lower_name:
                return channel
    return None


def get_channel_dirs(music_root: Path) -> list[str]:
    if not music_root.exists():
        return []
    return sorted(
        d.name
        for d in music_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def is_channel_blocked(music_root: Path, channel: str) -> bool:
    return (music_root / channel / ".blocked").exists()


def block_channel(music_root: Path, channel: str) -> None:
    (music_root / channel / ".blocked").touch()


def unblock_channel(music_root: Path, channel: str) -> None:
    blocked_file = music_root / channel / ".blocked"
    if blocked_file.exists():
        blocked_file.unlink()


def get_file_mtime(file_path: Path) -> int:
    try:
        return int(file_path.stat().st_mtime)
    except Exception:
        return 0


def write_song_metadata(song: Song) -> tuple[bool, str]:
    song_dir = song.path.parent
    song_dir.mkdir(parents=True, exist_ok=True)
    temp_path = song_dir / f".metadata-update-{song.path.stem}.mp3"
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(song.path),
                "-map",
                "0",
                "-c",
                "copy",
                "-metadata",
                f"comment={song.comment}",
                "-metadata",
                f"{MIDORI_TAG_WHY_MADE}={song.why_made}",
                "-metadata",
                f"{MIDORI_TAG_BACKSTORY}={song.backstory}",
                "-metadata",
                f"{MIDORI_TAG_RADIO_REASON}={song.radio_reason}",
                "-metadata",
                f"{MIDORI_TAG_MUSIC_THEME}={song.music_theme}",
                "-metadata",
                f"{MIDORI_TAG_LISTENER_TAKEAWAY}={song.listener_takeaway}",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            temp_path.unlink(missing_ok=True)
            return False, result.stderr
        temp_path.rename(song.path)
        return True, ""
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        return False, str(e)


def write_vibe_cache(song: Song) -> tuple[bool, str]:
    song_dir = song.path.parent
    song_dir.mkdir(parents=True, exist_ok=True)
    temp_path = song_dir / f".vibe-cache-{song.path.stem}.mp3"
    original_mtime = get_file_mtime(song.path)
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(song.path),
                "-map",
                "0",
                "-c",
                "copy",
                "-metadata",
                f"{MIDORI_TAG_VIBE_ANALYSIS}={song.vibe_analysis}",
                "-metadata",
                f"{MIDORI_TAG_VIBE_SUMMARY}={song.vibe_summary}",
                "-metadata",
                f"{MIDORI_TAG_VIBE_CACHED_AT_EPOCH}={song.vibe_cached_at_epoch}",
                "-metadata",
                f"{MIDORI_TAG_VIBE_CACHE_SCHEMA}={song.vibe_cache_schema}",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            temp_path.unlink(missing_ok=True)
            return False, result.stderr
        temp_path.rename(song.path)
        if original_mtime > 0:
            import os

            os.utime(song.path, (original_mtime, original_mtime))
        return True, ""
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        return False, str(e)


def trash_file(file_path: Path) -> bool:
    for tool in ["kioclient", "kioclient5"]:
        try:
            result = subprocess.run(
                [tool, "move", str(file_path), "trash:/"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["gio", "trash", str(file_path)],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    return False
