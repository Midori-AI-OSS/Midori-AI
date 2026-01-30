import sys
import os
import getpass
from pathlib import Path

# Ensure current dir is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from point_cloud_game.ui import GameWindow

def main():
    if not os.environ.get("DISPLAY") and Path("/tmp/.X11-unix/X1").exists():
        os.environ["DISPLAY"] = ":1"
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/tmp/xdg-{getpass.getuser()}")
    Path(os.environ["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)

    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(0)
    fmt.setStencilBufferSize(0)
    fmt.setSamples(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    
    # Dark Mode Palette
    # (Optional, styling handles most)
    
    window = GameWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
