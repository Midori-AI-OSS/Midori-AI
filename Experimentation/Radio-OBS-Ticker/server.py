from __future__ import annotations

import json
import asyncio
import logging
import urllib.request
from pathlib import Path

import tomli
import hypercorn.config
import hypercorn.asyncio

from quart import Quart
from quart import jsonify
from quart import send_file

CONFIG_PATH = Path(__file__).parent / "config.toml"
HTML_PATH = Path(__file__).parent / "index.html"
RADIO_BASE = "https://radio.midori-ai.xyz"
USER_AGENT = "MidoriAI-Radio-OBS-Ticker/1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("radio-obs-ticker")

app = Quart(__name__)

config: dict = {}
metadata_cache: dict[str, str | bool] = {}
metadata_lock = asyncio.Lock()
last_known_track_id: str = ""


def load_config() -> dict:
    raw = CONFIG_PATH.read_text()
    return tomli.loads(raw)


def build_stream_url(channel: str, quality: str) -> str:
    return f"{RADIO_BASE}/radio/v1/stream?channel={channel}&q={quality}"


def build_radio_api_url(resource: str, channel: str) -> str:
    return f"{RADIO_BASE}/radio/v1/{resource}?channel={channel}"


def build_request(url: str, *, accept: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def empty_metadata_payload() -> dict[str, str | bool]:
    return {
        "track_id": "",
        "current_title": "",
        "metadata_title": "",
        "artist": "",
        "comment": "",
        "matched": False,
    }


def normalize_title(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def reconcile_metadata(
    current_track: dict[str, str] | None,
    ffprobe_result: dict[str, str] | None,
) -> dict[str, str | bool]:
    current_track = current_track or {}
    ffprobe_result = ffprobe_result or {}

    current_title = str(current_track.get("title", "") or "")
    metadata_title = str(ffprobe_result.get("title", "") or "")
    matched = bool(
        current_title
        and metadata_title
        and normalize_title(current_title) == normalize_title(metadata_title)
    )

    return {
        "track_id": str(current_track.get("track_id", "") or ""),
        "current_title": current_title,
        "metadata_title": metadata_title,
        "artist": str(ffprobe_result.get("artist", "") or ""),
        "comment": str(ffprobe_result.get("comment", "") or "") if matched else "",
        "matched": matched,
    }


async def run_ffprobe(stream_url: str) -> dict[str, str]:
    ffprobe_path = config.get("ffprobe", {}).get("path", "ffprobe")
    timeout_s = config.get("ffprobe", {}).get("timeout_s", 8)

    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_format",
        "-of",
        "json",
        stream_url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)

        if proc.returncode != 0:
            err_text = stderr.decode(errors="replace").strip()
            log.warning("ffprobe exited %d: %s", proc.returncode, err_text)
            return {}

        data = json.loads(stdout.decode())
        tags = data.get("format", {}).get("tags", {})
        return {
            "title": tags.get("title", ""),
            "artist": tags.get("artist", ""),
            "comment": tags.get("comment", ""),
        }
    except asyncio.TimeoutError:
        log.warning("ffprobe timed out after %ds", timeout_s)
        return {}
    except Exception:
        log.exception("ffprobe failed")
        return {}


async def fetch_current_track() -> dict[str, str]:
    channel = config.get("audio", {}).get("channel", "all")
    url = build_radio_api_url("current", channel)

    try:
        with urllib.request.urlopen(
            build_request(url, accept="application/json"),
            timeout=5,
        ) as resp:
            data = json.loads(resp.read())
            current = data.get("data", {}) or {}
            return {
                "track_id": str(current.get("track_id", "") or ""),
                "title": str(current.get("title", "") or ""),
            }
    except Exception:
        return {}


async def refresh_metadata(stream_url: str) -> dict[str, str | bool]:
    current_track = await fetch_current_track()
    ffprobe_result = await run_ffprobe(stream_url)
    reconciled = reconcile_metadata(current_track, ffprobe_result)

    async with metadata_lock:
        metadata_cache.clear()
        metadata_cache.update(reconciled)

    return reconciled


async def ffprobe_refresh_loop() -> None:
    global last_known_track_id

    interval = config.get("polling", {}).get("ffprobe_interval_ms", 30000) / 1000.0
    channel = config.get("audio", {}).get("channel", "all")
    quality = config.get("audio", {}).get("quality", "high")
    stream_url = build_stream_url(channel, quality)

    while True:
        try:
            reconciled = await refresh_metadata(stream_url)
            current_id = str(reconciled.get("track_id", "") or "")

            if current_id and current_id != last_known_track_id:
                log.info(
                    "Track change detected (%s -> %s)",
                    last_known_track_id,
                    current_id,
                )
                last_known_track_id = current_id

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("ffprobe refresh loop error")
            await asyncio.sleep(interval)


@app.route("/")
async def index():
    return await send_file(HTML_PATH, mimetype="text/html")


@app.route("/api/config")
async def api_config():
    audio = config.get("audio", {})
    return jsonify(
        {
            "channel": audio.get("channel", "all"),
            "quality": audio.get("quality", "high"),
            "polling": {
                "metadata_interval_ms": config.get("polling", {}).get(
                    "metadata_interval_ms", 2000
                ),
            },
        }
    )


@app.route("/api/metadata")
async def api_metadata():
    async with metadata_lock:
        payload = dict(metadata_cache) if metadata_cache else empty_metadata_payload()
    return jsonify({"ok": True, **payload})


@app.route("/api/radio/current")
async def api_radio_current():
    channel = config.get("audio", {}).get("channel", "all")
    url = build_radio_api_url("current", channel)

    try:
        with urllib.request.urlopen(
            build_request(url, accept="application/json"),
            timeout=5,
        ) as resp:
            data = resp.read()
            return data, 200, {"Content-Type": "application/json"}
    except Exception as e:
        log.warning("Failed to fetch radio current: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/radio/art")
async def api_radio_art():
    channel = config.get("audio", {}).get("channel", "all")
    url = build_radio_api_url("art", channel)

    try:
        with urllib.request.urlopen(
            build_request(url, accept="application/json"),
            timeout=5,
        ) as resp:
            data = resp.read()
            return data, 200, {"Content-Type": "application/json"}
    except Exception as e:
        log.warning("Failed to fetch radio art: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/radio/art/image")
async def api_radio_art_image():
    channel = config.get("audio", {}).get("channel", "all")
    url = build_radio_api_url("art/image", channel)

    try:
        with urllib.request.urlopen(build_request(url), timeout=10) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            return data, 200, {"Content-Type": ct, "Cache-Control": "no-cache"}
    except Exception as e:
        log.warning("Failed to fetch radio art image: %s", e)
        return b"", 502


@app.before_serving
async def _startup():
    global last_known_track_id
    channel = config.get("audio", {}).get("channel", "all")
    quality = config.get("audio", {}).get("quality", "high")
    stream_url = build_stream_url(channel, quality)

    result = await refresh_metadata(stream_url)
    if result.get("current_title") or result.get("metadata_title"):
        last_known_track_id = str(result.get("track_id", "") or "")
        log.info(
            "Initial metadata: current_title=%s metadata_title=%s matched=%s track_id=%s",
            result.get("current_title", ""),
            result.get("metadata_title", ""),
            result.get("matched", False),
            last_known_track_id,
        )
    else:
        log.warning("Initial metadata refresh returned no data")

    asyncio.ensure_future(ffprobe_refresh_loop())


if __name__ == "__main__":
    config = load_config()
    port = config.get("port", {}).get("port", 8199)

    log.info("Radio OBS Ticker starting on port %d", port)
    log.info(
        "Config: channel=%s quality=%s",
        config.get("audio", {}).get("channel", "all"),
        config.get("audio", {}).get("quality", "high"),
    )

    hyper_cfg = hypercorn.config.Config()
    hyper_cfg.bind = [f"0.0.0.0:{port}"]

    asyncio.run(hypercorn.asyncio.serve(app, hyper_cfg))
