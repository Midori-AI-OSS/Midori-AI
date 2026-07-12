from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QGroupBox,
    QProgressBar,
    QSplitter,
)

from gui.core.song import Song
from gui.core.metadata import write_song_metadata
from gui.core.opencode_client import OpenCodeWorker
from gui.core.config import get_config
from gui.core.prompts import PromptStore, FeedbackEntry
from gui.widgets.components import make_header, StarRating


class CommentEditor(QWidget):
    finished = Signal(Song)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._song: Song | None = None
        self._config = get_config()
        self._prompts = PromptStore(Path("prompts.toml"), Path("prompts.base.toml"))
        self._prompts.load()
        self._worker: OpenCodeWorker | None = None
        self._draft_history: list[str] = []
        self._current_draft = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Comment Editor", self._on_cancel)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        info_group = QGroupBox("Song Information")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(4)
        self._file_label = QLabel()
        self._file_label.setObjectName("dimLabel")
        self._file_label.setWordWrap(True)
        info_layout.addWidget(self._file_label)
        self._comment_label = QLabel()
        self._comment_label.setObjectName("dimLabel")
        self._comment_label.setWordWrap(True)
        info_layout.addWidget(self._comment_label)
        self._tags_label = QLabel()
        self._tags_label.setObjectName("dimLabel")
        self._tags_label.setWordWrap(True)
        info_layout.addWidget(self._tags_label)
        left_layout.addWidget(info_group)

        qna_group = QGroupBox("Q&A Inputs")
        qna_layout = QVBoxLayout(qna_group)
        qna_layout.setSpacing(6)
        fields = [
            ("why_made", "Why I made this song"),
            ("backstory", "Backstory"),
            ("radio_reason", "Why on Midori AI Radio"),
            ("music_theme", "Music theme"),
            ("listener_takeaway", "Listener takeaway"),
        ]
        self._qna_inputs: dict[str, QLineEdit] = {}
        for key, label_text in fields:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(130)
            lbl.setObjectName("dimLabel")
            row.addWidget(lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(f"Enter {label_text.lower()}...")
            row.addWidget(edit)
            self._qna_inputs[key] = edit
            qna_layout.addLayout(row)
        left_layout.addWidget(qna_group)

        gen_row = QHBoxLayout()
        self._generate_btn = QPushButton("Generate Comment")
        self._generate_btn.setObjectName("accentButton")
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.clicked.connect(self._start_generation)
        gen_row.addWidget(self._generate_btn)
        gen_row.addStretch()
        left_layout.addLayout(gen_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(20)
        left_layout.addWidget(self._progress_bar)

        self._reasoning_label = QLabel()
        self._reasoning_label.setObjectName("dimLabel")
        self._reasoning_label.setWordWrap(True)
        self._reasoning_label.setVisible(False)
        left_layout.addWidget(self._reasoning_label)

        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        draft_group = QGroupBox("Generated Draft")
        draft_layout = QVBoxLayout(draft_group)
        self._draft_text = QTextEdit()
        self._draft_text.setReadOnly(True)
        self._draft_text.setMinimumHeight(100)
        self._draft_text.setPlaceholderText(
            "Click Generate Comment to create a draft..."
        )
        draft_layout.addWidget(self._draft_text)
        right_layout.addWidget(draft_group)

        rating_group = QGroupBox("Rate This Output")
        rating_layout = QVBoxLayout(rating_group)
        rating_layout.setSpacing(6)
        star_row = QHBoxLayout()
        star_row.addWidget(QLabel("Rating:"))
        self._star_rating = StarRating()
        star_row.addWidget(self._star_rating)
        star_row.addStretch()
        rating_layout.addLayout(star_row)
        self._rating_note = QLineEdit()
        self._rating_note.setPlaceholderText("Optional note about this output...")
        rating_layout.addWidget(self._rating_note)
        right_layout.addWidget(rating_group)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._accept_btn = QPushButton("Accept & Save")
        self._accept_btn.setObjectName("successButton")
        self._accept_btn.clicked.connect(self._on_accept)
        self._accept_btn.setEnabled(False)
        btn_row.addWidget(self._accept_btn)
        self._refine_btn = QPushButton("Refine")
        self._refine_btn.clicked.connect(self._on_refine)
        self._refine_btn.setEnabled(False)
        btn_row.addWidget(self._refine_btn)
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.clicked.connect(self._on_undo)
        self._undo_btn.setEnabled(False)
        btn_row.addWidget(self._undo_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)
        right_layout.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([440, 460])
        layout.addWidget(splitter)

    def load_song(self, song: Song):
        self._song = song
        self._draft_history = []
        self._current_draft = ""
        self._draft_text.clear()
        self._draft_text.setPlaceholderText(
            "Click Generate Comment to create a draft..."
        )
        self._star_rating.clear()
        self._rating_note.clear()
        self._accept_btn.setEnabled(False)
        self._refine_btn.setEnabled(False)
        self._undo_btn.setEnabled(False)
        self._progress_bar.setVisible(False)
        self._reasoning_label.setVisible(False)

        self._file_label.setText(
            f"{song.relative_path}\nChannel: {song.channel}"
        )
        self._comment_label.setText(f"Current: {song.comment or '(empty)'}")

        parts = []
        if song.vibe_summary:
            parts.append(f"Vibes: {song.vibe_summary}")
        if song.music_theme:
            parts.append(f"Theme: {song.music_theme}")
        if song.why_made:
            parts.append(f"Why: {song.why_made}")
        if song.backstory:
            parts.append(f"Story: {song.backstory}")
        if song.radio_reason:
            parts.append(f"Radio: {song.radio_reason}")
        if song.listener_takeaway:
            parts.append(f"Takeaway: {song.listener_takeaway}")
        self._tags_label.setText("  |  ".join(parts))

        self._qna_inputs["why_made"].setText(song.why_made)
        self._qna_inputs["backstory"].setText(song.backstory)
        self._qna_inputs["radio_reason"].setText(song.radio_reason)
        self._qna_inputs["music_theme"].setText(song.music_theme)
        self._qna_inputs["listener_takeaway"].setText(song.listener_takeaway)

    def _start_generation(self):
        if self._song is None:
            return
        self._cancel_worker()
        self._generate_btn.setEnabled(False)
        self._accept_btn.setEnabled(False)
        self._refine_btn.setEnabled(False)
        self._undo_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._reasoning_label.setVisible(True)
        self._reasoning_label.clear()
        self._draft_text.setPlaceholderText("Generating...")

        title = self._song.title
        channel = self._song.channel

        def _get(field: str) -> str:
            return self._qna_inputs[field].text().strip() or getattr(
                self._song, field, ""
            )

        qna_parts = [
            f"Why I made this song: {_get('why_made')}",
            f"Backstory: {_get('backstory')}",
            f"Why on Midori AI Radio: {_get('radio_reason')}",
            f"Music theme: {_get('music_theme')}",
            f"Listener takeaway: {_get('listener_takeaway')}",
        ]
        statement = "\n".join(qna_parts)
        if not statement.strip():
            statement = f"Song: {title} in channel: {channel}"

        research = self._prompts.get_prompt("library_research")
        research = research.replace("$song_file", str(self._song.path))

        template = self._prompts.get_prompt("song_statement")
        prompt = template.format(
            library_research=research,
            title=title,
            statement=statement,
        )

        self._worker = OpenCodeWorker(
            prompt=prompt,
            working_dir=self._song.path.parent,
            model=self._config.opencode_model,
            variant=self._config.opencode_variant,
            continue_session=bool(self._draft_history),
        )
        self._worker.progress_update.connect(self._on_progress)
        self._worker.reasoning_update.connect(self._on_reasoning)
        self._worker.finished.connect(self._on_draft_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _cancel_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)

    def _on_progress(self, current: int, total: int, status: str):
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def _on_reasoning(self, text: str):
        self._reasoning_label.setText(text[:200])

    def _on_draft_ready(self, draft: str):
        self._progress_bar.setVisible(False)
        self._reasoning_label.setVisible(False)
        self._generate_btn.setEnabled(True)

        draft = draft.strip()
        if draft and self._current_draft:
            self._draft_history.append(self._current_draft)
        self._current_draft = draft
        self._draft_text.setPlainText(draft)

        self._accept_btn.setEnabled(bool(draft))
        self._refine_btn.setEnabled(bool(draft))
        self._undo_btn.setEnabled(len(self._draft_history) > 0)

    def _on_error(self, msg: str):
        self._progress_bar.setVisible(False)
        self._reasoning_label.setVisible(False)
        self._generate_btn.setEnabled(True)
        self._draft_text.setPlaceholderText(f"Error: {msg[:300]}")

    def _on_refine(self):
        if self._song is None or not self._current_draft:
            return
        self._cancel_worker()
        self._generate_btn.setEnabled(False)
        self._accept_btn.setEnabled(False)
        self._refine_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._reasoning_label.setVisible(True)
        self._reasoning_label.clear()

        def _get(field: str) -> str:
            return self._qna_inputs[field].text().strip() or getattr(
                self._song, field, ""
            )

        source = "\n".join(
            [
                f"Why I made this song: {_get('why_made')}",
                f"Backstory: {_get('backstory')}",
                f"Radio Reason: {_get('radio_reason')}",
                f"Music theme: {_get('music_theme')}",
                f"Listener takeaway: {_get('listener_takeaway')}",
            ]
        )

        research = self._prompts.get_prompt("library_research")
        research = research.replace("$song_file", str(self._song.path))

        template = self._prompts.get_prompt("refinement")
        prompt = template.format(
            library_research=research,
            title=self._song.title,
            source_statement=source,
            current_draft=self._current_draft,
            feedback="Preserve details but improve readability",
        )

        self._worker = OpenCodeWorker(
            prompt=prompt,
            working_dir=self._song.path.parent,
            model=self._config.opencode_model,
            variant=self._config.opencode_variant,
            continue_session=True,
        )
        self._worker.progress_update.connect(self._on_progress)
        self._worker.reasoning_update.connect(self._on_reasoning)
        self._worker.finished.connect(self._on_draft_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_undo(self):
        if self._draft_history:
            self._current_draft = self._draft_history.pop()
            self._draft_text.setPlainText(self._current_draft)
            self._undo_btn.setEnabled(len(self._draft_history) > 0)

    def _on_accept(self):
        if self._song is None or not self._current_draft:
            return
        self._song.comment = self._current_draft
        self._song.why_made = (
            self._qna_inputs["why_made"].text().strip() or self._song.why_made
        )
        self._song.backstory = (
            self._qna_inputs["backstory"].text().strip() or self._song.backstory
        )
        self._song.radio_reason = (
            self._qna_inputs["radio_reason"].text().strip() or self._song.radio_reason
        )
        self._song.music_theme = (
            self._qna_inputs["music_theme"].text().strip() or self._song.music_theme
        )
        self._song.listener_takeaway = (
            self._qna_inputs["listener_takeaway"].text().strip()
            or self._song.listener_takeaway
        )

        rating = self._star_rating.rating
        if rating > 0:
            self._save_feedback(rating)

        success, err = write_song_metadata(self._song)
        if success:
            parent_window = self.window()
            if hasattr(parent_window, "show_toast"):
                parent_window.show_toast("Metadata saved", "success")
            self.finished.emit(self._song)
        else:
            parent_window = self.window()
            if hasattr(parent_window, "show_toast"):
                parent_window.show_toast(f"Failed to save: {err[:200]}", "error")

    def _save_feedback(self, rating: int):
        from gui.core.prompts import FeedbackQueue

        entry = FeedbackEntry(
            rating=rating,
            output=self._current_draft,
            prompt_template="song_statement",
            song_title=self._song.title if self._song else "",
            song_context=(
                f"channel: {self._song.channel if self._song else ''}, "
                f"theme: {self._song.music_theme if self._song else ''}"
            ),
            note=self._rating_note.text().strip(),
        )
        queue = FeedbackQueue(self._config.feedback_queue_path)
        queue.append(entry)

    def _on_cancel(self):
        self._cancel_worker()
        self.cancelled.emit()
