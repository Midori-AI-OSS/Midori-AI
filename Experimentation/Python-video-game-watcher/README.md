Python Video Game Watcher
=========================

Goal
----
Capture the selected monitor, read gamepad inputs while the user plays, run a YOLO model on frames in near real-time, and record paired frame+input+detections for later training of an agent that mimics the player.

Quick start
-----------
1. Create and activate a Python venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies (PySide6 + others). On Linux, install `torch` matching your CUDA first if you want GPU acceleration; otherwise CPU-only will work but slow.

```bash
pip install -r requirements.txt
# If you need GPU accel, install the correct torch wheel from https://pytorch.org
```

3. Run the app:

```bash
python -m src.main
```

What this repo contains
-----------------------
- `src/main.py`: application entry (PySide6)
- `src/ui.py`: GUI widgets
- `src/capture.py`: screen capture worker using `mss`
- `src/gamepad.py`: gamepad reader (pygame-based)
- `src/detector.py`: YOLO wrapper using `ultralytics` or fallback
- `src/recorder.py`: pairs frames+inputs+detections and writes `session` dataset
- `requirements.txt`: suggested libraries

Dataset layout
--------------
Each session is saved under `data/sessions/session_<iso_ts>/` with:
- `images/frame_<ts>.jpg`
- `meta.jsonl` (one JSON object per line with timestamp, frame path, gamepad state, detections)
- `session_meta.json` (session settings)

Notes
-----
- This is a starting scaffold. YOLO inference, performance tuning, and advanced dataset handling will need iteration.
- On Linux, `pygame` may need SDL and joystick drivers. If `pygame` cannot access the controller, try the `inputs` or `evdev` library alternatives.

Next steps
----------
- Run the app and verify capture + preview works.
- Test gamepad readings and session saving for short runs.
- Hook up a real YOLO model (weights) or use `ultralytics` default for prototyping.

If you'd like, I can now:
- Run small tests here to validate file imports and basic capture (non-GUI), or
- Implement a packaged `pyproject.toml` and a single-run smoke test script.
