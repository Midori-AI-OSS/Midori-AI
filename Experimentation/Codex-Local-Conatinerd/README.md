Run the GUI:

`uv run main.py`

UI styling lives in `codex_local_conatinerd/style.py` (Qt stylesheet) and `codex_local_conatinerd/widgets.py` (custom-painted widgets). The default look uses square corners (no rounded borders).

It starts a Docker container using `lunamidori5/pixelarch:emerald` and runs:

`codex exec --sandbox danger-full-access <your prompt>`

Interactive mode:

- Click `New task`, then use `Run Interactive` to launch a real TTY session in your installed terminal emulator (Linux/macOS).
- It runs the container with `docker run -it …` and (by default) starts `codex --sandbox danger-full-access` (no `exec`), so you can use agent TUIs.
- “Container command args” accepts flags for the configured Agent CLI (starting with `-`), or a full container command like `bash`.

If you see `executable file not found in $PATH` for `codex`, the GUI runs `codex` inside the container (not on the host). Make sure the image has Codex installed, or that it’s available in the container’s login shell PATH.

By default the GUI pulls the image before each run, since re-pushing the same tag won’t update an already-cached local image.

Preflight order:

- Settings preflight runs on every environment, before environment preflight.
- Environment preflight (if enabled) runs after settings preflight.

Local storage:

- GUI state/settings: `~/.midoriai/codex-container-gui/state.json`
- Environments (one file per environment): `~/.midoriai/codex-container-gui/environment-*.json`
- Codex home mounted into the container: `~/.codex` -> `/home/midori-ai/.codex` (override with `CODEX_HOST_CODEX_DIR`)
