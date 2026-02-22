# dnd-agent-game

Rust prototype for a 6-player DnD loop:
- 1 DM agent (`codex exec`)
- 4 AI player agents (`codex exec`)
- 1 human player (you)

It supports both local and remote Codex runs.

## Config Layout

The app keeps config ownership split:

- `config.toml`: app/runtime settings and local API key
- `local-config.toml`: Codex-only settings used for local runs

At first run, `config.toml` is auto-created if missing.
On local mode, `local-config.toml` is auto-created if missing, then copied into a runtime `CODEX_HOME/config.toml`.
The default local API key value is `sx-xxx` (you can change it in `config.toml`).

## Local vs Remote

### Local mode

Uses `local-config.toml` profiles:
- `dm_local` -> `openai/gpt-oss-120b` with `model_reasoning_effort = "xhigh"`
- `player_local` -> `openai/gpt-oss-20b` with `model_reasoning_effort = "xhigh"`
- `model_auto_compact_token_limit = 80000`
- `[features].enable_request_compression = false`

`OPENAI_API_KEY` is read from `config.toml` and passed to Codex as an env var.

### Remote mode

Runs standard `codex exec` behavior without local env/provider overrides.
No model or reasoning flags are forced in remote mode.

## Run

```bash
cargo run
```

Optional flags:

```bash
cargo run -- --config config.toml --campaign <campaign_id> --mode local
```

Flags are optional; the app prompts you in-program for new/continue and mode selection.

## Game Commands (Human)

- `/w targetplayername message` -> DM-approved whisper
- `/history` -> show your visible recent events
- `/pass` -> skip your turn
- `/quit` -> end loop
- plain text -> public in-character message

Targets accept IDs/aliases like:
- `dm`, `dm_agent`
- `player1` / `p1` / `ai1`
- `player2` / `p2` / `ai2`
- `player3` / `p3` / `ai3`
- `player4` / `p4` / `ai4`

## Campaign Storage

By default:
- `data/campaigns/<campaign_id>/campaign_state.json`
- `data/campaigns/<campaign_id>/events.jsonl`
- `data/campaigns/<campaign_id>/sessions/sessions.json`
- `data/campaigns/<campaign_id>/notes/*.json`
- `data/campaigns/<campaign_id>/characters/*.json`

Sessions store Codex thread IDs so `resume` can continue long campaigns.
