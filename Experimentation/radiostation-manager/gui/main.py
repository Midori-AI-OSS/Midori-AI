from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def main() -> int:
    if not os.environ.get("DISPLAY") and Path("/tmp/.X11-unix/X1").exists():
        os.environ["DISPLAY"] = ":1"
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)

    style_path = Path(__file__).parent / "resources" / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text())

    from gui.app import MainWindow

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
