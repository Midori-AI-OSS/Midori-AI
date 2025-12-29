def app_stylesheet() -> str:
    return """
    QWidget {
        color: #EDEFF5;
        font-family: Inter, Segoe UI, system-ui, -apple-system, sans-serif;
        font-size: 13px;
    }

    QMainWindow {
        background: transparent;
    }

    QLineEdit, QPlainTextEdit {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 10px;
        selection-background-color: rgba(56, 189, 248, 120);
    }

    QComboBox {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 9px 34px 9px 10px;
        selection-background-color: rgba(56, 189, 248, 120);
    }

    QComboBox:hover {
        border: 1px solid rgba(255, 255, 255, 30);
    }

    QComboBox:disabled {
        background-color: rgba(18, 20, 28, 90);
        color: rgba(237, 239, 245, 130);
        border: 1px solid rgba(255, 255, 255, 14);
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 28px;
        border-left: 1px solid rgba(255, 255, 255, 14);
        background-color: rgba(18, 20, 28, 120);
    }

    QComboBox QAbstractItemView {
        background-color: rgba(18, 20, 28, 240);
        border: 1px solid rgba(255, 255, 255, 22);
        outline: 0px;
        selection-background-color: rgba(56, 189, 248, 85);
    }

    QComboBox QAbstractItemView::item {
        padding: 8px 10px;
    }

    QPlainTextEdit {
        border-radius: 0px;
    }

    QPushButton {
        background-color: rgba(56, 189, 248, 165);
        border: 1px solid rgba(255, 255, 255, 24);
        border-radius: 0px;
        padding: 10px 14px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: rgba(56, 189, 248, 195);
    }

    QPushButton:pressed {
        background-color: rgba(56, 189, 248, 140);
    }

    QPushButton:disabled {
        background-color: rgba(100, 116, 139, 90);
        color: rgba(237, 239, 245, 130);
    }

    QToolButton {
        color: rgba(237, 239, 245, 235);
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 9px 12px;
        font-weight: 600;
    }

    QToolButton:hover {
        background-color: rgba(255, 255, 255, 14);
        border: 1px solid rgba(255, 255, 255, 30);
    }

    QToolButton:pressed {
        background-color: rgba(56, 189, 248, 70);
        border: 1px solid rgba(56, 189, 248, 100);
    }

    QToolButton:disabled {
        background-color: rgba(18, 20, 28, 90);
        color: rgba(237, 239, 245, 130);
        border: 1px solid rgba(255, 255, 255, 14);
    }

    QCheckBox {
        spacing: 10px;
    }

    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 0px;
        border: 1px solid rgba(255, 255, 255, 35);
        background-color: rgba(18, 20, 28, 170);
    }

    QCheckBox::indicator:checked {
        background-color: rgba(16, 185, 129, 165);
        border: 1px solid rgba(255, 255, 255, 35);
    }

    QScrollBar:vertical {
        background: rgba(0, 0, 0, 0);
        width: 10px;
        margin: 4px 2px 4px 2px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 35);
        border-radius: 0px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 55);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        subcontrol-origin: margin;
    }

    QScrollArea#TaskScroll {
        background: transparent;
        border: none;
    }
    QScrollArea#TaskScroll > QWidget > QWidget {
        background: transparent;
    }

    QTabWidget::pane {
        border: 1px solid rgba(255, 255, 255, 14);
        background: rgba(18, 20, 28, 55);
        margin-top: -1px;
    }

    QTabBar::tab {
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 18);
        padding: 8px 12px;
        margin-right: 6px;
        font-weight: 650;
    }

    QTabBar::tab:hover {
        background-color: rgba(255, 255, 255, 14);
        border: 1px solid rgba(255, 255, 255, 26);
    }

    QTabBar::tab:selected {
        background-color: rgba(56, 189, 248, 60);
        border: 1px solid rgba(56, 189, 248, 90);
    }
    QWidget#TaskList {
        background-color: rgba(18, 20, 28, 95);
        border: 1px solid rgba(255, 255, 255, 14);
        border-radius: 0px;
    }

    QWidget#TaskRow {
        border: 1px solid rgba(255, 255, 255, 12);
        border-left: 4px solid rgba(148, 163, 184, 110);
        border-radius: 0px;
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(148, 163, 184, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }

    QWidget#TaskRow[stain="slate"] {
        border-left-color: rgba(148, 163, 184, 110);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(148, 163, 184, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="cyan"] {
        border-left-color: rgba(56, 189, 248, 130);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(56, 189, 248, 22),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="emerald"] {
        border-left-color: rgba(16, 185, 129, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(16, 185, 129, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="violet"] {
        border-left-color: rgba(139, 92, 246, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(139, 92, 246, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="rose"] {
        border-left-color: rgba(244, 63, 94, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(244, 63, 94, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="amber"] {
        border-left-color: rgba(245, 158, 11, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(245, 158, 11, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }

    QWidget#TaskRow[stain="slate"]:hover,
    QWidget#TaskRow[stain="cyan"]:hover,
    QWidget#TaskRow[stain="emerald"]:hover,
    QWidget#TaskRow[stain="violet"]:hover,
    QWidget#TaskRow[stain="rose"]:hover,
    QWidget#TaskRow[stain="amber"]:hover {
        border-top: 1px solid rgba(255, 255, 255, 18);
        border-right: 1px solid rgba(255, 255, 255, 18);
        border-bottom: 1px solid rgba(255, 255, 255, 18);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(255, 255, 255, 14),
            stop: 1 rgba(18, 20, 28, 65)
        );
    }
    """
