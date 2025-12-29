Run the GUI:

`uv run main.py`

It starts a Docker container using `lunamidori5/pixelarch:emerald` and runs:

`codex exec --sandbox danger-full-access <your prompt>`

Interactive mode:

- Click `New task (interactive)` to launch a real TTY session in your installed terminal emulator (Linux/macOS).
- It runs the container with `docker run -it …` and (by default) starts `codex --sandbox danger-full-access` (no `exec` and no prompt), so you can use agent TUIs.
- You can change the “Container command” field to run something else (e.g. `bash`, `claude`, `gh …`) as long as it exists inside the image.

If you see `executable file not found in $PATH` for `codex`, the GUI runs `codex` inside the container (not on the host). Make sure the image has Codex installed, or that it’s available in the container’s login shell PATH.

By default the GUI pulls the image before each run, since re-pushing the same tag won’t update an already-cached local image.

Preflight order:

- Settings preflight runs on every environment, before environment preflight.
- Environment preflight (if enabled) runs after settings preflight.

Local storage:

- GUI state/settings: `~/.midoriai/codex-container-gui/state.json`
- Environments (one file per environment): `~/.midoriai/codex-container-gui/environment-*.json`
- Codex home mounted into the container: `~/.codex` -> `/home/midori-ai/.codex` (override with `CODEX_HOST_CODEX_DIR`)
