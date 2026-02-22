# dnd-agent-game

Rust prototype for a 6-player DnD loop:
- 1 DM agent (`codex exec`)
- 4 player agents (`codex exec`)
- 1 player (you)

It supports both local and remote Codex runs.

Turn flow is DM-directed:
- DM acts and sets `next_actor_id`
- chosen actor acts
- control returns to DM
- repeats (no fixed round-robin fallback)

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

## Identity Setup

- Player 5 identity is prompted at startup (`name`, `pronouns`).
- Players 1-4 start as `Player 1`..`Player 4`.
- Players 1-4 each propose `name` + `pronouns`.
- DM finalizes each player identity before play begins.
- Identities are saved per campaign in `identities.json`.

## Game Commands (Player)

- `/w targetplayername message` -> DM-approved whisper
- `/history` -> show your visible recent events
- `/pass` -> skip your turn
- `/quit` -> end loop
- plain text -> public in-character message

Targets accept IDs/aliases like:
- `dm`, `dm_agent`
- `player1` / `p1`
- `player2` / `p2`
- `player3` / `p3`
- `player4` / `p4`
- `player5` / `p5`

Notes:
- Plain player speech input is hidden after submit in interactive TTY mode.
- Command inputs stay visible for traceability.

## Campaign Storage

By default:
- `data/campaigns/<campaign_id>/campaign_state.json`
- `data/campaigns/<campaign_id>/events.jsonl`
- `data/campaigns/<campaign_id>/sessions/sessions.json`
- `data/campaigns/<campaign_id>/identities.json`
- `data/campaigns/<campaign_id>/notes/*.json`
- `data/campaigns/<campaign_id>/characters/*.json`

Sessions store Codex thread IDs so `resume` can continue long campaigns.
