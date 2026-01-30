from __future__ import annotations


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

QFrame#mainMenuPanel, QWidget#mainMenuPanel {
    background-color: rgba(20, 30, 60, 130);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 0px;
}

QFrame#mainMenuPanel[fullScreen="true"], QWidget#mainMenuPanel[fullScreen="true"] {
    background-color: rgba(0, 0, 0, 245);
    border: none;
}

QFrame#mainMenuPanel[fullScreen="true"][mode="pause"], QWidget#mainMenuPanel[fullScreen="true"][mode="pause"] {
    background-color: rgba(0, 0, 0, 160);
}

QFrame#mainMenuPanel[fullScreen="true"][mode="game_over"], QWidget#mainMenuPanel[fullScreen="true"][mode="game_over"] {
    background-color: rgba(0, 0, 0, 220);
}

QPushButton[stainedMenu="true"] {
    background-color: rgba(255, 255, 255, 26);
    border: none;
    border-radius: 0px;
    padding: 10px 14px;
    color: rgba(255, 255, 255, 235);
    font-size: 14px;
    text-align: left;
}

QPushButton[stainedMenu="true"]:hover {
    background-color: rgba(120, 180, 255, 56);
}

QPushButton[stainedMenu="true"]:pressed {
    background-color: rgba(80, 140, 220, 72);
}

QDockWidget {
    background: transparent;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}

QDockWidget::title {
    background-color: rgba(18, 20, 28, 190);
    border: 1px solid rgba(255, 255, 255, 18);
    padding: 6px 10px;
    font-weight: 700;
    border-radius: 0px;
}

QGroupBox {
    border: 1px solid rgba(255, 255, 255, 12);
    margin-top: 10px;
    border-radius: 0px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0px 6px 0px 6px;
    color: rgba(237, 239, 245, 200);
    font-weight: 650;
}

QPushButton {
    color: rgba(237, 239, 245, 235);
    background-color: rgba(18, 20, 28, 135);
    border: 1px solid rgba(255, 255, 255, 22);
    border-radius: 0px;
    padding: 9px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(56, 189, 248, 30);
    border: 1px solid rgba(56, 189, 248, 80);
}

QPushButton:pressed {
    background-color: rgba(56, 189, 248, 70);
    border: 1px solid rgba(56, 189, 248, 100);
}

QPushButton:focus {
    border: 1px solid rgba(56, 189, 248, 105);
}

QPushButton:disabled {
    background-color: rgba(18, 20, 28, 90);
    color: rgba(237, 239, 245, 130);
    border: 1px solid rgba(255, 255, 255, 14);
}

QSlider::groove:horizontal {
    background: rgba(255, 255, 255, 14);
    height: 6px;
    border: 1px solid rgba(255, 255, 255, 16);
    border-radius: 0px;
}

QSlider::handle:horizontal {
    background: rgba(56, 189, 248, 140);
    border: 1px solid rgba(56, 189, 248, 220);
    width: 12px;
    margin: -6px 0px;
    border-radius: 0px;
}

QSlider::handle:horizontal:hover {
    background: rgba(56, 189, 248, 180);
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 0px;
    border: 1px solid rgba(255, 255, 255, 35);
    background-color: rgba(18, 20, 28, 170);
}

QCheckBox::indicator:hover {
    border: 1px solid rgba(56, 189, 248, 70);
    background-color: rgba(18, 20, 28, 200);
}

QCheckBox::indicator:checked {
    background-color: rgba(16, 185, 129, 165);
    border: 1px solid rgba(16, 185, 129, 180);
}

QLabel[role="dim"] {
    color: rgba(237, 239, 245, 165);
}
"""
