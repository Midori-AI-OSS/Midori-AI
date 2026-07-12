from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QRunnable, Signal, QObject


class EssentiaSignals(QObject):
    finished = Signal(str, str)
    error_occurred = Signal(str, str)


class EssentiaWorker(QRunnable):
    def __init__(self, song_path: Path, uv_workdir: Path, uv_package_spec: str):
        super().__init__()
        self.song_path = song_path
        self.uv_workdir = uv_workdir
        self.uv_package_spec = uv_package_spec
        self.signals = EssentiaSignals()

    def run(self):
        song_key = str(self.song_path)
        try:
            analysis = self._analyze()
            summary = self._build_summary(analysis)
            self.signals.finished.emit(song_key, f"{analysis}|{summary}")
        except Exception as e:
            self.signals.error_occurred.emit(song_key, str(e))

    def _analyze(self) -> str:
        venv_python = self.uv_workdir / ".venv" / "bin" / "python"
        if not venv_python.exists():
            subprocess.run(
                ["uv", "venv", str(self.uv_workdir / ".venv")],
                capture_output=True,
                text=True,
                timeout=60,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(venv_python),
                    self.uv_package_spec,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        result = subprocess.run(
            [str(venv_python), "-c", ESSENTIA_SCRIPT, str(self.song_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Essentia analysis failed")
        return result.stdout.strip()

    def _build_summary(self, analysis: str) -> str:
        parts = []
        metrics = {}
        for segment in analysis.split("; "):
            if "=" in segment:
                k, v = segment.split("=", 1)
                metrics[k.strip()] = v.strip()

        tempo_raw = metrics.get("tempo", "")
        tempo_val = tempo_raw.split()[0] if tempo_raw else ""
        try:
            t = float(tempo_val)
            if t < 80:
                parts.append("slow tempo")
            elif t < 110:
                parts.append("steady tempo")
            elif t < 145:
                parts.append("driving tempo")
            else:
                parts.append("fast tempo")
        except ValueError:
            pass

        rms_raw = metrics.get("rms_mean", "")
        try:
            r = float(rms_raw)
            if r < 0.035:
                parts.append("soft dynamics")
            elif r < 0.080:
                parts.append("balanced dynamics")
            else:
                parts.append("strong dynamics")
        except ValueError:
            pass

        centroid_raw = metrics.get("centroid_mean_hz", "")
        try:
            c = float(centroid_raw)
            if c < 1700:
                parts.append("warm tone")
            elif c < 3200:
                parts.append("neutral tone")
            else:
                parts.append("bright tone")
        except ValueError:
            pass

        key_raw = metrics.get("key", "")
        if key_raw:
            parts.append(f"key {key_raw}")

        if not parts:
            return "unknown vibes"
        return ", ".join(parts)


ESSENTIA_SCRIPT = r"""
import sys
import essentia.standard as es

song_file = sys.argv[1]

def mean(values):
    if not values: return None
    return sum(values) / float(len(values))

def safe_float(value):
    try: return float(value)
    except: return None

sample_rate = 44100
audio = es.MonoLoader(filename=song_file, sampleRate=sample_rate)()
if len(audio) == 0:
    sys.exit(1)

duration = len(audio) / float(sample_rate)
bpm, ticks, confidence, _, _ = es.RhythmExtractor2013(method='multifeature')(audio)
key, scale, strength = es.KeyExtractor()(audio)
onset_rate = (len(ticks) / duration) if duration > 0 else None

parts = [f"tempo={float(bpm):.2f} BPM"]
if key:
    key_text = str(key)
    if scale: key_text = f"{key_text} {scale}"
    key_text = f"{key_text} (strength {float(strength):.2f})"
    parts.append(f"key={key_text}")
parts.append(f"rhythm_confidence={float(confidence):.3f}")
parts.append(f"duration={duration:.2f}s")
if onset_rate is not None:
    parts.append(f"onset_rate={onset_rate:.2f}/s")

frame_size = 2048
hop_size = 512
windowing = es.Windowing(type='hann')
spectrum = es.Spectrum(size=frame_size)
rms_algo = es.RMS()
centroid_algo = es.Centroid(range=sample_rate / 2.0)

rms_values = []
centroid_values = []

for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
    if len(frame) == 0: continue
    rms_value = safe_float(rms_algo(frame))
    if rms_value is not None: rms_values.append(rms_value)
    try:
        spec = spectrum(windowing(frame))
        c_val = safe_float(centroid_algo(spec))
        if c_val is not None: centroid_values.append(c_val)
    except: pass

rms_mean = mean(rms_values)
if rms_mean is not None: parts.append(f"rms_mean={rms_mean:.4f}")
centroid_mean = mean(centroid_values)
if centroid_mean is not None: parts.append(f"centroid_mean_hz={centroid_mean:.2f}")

print("; ".join(parts))
"""
