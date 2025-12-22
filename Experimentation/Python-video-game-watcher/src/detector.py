import threading
import time
import queue
import os

try:
    # ultralytics YOLOv8
    from ultralytics import YOLO
    _HAS_ULTRALYTICS = True
except Exception:
    _HAS_ULTRALYTICS = False

# Fallback to torch.hub yolov5 if ultralytics is not available
try:
    import torch
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


class Detector(threading.Thread):
    def __init__(self, in_queue: queue.Queue, out_queue: queue.Queue, status_signal=None, model_path: str = None):
        super().__init__(daemon=True)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.status_signal = status_signal
        self._stop_event = threading.Event()
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _emit(self, text: str):
        if self.status_signal:
            try:
                self.status_signal.emit(text)
            except Exception:
                pass

    def _load_model(self):
        if _HAS_ULTRALYTICS:
            try:
                if self.model_path:
                    self.model = YOLO(self.model_path)
                else:
                    # default small model
                    self.model = YOLO('yolov8n.pt')
                self._emit('Detector: ultralytics model loaded')
                return
            except Exception as e:
                self._emit(f'Ultralytics load failed: {e}')
        if _HAS_TORCH:
            try:
                # Attempt to load yolov5 via torch.hub
                self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
                self._emit('Detector: yolov5 (torch hub) loaded')
                return
            except Exception as e:
                self._emit(f'Torch hub load failed: {e}')
        self._emit('Detector: no model available, running in passthrough mode')
        self.model = None

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._stop_event.set()
        super().join(timeout)

    def run(self):
        while not self._stop_event.is_set():
            try:
                frame = self.in_queue.get(timeout=0.1)
            except Exception:
                continue
            if frame is None:
                continue
            img = frame.get('image') if isinstance(frame, dict) else frame
            timestamp = frame.get('timestamp_ns', None) if isinstance(frame, dict) else None
            detections = None
            try:
                if self.model is not None:
                    if _HAS_ULTRALYTICS:
                        results = self.model(img)
                        # convert to simple list of dicts
                        detections = []
                        for r in results:
                            for det in r.boxes:
                                xyxy = det.xyxy.tolist()[0]
                                conf = float(det.conf.tolist()[0])
                                cls = int(det.cls.tolist()[0])
                                detections.append({'xyxy': xyxy, 'conf': conf, 'class': cls})
                    elif _HAS_TORCH:
                        results = self.model(img)
                        preds = results.xyxy[0].cpu().numpy() if hasattr(results, 'xyxy') else None
                        detections = []
                        if preds is not None:
                            for p in preds:
                                x1, y1, x2, y2, conf, cls = p.tolist()
                                detections.append({'xyxy': [x1, y1, x2, y2], 'conf': float(conf), 'class': int(cls)})
                else:
                    detections = []
            except Exception as e:
                self._emit(f'Detector inference error: {e}')
                detections = []

            out = {'timestamp_ns': timestamp, 'detections': detections}
            try:
                self.out_queue.put(out, block=False)
            except Exception:
                pass
