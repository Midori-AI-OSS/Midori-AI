from __future__ import annotations

from difflib import SequenceMatcher

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QStyle,
)


class DiffDialog(QDialog):
    def __init__(
        self,
        old_text: str,
        new_text: str,
        template_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Review Refinement — {template_name}")
        self.resize(1000, 700)
        self.setModal(True)
        self._accepted = False

        ratio = SequenceMatcher(None, old_text, new_text).ratio()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        panes = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Original Prompt"))
        old_edit = QTextEdit()
        old_edit.setReadOnly(True)
        old_edit.setObjectName("diffView")
        old_edit.setPlainText(old_text)
        left_col.addWidget(old_edit)
        panes.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Refined Prompt"))
        new_edit = QTextEdit()
        new_edit.setReadOnly(True)
        new_edit.setObjectName("diffView")
        new_edit.setPlainText(new_text)
        right_col.addWidget(new_edit)
        panes.addLayout(right_col)

        layout.addLayout(panes)

        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel(f"Changed: {ratio:.0%}"))
        stats_row.addWidget(QLabel(f"|"))
        stats_row.addWidget(QLabel(f"Old: {len(old_text)} chars"))
        stats_row.addWidget(QLabel(f"|"))
        stats_row.addWidget(QLabel(f"New: {len(new_text)} chars"))
        stats_row.addStretch()
        layout.addLayout(stats_row)

        self._fail_banner = QLabel()
        self._fail_banner.setObjectName("diffFailBanner")
        self._fail_banner.setWordWrap(True)
        self._fail_banner.setVisible(False)
        layout.addWidget(self._fail_banner)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reject_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton)
        self._reject_btn = QPushButton("Reject")
        self._reject_btn.setIcon(reject_icon)
        self._reject_btn.setObjectName("dangerButton")
        self._reject_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._reject_btn)

        accept_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        self._accept_btn = QPushButton("Accept")
        self._accept_btn.setIcon(accept_icon)
        self._accept_btn.setObjectName("successButton")
        self._accept_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(self._accept_btn)

        layout.addLayout(btn_row)

    def set_auto_fail(self, reason: str):
        self._fail_banner.setText(f"Auto-fail: {reason}")
        self._fail_banner.setVisible(True)
        self._accept_btn.setEnabled(False)
        self._accept_btn.setVisible(False)

    def _on_accept(self):
        self._accepted = True
        self.accept()

    def result(self) -> bool:
        self.exec()
        return self._accepted
