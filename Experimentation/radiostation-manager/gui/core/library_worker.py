from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from gui.core.metadata import scan_library, read_song, scan_downloads
from gui.core.song import Song


class LibraryScanWorker(QThread):
    progress = Signal(int, int, str)
    songs_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, music_root: Path, exclude_blocked: bool = True, parent=None):
        super().__init__(parent)
        self._music_root = music_root
        self._exclude_blocked = exclude_blocked
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.requestInterruption()

    def run(self):
        try:
            self.progress.emit(0, 100, "Scanning library...")
            paths = scan_library(
                self._music_root, exclude_blocked=self._exclude_blocked
            )
            total = len(paths)
            if total == 0:
                self.songs_ready.emit([])
                return

            songs: list[dict] = []
            for i, p in enumerate(paths):
                if self._cancelled or self.isInterruptionRequested():
                    return
                if i % 5 == 0:
                    self.progress.emit(i, total, f"Reading {p.name}...")
                try:
                    s = read_song(p)
                    songs.append(
                        {
                            "path": p,
                            "channel": s.channel,
                            "title": s.title,
                            "comment": s.comment,
                            "vibe_summary": s.vibe_summary,
                            "filename": p.name,
                        }
                    )
                except Exception:
                    songs.append(
                        {
                            "path": p,
                            "channel": "",
                            "title": p.stem,
                            "comment": "",
                            "vibe_summary": "",
                            "filename": p.name,
                        }
                    )
            self.progress.emit(total, total, "Done.")
            self.songs_ready.emit(songs)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DownloadScanWorker(QThread):
    progress = Signal(int, int, str)
    ready = Signal(list, list)
    error_occurred = Signal(str)

    def __init__(self, downloads_dir: Path, music_root: Path, parent=None):
        super().__init__(parent)
        self._downloads_dir = downloads_dir
        self._music_root = music_root
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.requestInterruption()

    def run(self):
        try:
            self.progress.emit(0, 100, "Scanning Downloads...")
            all_downloads = (
                scan_downloads(self._downloads_dir)
                if self._downloads_dir.exists()
                else []
            )
            library = {p.name.lower() for p in scan_library(self._music_root)}
            non_imported = [d for d in all_downloads if d.name.lower() not in library]
            self.progress.emit(100, 100, "Done.")
            self.ready.emit(all_downloads, non_imported)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SongReadWorker(QThread):
    song_ready = Signal(Path, dict)
    error_occurred = Signal(str)

    def __init__(self, song_path: Path, parent=None):
        super().__init__(parent)
        self._song_path = song_path

    def run(self):
        try:
            s = read_song(self._song_path)
            data = {
                "path": self._song_path,
                "channel": s.channel,
                "title": s.title,
                "comment": s.comment,
                "vibe_summary": s.vibe_summary,
                "filename": s.filename,
            }
            self.song_ready.emit(self._song_path, data)
        except Exception as e:
            self.error_occurred.emit(str(e))
