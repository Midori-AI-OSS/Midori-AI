from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QGroupBox,
    QTabWidget,
    QComboBox,
    QProgressBar,
    QMessageBox,
)

from gui.core.config import get_config
from gui.core.prompts import PromptStore, FeedbackQueue, FeedbackEntry
from gui.core.opencode_client import OpenCodeWorker


class PromptManager(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._prompts = PromptStore(Path("prompts.toml"), Path("prompts.base.toml"))
        self._prompts.load()
        self._queue = FeedbackQueue(self._config.feedback_queue_path)
        self._worker: OpenCodeWorker | None = None
        self._processing = False
        self._setup_ui()
        self._refresh_all()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("Manage Prompts")
        title.setObjectName("sectionLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("Back to Menu")
        back_btn.clicked.connect(self.back.emit)
        header.addWidget(back_btn)
        layout.addLayout(header)

        tabs = QTabWidget()

        templates_tab = QWidget()
        templates_layout = QVBoxLayout(templates_tab)

        template_list_layout = QHBoxLayout()
        self._template_list = QListWidget()
        self._template_list.setMaximumWidth(200)
        self._template_list.itemClicked.connect(self._on_template_select)
        template_list_layout.addWidget(self._template_list)

        edit_layout = QVBoxLayout()
        desc_label = QLabel("Template Content:")
        edit_layout.addWidget(desc_label)
        self._template_edit = QTextEdit()
        self._template_edit.setPlaceholderText("Select a template to edit...")
        edit_layout.addWidget(self._template_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("successButton")
        save_btn.clicked.connect(self._save_template)
        btn_row.addWidget(save_btn)
        reset_btn = QPushButton("Reset All to Base")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._reset_to_base)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        edit_layout.addLayout(btn_row)

        template_list_layout.addLayout(edit_layout)
        templates_layout.addLayout(template_list_layout)
        tabs.addTab(templates_tab, "Templates")

        queue_tab = QWidget()
        queue_layout = QVBoxLayout(queue_tab)

        queue_header = QHBoxLayout()
        queue_header.addWidget(QLabel("Feedback Queue"))
        queue_header.addStretch()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_queue)
        queue_header.addWidget(clear_btn)
        queue_layout.addLayout(queue_header)

        self._queue_list = QListWidget()
        queue_layout.addWidget(self._queue_list)

        remove_row = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        remove_row.addWidget(remove_btn)
        remove_row.addStretch()
        queue_layout.addLayout(remove_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Refinement Model:"))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.addItems(
            [
                "deepseek/deepseek-v4-flash",
                "lm-studio/qwen/qwen3.6-27b",
                "lm-studio/qwen/qwen3.5-32b",
            ]
        )
        model_row.addWidget(self._model_combo)
        model_row.addWidget(QLabel("Variant:"))
        self._variant_combo = QComboBox()
        self._variant_combo.addItems(["max", "xhigh", "high", "medium"])
        self._variant_combo.setCurrentText(self._config.prompts_for_refinement_variant)
        model_row.addWidget(self._variant_combo)
        model_row.addStretch()
        queue_layout.addLayout(model_row)

        self._proc_progress = QProgressBar()
        self._proc_progress.setVisible(False)
        queue_layout.addWidget(self._proc_progress)

        self._proc_status = QLabel()
        self._proc_status.setObjectName("dimLabel")
        self._proc_status.setWordWrap(True)
        queue_layout.addWidget(self._proc_status)

        process_btn = QPushButton("Process Feedback Queue")
        process_btn.setObjectName("accentButton")
        process_btn.clicked.connect(self._process_queue)
        queue_layout.addWidget(process_btn)

        tabs.addTab(queue_tab, "Feedback Queue")
        layout.addWidget(tabs)

    def _refresh_all(self):
        self._refresh_templates()
        self._refresh_queue()

    def _refresh_templates(self):
        self._template_list.clear()
        for name in self._prompts.template_names:
            desc = self._prompts.get_description(name)
            item = QListWidgetItem(f"{name}\n{desc[:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._template_list.addItem(item)

    def _refresh_queue(self):
        entries = self._queue.load_all()
        self._queue_list.clear()
        for e in entries:
            stars = "★" * e.rating + "☆" * (5 - e.rating)
            text = f"[{stars}] {e.song_title[:40]} — {e.output[:60]}"
            if e.note:
                text += f"  ({e.note[:30]})"
            self._queue_list.addItem(text)

    def _on_template_select(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            prompt = self._prompts.get_prompt(name)
            self._template_edit.setPlainText(prompt)
            self._template_edit.setProperty("current_name", name)

    def _save_template(self):
        name = self._template_edit.property("current_name")
        if name:
            self._prompts.set_prompt(name, self._template_edit.toPlainText())
            self._prompts.save()
            self._template_edit.setPlaceholderText(
                f"Saved '{name}' — select another or edit."
            )

    def _reset_to_base(self):
        reply = QMessageBox.question(
            self,
            "Reset to Base",
            "This will overwrite all prompt templates with the base versions. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._prompts.reset_to_base()
            self._refresh_templates()
            self._template_edit.clear()
            self._template_edit.setPlaceholderText(
                "Reset to base templates. Select one to view."
            )

    def _clear_queue(self):
        reply = QMessageBox.question(
            self,
            "Clear Queue",
            "Delete all feedback queue items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._queue.clear()
            self._refresh_queue()

    def _remove_selected(self):
        item = self._queue_list.currentItem()
        if item:
            idx = self._queue_list.row(item)
            self._queue.remove(idx)
            self._refresh_queue()

    def _process_queue(self):
        if self._processing:
            return
        entries = self._queue.load_all()
        if not entries:
            QMessageBox.information(
                self, "Empty Queue", "No feedback items to process."
            )
            return
        self._processing = True
        self._process_index = 0
        self._proc_progress.setVisible(True)
        self._proc_progress.setMaximum(len(entries))
        self._proc_progress.setValue(0)
        self._process_next()

    def _process_next(self):
        entries = self._queue.load_all()
        if self._process_index >= len(entries):
            self._processing = False
            self._proc_progress.setVisible(False)
            self._proc_status.setText(
                f"All {len(entries)} feedback items processed. Queue is empty."
            )
            self._refresh_all()
            return

        entry = entries[self._process_index]
        template_name = entry.prompt_template
        current_prompt = self._prompts.get_prompt(template_name)
        if not current_prompt:
            self._process_index += 1
            self._process_next()
            return

        self._proc_progress.setValue(self._process_index)
        self._proc_status.setText(
            f"Processing item {self._process_index + 1}/{len(entries)}: "
            f'"{entry.song_title[:40]}" rated {entry.rating}/5...'
        )

        refined_prompt_template = self._prompts.get_prompt("prompt_refinement")
        query = refined_prompt_template.format(
            rating=str(entry.rating),
            current_prompt=current_prompt,
            rated_output=entry.output,
            song_context=entry.song_context,
            note=entry.note or "none",
        )

        # Remove items 0..process_index from the queue so we commit progress
        # Actually we should only remove after successful processing
        # Let's remove after each successful item
        self._worker = OpenCodeWorker(
            prompt=query,
            working_dir=Path("."),
            model=self._model_combo.currentText(),
            variant=self._variant_combo.currentText(),
            continue_session=False,
        )
        self._worker.finished.connect(self._on_refinement_done)
        self._worker.error_occurred.connect(self._on_refinement_error)
        self._worker.start()

    def _on_refinement_done(self, refined: str):
        entries = self._queue.load_all()
        if self._process_index < len(entries):
            entry = entries[self._process_index]
            self._prompts.set_prompt(entry.prompt_template, refined.strip())
            self._prompts.save()
        # Remove the processed item
        self._queue.remove(0)
        self._process_index += 1
        self._on_template_select(
            self._template_list.currentItem() or self._template_list.item(0) or None
        )  # type: ignore[arg-type]
        self._process_next()

    def _on_refinement_error(self, msg: str):
        self._proc_status.setText(f"Error: {msg[:200]}")
        self._process_index += 1
        self._process_next()
