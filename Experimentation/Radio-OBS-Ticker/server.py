from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import tomli
from quart import Quart
from quart import jsonify
from quart import request
from quart import send_file
from quart import Response

CONFIG_PATH = Path(__file__).parent / "config.toml"
HTML_PATH = Path(__file__).parent / "index.html"
RADIO_BASE = "https://radio.midori-ai.xyz"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("radio-obs-ticker")

app = Quart(__name__)

config: dict = {}
ffprobe_cache: dict = {}
ffprobe_lock = asyncio.Lock()
last_known_track_id: str = ""


def load_config() -> dict:
    raw = CONFIG_PATH.read_text()
    return tomli.loads(raw)


def build_stream_url(channel: str, quality: str) -> str:
    return f"{RADIO_BASE}/radio/v1/stream?channel={channel}&q={quality}"


async def run_ffprobe(stream_url: str) -> dict:
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


async def fetch_current_track_id() -> str:
    import urllib.request

    channel = config.get("audio", {}).get("channel", "all")
    url = f"{RADIO_BASE}/radio/v1/current?channel={channel}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "MidoriAI-Radio-OBS-Ticker/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("data", {}).get("track_id", "")
    except Exception:
        return ""


async def ffprobe_refresh_loop() -> None:
    global last_known_track_id

    interval = config.get("polling", {}).get("ffprobe_interval_ms", 30000) / 1000.0
    channel = config.get("audio", {}).get("channel", "all")
    quality = config.get("audio", {}).get("quality", "high")
    stream_url = build_stream_url(channel, quality)

    while True:
        try:
            current_id = await fetch_current_track_id()
            track_changed = current_id != last_known_track_id and current_id != ""

            if track_changed or not ffprobe_cache:
                log.info(
                    "Track change detected (%s -> %s), running ffprobe",
                    last_known_track_id,
                    current_id,
                )
                async with ffprobe_lock:
                    result = await run_ffprobe(stream_url)
                    if result:
                        ffprobe_cache.update(result)
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
            "volume": audio.get("volume", 0.5),
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
    async with ffprobe_lock:
        return jsonify(
            {
                "ok": True,
                "title": ffprobe_cache.get("title", ""),
                "artist": ffprobe_cache.get("artist", ""),
                "comment": ffprobe_cache.get("comment", ""),
            }
        )


@app.route("/api/radio/current")
async def api_radio_current():
    channel = config.get("audio", {}).get("channel", "all")
    url = f"{RADIO_BASE}/radio/v1/current?channel={channel}"
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "MidoriAI-Radio-OBS-Ticker/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            return data, 200, {"Content-Type": "application/json"}
    except Exception as e:
        log.warning("Failed to fetch radio current: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/radio/art")
async def api_radio_art():
    channel = config.get("audio", {}).get("channel", "all")
    url = f"{RADIO_BASE}/radio/v1/art?channel={channel}"
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "MidoriAI-Radio-OBS-Ticker/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            return data, 200, {"Content-Type": "application/json"}
    except Exception as e:
        log.warning("Failed to fetch radio art: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/radio/art/image")
async def api_radio_art_image():
    channel = config.get("audio", {}).get("channel", "all")
    url = f"{RADIO_BASE}/radio/v1/art/image?channel={channel}"
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MidoriAI-Radio-OBS-Ticker/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            return data, 200, {"Content-Type": ct, "Cache-Control": "no-cache"}
    except Exception as e:
        log.warning("Failed to fetch radio art image: %s", e)
        return b"", 502


@app.route("/api/radio/stream")
async def api_radio_stream():
    import aiohttp

    channel = request.args.get("channel", config.get("audio", {}).get("channel", "all"))
    quality = request.args.get("q", config.get("audio", {}).get("quality", "high"))
    url = f"{RADIO_BASE}/radio/v1/stream?channel={channel}&q={quality}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"User-Agent": "MidoriAI-Radio-OBS-Ticker/1.0"},
            ) as resp:
                content_type = resp.headers.get("Content-Type", "audio/mpeg")

                async def generate():
                    async for chunk in resp.content.iter_chunked(4096):
                        yield chunk

                return Response(
                    generate(),
                    mimetype=content_type,
                    headers={
                        "Cache-Control": "no-cache",
                        "Accept-Ranges": "none",
                    },
                )
    except Exception as e:
        log.warning("Failed to stream audio: %s", e)
        return b"", 502


@app.before_serving
async def _startup():
    global last_known_track_id
    channel = config.get("audio", {}).get("channel", "all")
    quality = config.get("audio", {}).get("quality", "high")
    stream_url = build_stream_url(channel, quality)

    result = await run_ffprobe(stream_url)
    if result:
        ffprobe_cache.update(result)
        last_known_track_id = await fetch_current_track_id()
        log.info(
            "Initial ffprobe: title=%s artist=%s track_id=%s",
            result.get("title", ""),
            result.get("artist", ""),
            last_known_track_id,
        )
    else:
        log.warning("Initial ffprobe returned no data")

    asyncio.ensure_future(ffprobe_refresh_loop())


if __name__ == "__main__":
    config = load_config()
    port = config.get("port", {}).get("port", 8199)

    log.info("Radio OBS Ticker starting on port %d", port)
    log.info(
        "Config: channel=%s quality=%s volume=%.2f",
        config.get("audio", {}).get("channel", "all"),
        config.get("audio", {}).get("quality", "high"),
        config.get("audio", {}).get("volume", 0.5),
    )

    import hypercorn.asyncio
    import hypercorn.config

    hyper_cfg = hypercorn.config.Config()
    hyper_cfg.bind = [f"0.0.0.0:{port}"]

    asyncio.run(hypercorn.asyncio.serve(app, hyper_cfg))
