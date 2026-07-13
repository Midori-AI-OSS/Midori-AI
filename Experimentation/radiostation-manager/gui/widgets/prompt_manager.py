from __future__ import annotations

import tomllib
from difflib import SequenceMatcher
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
    QTabWidget,
    QComboBox,
    QProgressBar,
    QMessageBox,
)

from gui.core.config import get_config
from gui.core.prompts import PromptStore, FeedbackQueue
from gui.core.opencode_client import OpenCodeWorker
from gui.widgets.components import make_header, confirm
from gui.widgets.diff_dialog import DiffDialog


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
        self._sandbox_dir = Path("/tmp/midoriai/radiostation-manager/prompt_refinement")
        self._original_prompts_snapshot: dict[str, str] = {}
        self._retry_count = 0
        self._max_retries = 15
        self._setup_ui()
        self._refresh_all()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Manage Prompts", self.back.emit)
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

        process_row = QHBoxLayout()
        process_btn = QPushButton("Process Feedback Queue")
        process_btn.setObjectName("accentButton")
        process_btn.clicked.connect(self._process_queue)
        self._process_btn = process_btn
        process_row.addWidget(process_btn)

        self._stop_btn = QPushButton("Stop Processing")
        self._stop_btn.setObjectName("dangerButton")
        self._stop_btn.clicked.connect(self._stop_processing)
        self._stop_btn.setVisible(False)
        process_row.addWidget(self._stop_btn)

        process_row.addStretch()
        queue_layout.addLayout(process_row)

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
            pwin = self.window()
            if hasattr(pwin, "show_toast"):
                pwin.show_toast("Template saved", "success")

    def _reset_to_base(self):
        if not confirm(
            self,
            "Reset to Base",
            "This will overwrite all prompt templates with the base versions. Continue?",
        ):
            return
        self._prompts.reset_to_base()
        self._refresh_templates()
        self._template_edit.clear()
        pwin = self.window()
        if hasattr(pwin, "show_toast"):
            pwin.show_toast("Reset to base", "success")

    def _clear_queue(self):
        if not confirm(self, "Clear Queue", "Delete all feedback queue items?"):
            return
        self._queue.clear()
        self._refresh_queue()
        pwin = self.window()
        if hasattr(pwin, "show_toast"):
            pwin.show_toast("Queue cleared", "success")

    def _remove_selected(self):
        item = self._queue_list.currentItem()
        if item:
            idx = self._queue_list.row(item)
            self._queue.remove(idx)
            self._refresh_queue()

    def _copy_prompts_to_sandbox(self):
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        sandbox_toml = self._sandbox_dir / "prompts.toml"
        real_toml = Path("prompts.toml")
        if real_toml.exists():
            sandbox_toml.write_bytes(real_toml.read_bytes())
        self._original_prompts_snapshot = {
            name: self._prompts.get_prompt(name)
            for name in self._prompts.template_names
        }

    def _build_sandbox_prompt(self, entry, template_name: str) -> str:
        return (
            "You are helping improve an AI prompt template stored in a TOML file.\n\n"
            f"In this sandbox directory there is a file named `prompts.toml`. "
            "This file contains AI prompt templates used to generate music metadata comments.\n\n"
            "YOUR TASK:\n"
            f"1. Read the file `prompts.toml` in this directory\n"
            f'2. Find the `[{template_name}]` section\n'
            "3. Look at the feedback below about the output this template produced\n\n"
            "FEEDBACK:\n"
            f"The AI generated this text (rated {entry.rating}/5):\n"
            "```\n"
            f"{entry.output}\n"
            "```\n"
            f"Rating: {entry.rating}/5 (1 = trash, 5 = great)\n"
            f"Context: {entry.song_context}\n"
            f"User note: {entry.note or 'none'}\n\n"
            f"4. Write an IMPROVED version of the prompt into the `prompt` key "
            f'under `[{template_name}]` in `prompts.toml`\n\n'
            "RULES:\n"
            f"- ONLY modify the `prompt` value inside `[{template_name}]`\n"
            "- DO NOT change any other section, key, value, or description\n"
            "- DO NOT change the TOML file structure\n"
            '- Return only the word "DONE" when finished'
        )

    def _process_queue(self):
        if self._processing:
            return
        entries = self._queue.load_all()
        if not entries:
            QMessageBox.information(
                self, "Empty Queue", "No feedback items to process."
            )
            return
        self._copy_prompts_to_sandbox()
        self._processing = True
        self._retry_count = 0
        self._process_index = 0
        self._proc_progress.setVisible(True)
        self._proc_progress.setMaximum(len(entries))
        self._proc_progress.setValue(0)
        self._process_btn.setVisible(False)
        self._stop_btn.setVisible(True)
        self._proc_status.setText(
            f"Processing {len(entries)} feedback item(s)..."
        )
        self._process_next()

    def _process_next(self):
        if not self._processing:
            return
        entries = self._queue.load_all()
        if self._process_index >= len(entries):
            self._processing = False
            self._proc_progress.setVisible(False)
            self._process_btn.setVisible(True)
            self._stop_btn.setVisible(False)
            remaining = len(entries)
            if remaining:
                QMessageBox.information(
                    self,
                    "Processing Complete",
                    f"Done. {remaining} item(s) remain in queue.",
                )
            self._proc_status.setText(
                f"Done. {remaining} item(s) remain in queue."
                if remaining
                else "Queue is empty."
            )
            self._refresh_queue()
            return

        entry = entries[self._process_index]
        template_name = entry.prompt_template
        current_prompt = self._prompts.get_prompt(template_name)
        if not current_prompt:
            self._process_index += 1
            self._retry_count = 0
            self._process_next()
            return

        self._proc_progress.setValue(self._process_index)
        self._proc_progress.setMaximum(len(entries))
        self._proc_status.setText(
            f"Processing item {self._process_index + 1}/{len(entries)}: "
            f'"{entry.song_title[:40]}" rated {entry.rating}/5...'
        )

        query = self._build_sandbox_prompt(entry, template_name)
        self._worker = OpenCodeWorker(
            prompt=query,
            working_dir=self._sandbox_dir,
            model=self._model_combo.currentText(),
            variant=self._variant_combo.currentText(),
            continue_session=False,
        )
        self._worker.finished.connect(self._on_sandbox_done)
        self._worker.error_occurred.connect(self._on_sandbox_error)
        self._worker.start()

    def _on_sandbox_done(self, result_text: str):
        entries = self._queue.load_all()
        if self._process_index >= len(entries):
            self._process_next()
            return

        entry = entries[self._process_index]
        template_name = entry.prompt_template
        old_prompt = self._original_prompts_snapshot.get(template_name, "")

        sandbox_toml = self._sandbox_dir / "prompts.toml"
        file_new_prompt = None

        try:
            if sandbox_toml.exists():
                file_data = tomllib.loads(sandbox_toml.read_text())
                if template_name in file_data:
                    candidate = file_data[template_name].get("prompt", "")
                    if candidate and candidate != old_prompt:
                        file_new_prompt = candidate

                        sections_ok = True
                        for name, original_text in (
                            self._original_prompts_snapshot.items()
                        ):
                            if name == template_name:
                                continue
                            if name in file_data:
                                if (
                                    file_data[name].get("prompt", "")
                                    != original_text
                                ):
                                    sections_ok = False
                                    break
                        if not sections_ok:
                            file_new_prompt = None
        except Exception:
            file_new_prompt = None

        text_new_prompt = None
        cleaned = result_text.strip()
        if cleaned and cleaned.upper() != "DONE" and len(cleaned) >= 100:
            text_new_prompt = cleaned

        if file_new_prompt:
            new_prompt = file_new_prompt
            self._proc_status.setText(
                "Refinement extracted from sandbox file"
            )
        elif text_new_prompt:
            new_prompt = text_new_prompt
            self._proc_status.setText(
                "Refinement extracted from OpenCode output"
            )
        else:
            return self._handle_auto_fail(
                "No refinement found — file unchanged and output was empty/DONE"
            )

        new_len = len(new_prompt)
        if new_len < 100:
            return self._handle_auto_fail(
                f"Too short: {new_len} chars (need >= 100)"
            )
        if new_len > 5000:
            return self._handle_auto_fail(
                f"Too long: {new_len} chars (max 5000)"
            )

        ratio = SequenceMatcher(None, old_prompt, new_prompt).ratio()
        if ratio < 0.5:
            return self._handle_auto_fail(
                f"Too different: {ratio:.0%} similar (need >= 50%)"
            )

        dialog = DiffDialog(old_prompt, new_prompt, template_name, self)
        if dialog.result():
            self._prompts.set_prompt(template_name, new_prompt)
            self._prompts.save()
            self._queue.remove(self._process_index)
            self._retry_count = 0
            self._proc_status.setText(
                f"Prompt [{template_name}] refined and saved"
            )
            pwin = self.window()
            if hasattr(pwin, "show_toast"):
                pwin.show_toast("Prompt refined", "success")
        else:
            self._proc_status.setText("Rejected, retrying...")
            return self._process_next()

        self._process_next()

    def _handle_auto_fail(self, reason: str):
        self._retry_count += 1
        if self._retry_count >= self._max_retries:
            QMessageBox.warning(
                self,
                "Auto-Fail",
                f"Gave up after {self._max_retries} retries:\n{reason}",
            )
            self._proc_status.setText(
                f"Gave up after {self._max_retries} retries: {reason}"
            )
            self._retry_count = 0
            self._process_index += 1
            self._process_next()
            return

        self._proc_status.setText(
            f"Auto-fail ({self._retry_count}/{self._max_retries}): {reason}, retrying..."
        )
        self._process_next()

    def _on_sandbox_error(self, msg: str):
        QMessageBox.warning(
            self,
            "Processing Error",
            f"OpenCode error on item {self._process_index + 1}:\n{msg[:500]}",
        )
        self._proc_status.setText(f"Error: {msg[:200]}")
        self._retry_count = 0
        self._process_index += 1
        self._process_next()

    def _stop_processing(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self._processing = False
        self._retry_count = 0
        self._proc_progress.setVisible(False)
        self._process_btn.setVisible(True)
        self._stop_btn.setVisible(False)
        self._proc_status.setText("Processing stopped by user")
        self._refresh_queue()
