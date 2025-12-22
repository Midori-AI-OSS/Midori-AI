import threading
import time
import os
import json
import queue
from pathlib import Path
from datetime import datetime


class Recorder(threading.Thread):
    def __init__(self, frame_queue: queue.Queue, input_queue: queue.Queue, det_queue: queue.Queue, status_signal=None, out_dir: str = None):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.input_queue = input_queue
        self.det_queue = det_queue
        self.status_signal = status_signal
        self._stop_event = threading.Event()
        self.session_dir = None
        self.out_dir = out_dir or os.path.join('data', 'sessions')
        self._ensure_session()

    def _ensure_session(self):
        ts = datetime.utcnow().isoformat(timespec='seconds').replace(':', '-')
        path = Path(self.out_dir) / f'session_{ts}'
        path.mkdir(parents=True, exist_ok=True)
        (path / 'images').mkdir(exist_ok=True)
        self.session_dir = path
        self.meta_file = open(path / 'meta.jsonl', 'a', encoding='utf8')
        # write session meta
        with open(path / 'session_meta.json', 'w', encoding='utf8') as f:
            json.dump({'started_at': ts}, f)

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._stop_event.set()
        super().join(timeout)
        try:
            self.meta_file.flush()
            self.meta_file.close()
        except Exception:
            pass

    def _emit(self, text: str):
        if self.status_signal:
            try:
                self.status_signal.emit(text)
            except Exception:
                pass

    def run(self):
        # We'll implement a simple pairing strategy: when a frame arrives, find the latest gamepad state and latest detections (non-blocking)
        import cv2
        while not self._stop_event.is_set():
            try:
                frame = self.frame_queue.get(timeout=0.5)
            except Exception:
                continue
            if frame is None:
                continue
            ts = frame.get('timestamp_ns', time.time_ns())
            img = frame.get('image')
            # get latest gamepad state
            latest_input = None
            try:
                while True:
                    candidate = self.input_queue.get_nowait()
                    latest_input = candidate
                # exhausted
            except Exception:
                pass
            # get latest detection
            latest_det = None
            try:
                while True:
                    candidate = self.det_queue.get_nowait()
                    latest_det = candidate
            except Exception:
                pass

            # Save image
            fn = f"frame_{ts}.jpg"
            imgpath = self.session_dir / 'images' / fn
            try:
                # write JPEG
                cv2.imwrite(str(imgpath), img)
            except Exception as e:
                self._emit(f"Recorder: failed to write image {e}")
                continue

            meta = {
                'timestamp_ns': ts,
                'frame_file': str(Path('images') / fn),
                'gamepad': latest_input,
                'detections': latest_det,
            }
            try:
                self.meta_file.write(json.dumps(meta, ensure_ascii=False) + "\n")
                self.meta_file.flush()
            except Exception as e:
                self._emit(f"Recorder: failed to write meta {e}")
                continue
