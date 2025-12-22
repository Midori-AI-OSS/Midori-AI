import threading
import time
import queue
from typing import Optional

import cv2
import numpy as np
from mss import mss


class ScreenCapture(threading.Thread):
    def __init__(self, monitor: Optional[int], out_queue: queue.Queue, status_signal=None, fps: int = 30):
        super().__init__(daemon=True)
        self.monitor_index = monitor
        self.out_queue = out_queue
        self.status_signal = status_signal
        self._stop_event = threading.Event()
        self.fps = fps
        self._interval = 1.0 / fps

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._stop_event.set()
        super().join(timeout)

    def run(self):
        with mss() as sct:
            monitors = sct.monitors
            mon = None
            if self.monitor_index is None:
                mon = monitors[0]
            else:
                try:
                    mon = monitors[self.monitor_index]
                except Exception:
                    mon = monitors[0]

            last = time.time()
            while not self._stop_event.is_set():
                t0 = time.time()
                sct_img = sct.grab(mon)
                # Convert to numpy array (BGRA)
                img = np.array(sct_img)
                # Drop alpha channel
                if img.shape[2] == 4:
                    img = img[:, :, :3]
                # mss gives BGRA/BGR order already compatible with cv2
                # Optionally resize or convert color
                frame = {
                    'timestamp_ns': time.time_ns(),
                    'image': img,
                    'monitor': self.monitor_index,
                }
                try:
                    self.out_queue.put(frame, block=False)
                except Exception:
                    # queue full; drop frame
                    if self.status_signal:
                        try:
                            self.status_signal.emit('Capture: queue full, dropping frame')
                        except Exception:
                            pass
                t1 = time.time()
                elapsed = t1 - t0
                to_sleep = max(0.0, self._interval - elapsed)
                time.sleep(to_sleep)
