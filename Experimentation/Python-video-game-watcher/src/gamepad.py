import threading
import time
import queue

# Uses pygame.joystick to read controllers; falls back gracefully

try:
    import pygame
    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False


class GamepadReader(threading.Thread):
    def __init__(self, out_queue: queue.Queue, status_signal=None, poll_hz: int = 120):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.status_signal = status_signal
        self._stop_event = threading.Event()
        self.poll_interval = 1.0 / poll_hz
        self.joystick = None

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._stop_event.set()
        super().join(timeout)

    def _init_pygame(self):
        if not _HAS_PYGAME:
            return False
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
            return True
        except Exception as e:
            if self.status_signal:
                try:
                    self.status_signal.emit(f"Gamepad init error: {e}")
                except Exception:
                    pass
            return False

    def run(self):
        initialized = self._init_pygame()
        if not initialized and self.status_signal:
            try:
                self.status_signal.emit("Gamepad: pygame not available or no joystick")
            except Exception:
                pass

        while not self._stop_event.is_set():
            ts = time.time_ns()
            state = {'timestamp_ns': ts, 'buttons': {}, 'axes': {}}
            if self.joystick is not None:
                try:
                    pygame.event.pump()
                    n_axes = self.joystick.get_numaxes()
                    for i in range(n_axes):
                        state['axes'][f'a{i}'] = float(self.joystick.get_axis(i))
                    n_buttons = self.joystick.get_numbuttons()
                    for i in range(n_buttons):
                        state['buttons'][f'b{i}'] = int(self.joystick.get_button(i))
                except Exception:
                    pass
            # If no joystick, still push empty state so recorder can pair
            try:
                self.out_queue.put(state, block=False)
            except Exception:
                pass
            time.sleep(self.poll_interval)
