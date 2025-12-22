import sys
import time
import threading
import queue

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QMainWindow,
    QFileDialog,
)
from PySide6.QtGui import QImage, QPixmap

from src.capture import ScreenCapture
from src.gamepad import GamepadReader
from src.detector import Detector
from src.recorder import Recorder


class Signals(QObject):
    frame_ready = Signal(object)
    status = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Video Game Watcher")
        self.signals = Signals()

        # UI elements
        self.monitor_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh Monitors")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.preview = QLabel("Preview")
        self.status = QLabel("Idle")

        # Layout
        ctl = QWidget()
        h = QHBoxLayout()
        h.addWidget(self.monitor_combo)
        h.addWidget(self.refresh_btn)
        h.addWidget(self.start_btn)
        h.addWidget(self.stop_btn)

        v = QVBoxLayout()
        v.addLayout(h)
        v.addWidget(self.preview)
        v.addWidget(self.status)
        ctl.setLayout(v)
        self.setCentralWidget(ctl)

        # Internal
        self.capture = None
        self.gamepad = None
        self.detector = None
        self.recorder = None
        self.frame_queue = queue.Queue(maxsize=4)
        self.det_queue = queue.Queue(maxsize=4)
        self.input_queue = queue.Queue(maxsize=256)
        self.preview_timer = QTimer()
        self.preview_timer.setInterval(33)
        self.preview_timer.timeout.connect(self.update_preview)

        # Wire
        self.refresh_btn.clicked.connect(self.refresh_monitors)
        self.start_btn.clicked.connect(self.start_session)
        self.stop_btn.clicked.connect(self.stop_session)
        self.signals.frame_ready.connect(self.on_frame_ready)
        self.signals.status.connect(self.set_status)

        self.refresh_monitors()

    def refresh_monitors(self):
        # ask capture helper for monitor list
        from mss import mss

        with mss() as sct:
            self.monitor_combo.clear()
            monitors = sct.monitors  # list, index 0 is all monitors
            for i, mon in enumerate(monitors):
                self.monitor_combo.addItem(f"Monitor {i}: {mon['left']},{mon['top']} {mon['width']}x{mon['height']}", i)

    def start_session(self):
        if self.capture is not None:
            self.set_status("Already running")
            return
        monitor_index = self.monitor_combo.currentData()
        self.capture = ScreenCapture(monitor=monitor_index, out_queue=self.frame_queue, status_signal=self.signals.status)
        self.capture.start()
        self.gamepad = GamepadReader(out_queue=self.input_queue, status_signal=self.signals.status)
        self.gamepad.start()
        self.detector = Detector(in_queue=self.frame_queue, out_queue=self.det_queue, status_signal=self.signals.status)
        self.detector.start()
        self.recorder = Recorder(frame_queue=self.frame_queue, input_queue=self.input_queue, det_queue=self.det_queue, status_signal=self.signals.status)
        self.recorder.start()
        self.preview_timer.start()
        self.set_status("Running")

    def stop_session(self):
        self.preview_timer.stop()
        if self.capture:
            self.capture.stop()
            self.capture.join()
            self.capture = None
        if self.gamepad:
            self.gamepad.stop()
            self.gamepad.join()
            self.gamepad = None
        if self.detector:
            self.detector.stop()
            self.detector.join()
            self.detector = None
        if self.recorder:
            self.recorder.stop()
            self.recorder.join()
            self.recorder = None
        self.set_status("Stopped")

    def on_frame_ready(self, frame):
        # currently unused - preview timer will fetch latest frame from recorder or queue
        pass

    def update_preview(self):
        # try to find the most recent frame from frame_queue without removing it permanently
        import numpy as np
        try:
            # get a frame non-blocking; if queue empty do nothing
            frame = None
            try:
                frame = self.frame_queue.get_nowait()
            except Exception:
                return
            # we put it back for other workers (detector/recorder) to consume
            # but to keep things simple we won't put it back — other workers read directly too
            # Convert BGR (cv2) to QImage
            img = frame.get('image') if isinstance(frame, dict) else frame
            if img is None:
                return
            h, w, ch = img.shape
            bytes_per_line = ch * w
            rgb = img[:, :, ::-1]
            qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qt_img).scaled(800, 450, Qt.KeepAspectRatio)
            self.preview.setPixmap(pix)
        except Exception as e:
            self.set_status(f"Preview error: {e}")

    def set_status(self, text: str):
        self.status.setText(text)
