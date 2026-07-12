from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, QThreadPool
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QMessageBox,
)

from gui.core.config import get_config
from gui.core.metadata import (
    scan_library,
    read_song,
    write_vibe_cache,
)
from gui.core.essentia_client import EssentiaWorker
from gui.widgets.components import make_header


class CacheVibesFlow(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._pool = QThreadPool.globalInstance()
        self._total = 0
        self._completed = 0
        self._success = 0
        self._failed = 0
        self._running = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Cache All Vibes", self.back.emit)
        layout.addLayout(header)

        options = QGroupBox("Options")
        opt_layout = QVBoxLayout(options)
        self._include_blocked = QCheckBox("Include blocked channels")
        opt_layout.addWidget(self._include_blocked)
        worker_row = QHBoxLayout()
        worker_row.addWidget(QLabel("Parallel workers:"))
        self._worker_spin = QSpinBox()
        self._worker_spin.setRange(1, 16)
        self._worker_spin.setValue(
            max(1, QThreadPool.globalInstance().maxThreadCount() // 2)
        )
        worker_row.addWidget(self._worker_spin)
        worker_row.addStretch()
        opt_layout.addLayout(worker_row)
        layout.addWidget(options)

        self._status_label = QLabel()
        self._status_label.setObjectName("dimLabel")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._detail_label = QLabel()
        self._detail_label.setObjectName("dimLabel")
        self._detail_label.setWordWrap(True)
        layout.addWidget(self._detail_label)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Caching")
        self._start_btn.setObjectName("accentButton")
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dangerButton")
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.setEnabled(False)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        layout.addStretch()

    def _start(self):
        self._running = True
        self._completed = 0
        self._success = 0
        self._failed = 0

        include = self._include_blocked.isChecked()
        songs = scan_library(self._config.music_root, exclude_blocked=not include)
        self._total = len(songs)
        if self._total == 0:
            QMessageBox.information(self, "No Songs", "No MP3 files found.")
            return

        self._pool.setMaxThreadCount(self._worker_spin.value())
        self._progress.setMaximum(self._total)
        self._progress.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._status_label.setText(f"Analyzing {self._total} songs...")

        for song_path in songs:
            if not self._running:
                break
            worker = EssentiaWorker(
                song_path=song_path,
                uv_workdir=self._config.essentia_uv_workdir,
                uv_package_spec=self._config.essentia_uv_package_spec,
            )
            worker.signals.finished.connect(self._on_song_done)
            worker.signals.error_occurred.connect(self._on_song_failed)
            self._pool.start(worker)

    def _on_song_done(self, song_key: str, result: str):
        if not self._running:
            return
        self._completed += 1
        self._success += 1
        self._progress.setValue(self._completed)

        parts = result.split("|", 1)
        analysis = parts[0] if len(parts) > 0 else ""
        summary = parts[1] if len(parts) > 1 else ""

        song_path = Path(song_key)
        song = read_song(song_path)
        import time

        song.vibe_analysis = analysis
        song.vibe_summary = summary
        song.vibe_cached_at_epoch = str(int(time.time()))
        song.vibe_cache_schema = "v1"
        write_vibe_cache(song)

        self._detail_label.setText(f"Cached: {song_path.name}")
        self._status_label.setText(
            f"Progress: {self._completed}/{self._total} ({self._success} ok, {self._failed} fail)"
        )
        if self._completed >= self._total:
            self._finish()

    def _on_song_failed(self, song_key: str, error: str):
        if not self._running:
            return
        self._completed += 1
        self._failed += 1
        self._progress.setValue(self._completed)
        self._detail_label.setText(f"Failed: {Path(song_key).name} — {error[:100]}")
        self._status_label.setText(
            f"Progress: {self._completed}/{self._total} ({self._success} ok, {self._failed} fail)"
        )
        if self._completed >= self._total:
            self._finish()

    def _finish(self):
        self._running = False
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._summary_label.setText(
            f"Done! {self._success} cached, {self._failed} failed out of {self._total} total."
        )
        self._pool.setMaxThreadCount(QThreadPool.globalInstance().maxThreadCount())
        parent_window = self.window()
        if hasattr(parent_window, "show_toast"):
            parent_window.show_toast(
                f"\u2705 {self._success} songs cached, {self._failed} failed", "success"
            )

    def _cancel(self):
        self._running = False
        self._pool.clear()
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._detail_label.setText("Cancelled.")
