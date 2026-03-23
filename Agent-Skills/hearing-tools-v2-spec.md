# Midori AI Hearing v2 Specification

## 1. Purpose

This document defines the external contract for Midori AI Hearing v2.

It is intended to be the single source of truth for long-lived agent operation.
Implementations MAY change internally, but externally visible behavior MUST match this specification.

## 2. Non-Goals

This specification does not define internal implementation details such as language-specific architecture,
private module boundaries, or provider-internal behavior.

This specification does not include historical aliases or migration guidance.
The content is forward-only by design.

## 3. Normative Language

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are normative.

- MUST / MUST NOT: absolute requirement.
- SHOULD / SHOULD NOT: strong recommendation; deviations require explicit rationale.
- MAY: optional behavior.

## 4. Locked v2 Constraints

The following constraints are fixed for v2 and MUST be enforced throughout this file.

### 4.1 Command Set

The command set is exactly:

1. `init`
2. `transcribe`
3. `review`
4. `qa`
5. `voice-map`
6. `manage-voice`

### 4.2 LRM Backend

All LRM-backed behavior MUST use `opencode`.

### 4.3 Config Discovery and Bootstrap

Public CLI usage MUST NOT require a config-path argument.

Configuration path is fixed to:

`~/.midoriai/<programname>/config.toml`

If the config file is missing, the tool MUST:

1. Create `~/.midoriai/<programname>/` if needed.
2. Create `~/.midoriai/<programname>/config.toml` with defaults.
3. Continue execution using that default config.

### 4.4 Repo-Presence Sync Rule

If a repository target is configured in TOML, repo sync is ON automatically for mutating voice operations.

Sync behavior MUST follow:

`pull -> edit -> commit -> push`

No auto-sync toggle flags are used for this rule.

## 5. Terminology

- Program root: `~/.midoriai/<programname>/`
- Caller scope: artifact and cache data under the active program root (`~/.midoriai/<programname>/`).
- Input fingerprint: `sha256` hash of the input media bytes; this is the canonical input identity for lane matching.
- Requested resolution tier: CLI `--resolution` value when explicitly provided; otherwise `null`.
- Selected resolution tier: effective tier used by command logic after explicit or implicit selection.
- Managed voices: voice profiles and samples managed under the program root.
- Mutating voice operation: an operation that changes managed voice state.
- Artifact: a generated file produced by `transcribe`, `review`, or `qa` stages.

## 6. Global Invariants

- External contracts MUST be deterministic.
- Errors MUST be machine-parseable in JSON mode.
- Examples MUST remain compatible with the locked constraints in Section 4.
- This file MUST avoid historical command names and deprecated aliases.

### 6.1 Resolution Tier Contract (Speech-to-Text)

Resolution tiers for speech-to-text MUST use one normalized contract:

- `mini`
- `low`
- `mid`
- `high`

The tier mapping to Whisper/ASR model family is fixed:

| Resolution tier | Whisper/ASR model |
| --- | --- |
| `mini` | `tiny` |
| `low` | `small` |
| `mid` | `medium` |
| `high` | `large-v3` |

Contract rules:

- Default resolution for `transcribe` MUST be `mid`.
- Public flag name MUST be `--resolution`.
- No alias or shorthand flag MAY be introduced.
- `--resolution` applies to `transcribe`, `review`, and `qa`.
- `--resolution` controls speech-to-text tier selection and stage data lane selection only.
- `--resolution` MUST NOT switch LRM provider, LRM model, or LRM reasoning settings.
- Each resolution tier defines an isolated stage lane for `transcribe`, `review`, and `qa` source selection.
- For explicit `--resolution`, cross-tier fallback MUST NOT occur.
- For omitted `--resolution` in `review` and `qa`, runtime MUST perform implicit lane selection by scanning caller scope lanes for the input and selecting the highest eligible tier.
- Implicit lane selection tier ranking is fixed: `high > mid > low > mini`.
- If no eligible lane is found during implicit selection, command MUST fail with `RESOLUTION_SOURCE_MISSING`.

## 7. CLI Contract

### 7.1 Global Invocation Shape

All commands MUST be invokable as:

`<runner-uvx-cmd> <programname> <command> [flags]`

All commands MUST discover config from Section 4.3.
No command MAY require or accept a public `--config` argument.
No command MAY expose public CLI flags for LRM provider, LRM model, or LRM reasoning overrides.

### 7.2 Command: `init`

Purpose: bootstrap and validate runtime prerequisites.

Syntax:

`<runner-uvx-cmd> <programname> init [--format text|json] [--strict]`

Required flags: none.

Optional flags and defaults:

- `--format`: `text` (default), `json`.
- `--strict`: `false` (default). When true, warning-class findings fail the command.

Behavior:

- MUST create `~/.midoriai/<programname>/` if missing.
- MUST create default `~/.midoriai/<programname>/config.toml` if missing.
- MUST validate config parse and required keys.
- MUST validate required runtime dependencies and writable directories.

Example:

`<runner-uvx-cmd> <programname> init --format json`

### 7.3 Command: `transcribe`

Purpose: stage-1 extraction artifacts from media input.

Syntax:

`<runner-uvx-cmd> <programname> transcribe --input <abs-path> [--resolution mini|low|mid|high] [--max-seconds <float>] [--chunk-target-sec <float>] [--chunk-min-sec <float>] [--chunk-max-sec <float>] [--chunk-overlap-sec <float>] [--silence-threshold-db <float>] [--min-silence-sec <float>] [--gpu] [--skip-diarization] [--refresh-cache] [--format text|json]`

Required flags:

- `--input <abs-path>`

Optional flags and defaults:

- `--resolution`: `mid`
- `--max-seconds`: `0.0`
- `--chunk-target-sec`: `60.0`
- `--chunk-min-sec`: `15.0`
- `--chunk-max-sec`: `90.0`
- `--chunk-overlap-sec`: `1.0`
- `--silence-threshold-db`: `-38.0`
- `--min-silence-sec`: `0.5`
- `--gpu`: `false`
- `--skip-diarization`: `false`
- `--refresh-cache`: `false`
- `--format`: `json`

Behavior:

- MUST treat `--resolution` as an explicit stage lane key.
- MUST write extraction artifacts tagged with the requested `resolution_tier` and resolved ASR model.

Example:

`<runner-uvx-cmd> <programname> transcribe --input /abs/audio.m4a --gpu --format json`

### 7.4 Command: `review`

Purpose: stage-2 cleanup/review from extraction artifacts.

Syntax:

`<runner-uvx-cmd> <programname> review --input <abs-path> [--resolution mini|low|mid|high] [--format markdown|json]`

Required flags:

- `--input <abs-path>`

Optional flags and defaults:

- `--resolution`: omitted (implicit lane selection)
- `--format`: `markdown`

Behavior:

- MUST require prior extraction artifacts for the same input/config state.
- When `--resolution` is provided, MUST require prior extraction artifacts for the requested lane and MUST NOT fall back to other tiers.
- When `--resolution` is omitted, MUST scan caller scope lanes for the input, rank tiers `high > mid > low > mini`, and select the highest eligible lane.
- When `--resolution` is omitted and no eligible lane is found, MUST fail with `RESOLUTION_SOURCE_MISSING`.
- Failure message for missing lane data MUST instruct operator to rerun `transcribe --resolution <tier>`.
- MUST run LRM-backed cleanup via `opencode`.

Example:

`<runner-uvx-cmd> <programname> review --input /abs/audio.m4a --format json`

### 7.5 Command: `qa`

Purpose: stage-3 question answering over prepared artifacts.

Syntax:

`<runner-uvx-cmd> <programname> qa --input <abs-path> --question <text> [--resolution mini|low|mid|high] [--source auto|review|artifacts] [--format answer|json]`

Required flags:

- `--input <abs-path>`
- `--question <text>`

Optional flags and defaults:

- `--resolution`: omitted (implicit lane selection)
- `--source`: `auto`
- `--format`: `answer`

Source behavior:

- `auto` with explicit `--resolution`: use review source for requested lane when available; otherwise use extraction artifacts for requested lane; fail if neither exists for requested lane.
- `auto` with omitted `--resolution`: evaluate tiers in fixed rank order `high > mid > low > mini`; for each tier, prefer review source then artifacts source; choose first eligible tier; fail if none exists.
- `review`: require review artifact for selected lane; fail if missing.
- `artifacts`: require extraction artifact for selected lane; fail if missing.

Behavior:

- With explicit `--resolution`, MUST resolve sources within the requested lane only.
- With explicit `--resolution`, MUST NOT fall back to sources from any other tier.
- With omitted `--resolution`, MUST perform implicit lane selection using caller scope lane scan and fixed ranking.
- MUST fail with `RESOLUTION_SOURCE_MISSING` when selected resolution tier data is absent, and the error message MUST instruct operator to rerun `transcribe --resolution <tier>`.
- In `qa --source auto` with omitted `--resolution`, successful implicit lane selection MUST emit `IMPLICIT_RESOLUTION_SELECTED` in top-level `warnings[]`.
- MUST fail with `RESOLUTION_ARTIFACT_MISMATCH` when located artifacts are present but tagged with a different resolution tier.
- MUST run LRM-backed answer synthesis via `opencode`.

Example:

`<runner-uvx-cmd> <programname> qa --input /abs/audio.m4a --question "What happened?" --source auto`

### 7.6 Command: `voice-map`

Purpose: maintain misspelling/alias mapping for speaker and character normalization.

Syntax:

`<runner-uvx-cmd> <programname> voice-map <action> [flags]`

Actions:

- `add-human --speaker <slug-or-name> --variant <text>`
- `remove-human --speaker <slug-or-name> --variant <text>`
- `add-character --speaker <slug-or-name> --character <name> --variant <text>`
- `remove-character --speaker <slug-or-name> --character <name> --variant <text>`
- `list [--speaker <slug-or-name>]`

Defaults:

- `list` without `--speaker` returns all configured mappings.

Example:

`<runner-uvx-cmd> <programname> voice-map add-character --speaker henry --character sigi --variant "Siggy"`

### 7.7 Command: `manage-voice`

Purpose: manage speaker profiles and sample lifecycle under managed storage.

Syntax:

`<runner-uvx-cmd> <programname> manage-voice <action> [flags]`

Lifecycle actions:

- `capture --speaker <slug> [--seconds <int>] [--device <name>] [--sample-rate <int>]`
- `add --speaker <slug> --file <abs-path>`
- `remove --speaker <slug> --sample-id <id>`
- `list [--speaker <slug>]`
- `ensure-profile --speaker <slug> --display-name <text>`

Defaults:

- `capture --seconds`: `10`
- `capture --sample-rate`: `16000`
- `list` without `--speaker` returns all profiles and sample summaries.

Repo sync behavior for mutating actions (`capture`, `add`, `remove`, `ensure-profile`):

- If repo is configured in TOML, sync MUST run as `pull -> edit -> commit -> push`.
- If repo is not configured, operation MUST remain local-only.

Example:

`<runner-uvx-cmd> <programname> manage-voice add --speaker henry --file /abs/speaker.wav`

## 8. Configuration and Managed Storage Contract

### 8.1 Fixed Config Path and Discovery

The config file path is fixed and MUST be resolved as:

`~/.midoriai/<programname>/config.toml`

Rules:

- The CLI MUST NOT expose a public config-path argument.
- The runtime MUST NOT require environment variables for configuration fallback.
- Tilde-prefixed paths MUST resolve against the current user home directory.

### 8.2 Bootstrap Behavior When Config Is Missing

Before executing command logic, the tool MUST bootstrap config state:

1. Ensure `~/.midoriai/<programname>/` exists.
2. Ensure `~/.midoriai/<programname>/config.toml` exists.
3. If missing, write a default TOML and continue execution.

Bootstrap MUST be idempotent and safe to run repeatedly.

### 8.3 Default TOML Example

The generated default file SHOULD follow this baseline structure:

```toml
schema_version = "1"

[runtime]
default_output_format = "json"  # json | text | markdown | answer
strict_init = false

[lrm]
provider = "opencode"
review_model = "openai/gpt-oss-20b"
qa_model = "openai/gpt-oss-120b"
review_reasoning_target = "high"
qa_reasoning_target = "high"
allow_xhigh_if_supported = true
review_timeout_sec = 20000
qa_timeout_sec = 20000

[transcribe_defaults]
resolution_tier = "mid"  # mini | low | mid | high
max_seconds = 0.0
chunk_target_sec = 60.0
chunk_min_sec = 15.0
chunk_max_sec = 90.0
chunk_overlap_sec = 1.0
silence_threshold_db = -38.0
min_silence_sec = 0.5
gpu = false
skip_diarization = false
refresh_cache = false

[paths]
root_dir = "~/.midoriai/<programname>"
cache_dir = "~/.midoriai/<programname>/cache"
artifacts_dir = "~/.midoriai/<programname>/artifacts"
logs_dir = "~/.midoriai/<programname>/logs"
voices_dir = "~/.midoriai/<programname>/voices"

[voices]
profiles_dir = "~/.midoriai/<programname>/voices/profiles"
default_sample_rate_hz = 16000
default_capture_seconds = 10

[voice_repo]
remote_url = "https://github.com/<org>/<voices-repo>.git"
repo_path = "~/.midoriai/<programname>/voices"
branch = "main"
commit_name = "Midori AI Hearing Bot"
commit_email = "midoriai-hearing@local"
commit_prefix = "[manage-voice]"
```

### 8.3.1 LRM Policy Is Config-Driven

LRM behavior MUST be configured only from TOML.

Rules:

- CLI flags MUST NOT override LRM provider, model, timeout, or reasoning policy.
- Reasoning target for review and qa is `high`.
- Runtime MAY use `xhigh` only when backend capability check confirms support.
- If backend does not support `xhigh`, runtime MUST stay at `high`.

### 8.4 Repo Presence Enables Sync

Repo sync is enabled by configuration presence, not toggle flags.

A repo is considered configured when either condition is true:

- `voice_repo.remote_url` is non-empty.
- `voice_repo.repo_path` is non-empty and points to a git working tree.

Auto-clone rule:

- If `voice_repo.remote_url` is configured and local repo is missing, runtime MUST auto-clone into:
  - `~/.midoriai/<programname>/voices/`
- After auto-clone, mutating `manage-voice` actions MUST use the existing sync flow:
  - `pull -> edit -> commit -> push`

When configured, mutating `manage-voice` actions MUST execute:

`pull -> edit -> commit -> push`

No `auto_*` sync toggle fields are used in v2.

### 8.5 Canonical Managed Storage Layout

All managed files MUST live under `~/.midoriai/<programname>/`.

Canonical contracts:

- Config:
  - `~/.midoriai/<programname>/config.toml`
- Logs:
  - `~/.midoriai/<programname>/logs/<command>-<run_id>.log`
- Cache snapshots:
  - `~/.midoriai/<programname>/cache/<cache_key>/extraction.json`
- Run artifacts:
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/pipeline.json`
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/meta.json`
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/cleaned.md`
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/review.json`
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/qa.txt`
  - `~/.midoriai/<programname>/artifacts/runs/<run_id>/error.json`
- Voice profiles and samples:
  - `~/.midoriai/<programname>/voices/profiles/<speaker_slug>/profile.toml`
  - `~/.midoriai/<programname>/voices/profiles/<speaker_slug>/samples/<sample_id>.wav`
  - `~/.midoriai/<programname>/voices/.git` (when `voice_repo.remote_url` is configured)

### 8.6 Write and Sync Failure Guarantees

Failure behavior MUST be explicit:

- If `pull` fails before edits, the mutating command MUST fail without partial writes.
- If commit/push fails after local edit, local state MUST remain intact.
- Sync failures MUST be surfaced in command output and logs; they MUST NOT be silent.

## 9. Output, Error, and Artifact Contracts

### 9.1 Output Modes

All commands MUST support machine-facing JSON output.

Supported mode behavior:

- `json`: structured payload following Sections 9.2 and 9.3.
- `text`: concise human-readable summary with identical success/failure outcome.
- `markdown`: reserved for transcript-like outputs where applicable (`review` and optional transcript views).
- `answer`: reserved for `qa` answer-first output.

Text/markdown/answer modes MUST NOT change success/failure semantics relative to JSON mode.

### 9.2 Success JSON Envelope

Successful command responses MUST return:

```json
{
  "ok": true,
  "command": "init",
  "meta": {
    "schema_version": "1.0",
    "run_id": "abc123def456",
    "timestamp_unix": 1760000000
  },
  "result": {},
  "artifacts": {},
  "warnings": []
}
```

Contract rules:

- `ok` MUST be `true`.
- `command` MUST match executed command name.
- `meta.schema_version` MUST be present.
- `meta.run_id` MUST be present for commands that create logs or artifacts.
- `result` MUST be an object (empty object allowed).
- `artifacts` MUST be an object (empty object allowed).
- `warnings` MUST be an array (empty array allowed).

### 9.3 Error JSON Envelope

Failed command responses MUST return:

```json
{
  "ok": false,
  "command": "qa",
  "meta": {
    "schema_version": "1.0",
    "run_id": "abc123def456",
    "timestamp_unix": 1760000000
  },
  "error": {
    "code": "RESOLUTION_SOURCE_MISSING",
    "message": "No review or extraction source found for requested resolution tier.",
    "details": {}
  },
  "warnings": []
}
```

Contract rules:

- `ok` MUST be `false`.
- `error.code` MUST be stable and machine-parseable.
- `error.message` MUST be human-readable and actionable.
- `error.details` MUST be an object (empty object allowed).
- `warnings` MUST still be returned for non-fatal side findings.

### 9.4 Exit Code Policy

Process exit codes MUST be deterministic:

- `0`: success.
- `1`: command executed but failed domain/runtime checks.
- `2`: usage/validation error (invalid flags, invalid argument shape, unsupported mode).

### 9.5 Command-Specific Output Expectations

Each command MUST expose the following minimum result/artifact expectations:

- `init`:
  - `result.checks`: array of dependency/path/config checks.
  - `result.bootstrap_created`: boolean for default config creation on this run.
  - `artifacts.config_path`: fixed config path.
- `transcribe`:
  - `result.chunk_count`, `result.duration_sec`, `result.cache_key`.
  - `result.resolution_tier`, `result.asr_model`.
  - `artifacts.extraction_json`, `artifacts.pipeline_json`, `artifacts.meta_json`.
- `review`:
  - `result.segment_count`, `result.cleanup_failures`.
  - `result.resolution_tier`.
  - `result.resolution_selection_mode` (`explicit` or `implicit`).
  - `result.requested_resolution_tier` (tier value when explicit, else `null`).
  - `result.selected_resolution_tier` (always populated).
  - `result.input_fingerprint`.
  - `artifacts.review_json`, `artifacts.cleaned_markdown`, `artifacts.pipeline_json`.
- `qa`:
  - `result.answer`, `result.confidence`, `result.source`.
  - `result.resolution_tier`.
  - `result.resolution_selection_mode` (`explicit` or `implicit`).
  - `result.requested_resolution_tier` (tier value when explicit, else `null`).
  - `result.selected_resolution_tier` (always populated).
  - `result.input_fingerprint`.
  - `artifacts.qa_text` when persisted by output policy.
- `voice-map`:
  - `result.updated`: boolean.
  - `result.reason`: stable update reason (`added`, `removed`, `already_present`, or command-specific equivalent).
- `manage-voice`:
  - `result.speaker`, `result.action`, `result.updated`.
  - `result.repo_sync`: object with `enabled`, `attempted`, `pull_ok`, `commit_ok`, `push_ok`.

### 9.5.1 Implicit Resolution Warning Contract

When `review` or `qa` runs with omitted `--resolution` and implicit selection succeeds, warning data MUST appear in top-level `warnings[]`.

Required warning entry:

- `code`: `IMPLICIT_RESOLUTION_SELECTED`
- `message`: human-readable statement that implicit tier selection was applied
- `details` object with:
  - `command`: `review` or `qa`
  - `input_fingerprint`: canonical input identity
  - `requested_resolution_tier`: `null`
  - `selected_resolution_tier`: selected tier value
  - `candidate_tier_order`: `["high","mid","low","mini"]`
  - `selected_source`: `review` or `artifacts` for `qa`; `artifacts` for `review`

Only one `IMPLICIT_RESOLUTION_SELECTED` warning entry MAY be emitted per command run.

### 9.6 QA Source Prerequisite Errors

`qa --source` behavior MUST enforce deterministic prerequisite checks:

- `--source auto` with explicit `--resolution`:
  - MUST prefer review source in requested lane.
  - MUST fallback to extraction artifacts only in requested lane.
  - MUST fail with `RESOLUTION_SOURCE_MISSING` when neither source exists for requested lane.
- `--source auto` with omitted `--resolution`:
  - MUST evaluate tiers in fixed rank order `high > mid > low > mini`.
  - MUST apply tier-first tie-break, and within each tier prefer review source then artifacts source.
  - When multiple same-tier candidates exist for a source type, MUST select deterministically by:
    1. `meta.timestamp_unix` descending (most recent complete candidate),
    2. then `meta.run_id` lexical ascending as stable tie-break.
  - A candidate is usable only when required metadata and required source fields are present and parseable.
  - If same-tier review candidate is malformed or unusable but same-tier artifacts candidate is usable, MUST use same-tier artifacts candidate and continue.
  - MUST emit `IMPLICIT_RESOLUTION_SELECTED` in top-level `warnings[]` when implicit lane selection succeeds.
  - MUST fail with `RESOLUTION_SOURCE_MISSING` when no eligible source exists across all tiers.
- `--source review`:
  - MUST fail with `RESOLUTION_SOURCE_MISSING` when review artifact for selected resolution tier is absent.
  - MUST fail with `RESOLUTION_SOURCE_MISSING` when extraction cache for selected resolution tier is absent.
- `--source artifacts`:
  - MUST fail with `RESOLUTION_SOURCE_MISSING` when extraction cache for selected resolution tier is absent.

`qa` MUST NOT use cross-tier source fallback when explicit `--resolution` is provided.

### 9.7 Artifact Path Contract

Artifact paths emitted in output payloads MUST match canonical layout from Section 8.5.

Rules:

- Returned artifact paths MUST be absolute.
- Missing optional artifacts MUST be returned as empty string, not omitted.
- When a command does not produce artifacts, `artifacts` MUST still be returned as an object.

### 9.8 Resolution-Specific Error Codes

Resolution-aware commands MUST use stable resolution error codes.

Required codes:

- `RESOLUTION_INVALID`:
  - Applies to `transcribe`, `review`, and `qa` when provided `--resolution` is not in allowed set (`mini|low|mid|high`).
  - SHOULD return exit code `2` (usage/validation).
- `RESOLUTION_SOURCE_MISSING`:
  - Applies to explicit mode when requested resolution tier artifacts are absent.
  - Applies to implicit mode when no eligible candidate exists in caller scope for the input.
  - Error message MUST instruct operator to rerun `transcribe --resolution <tier>`.
- `RESOLUTION_ARTIFACT_MISMATCH`:
  - Applies to `review` and `qa` when located artifacts are tagged with a different resolution tier than selected resolution tier.
  - In `review`, applies when the located extraction artifact lane metadata does not equal selected resolution tier.
  - In `qa --source review`, applies when review artifact metadata does not equal selected resolution tier.
  - In `qa --source artifacts`, applies when extraction artifact metadata does not equal selected resolution tier.
  - In `qa --source auto`, applies when only cross-tier candidates are found and no same-tier candidate exists.
  - Error details MUST include `requested_resolution_tier`, `selected_resolution_tier`, and `artifact_resolution_tier`.
  - In implicit mode, `requested_resolution_tier` MUST be `null`.
  - Error details SHOULD include `artifact_path` when a mismatched artifact was found.

### 9.9 Resolution Metadata Persistence Contract

Resolution metadata MUST be persisted in deterministic locations in cache and run artifacts.

Required location and key contract:

- Cache extraction snapshot:
  - Path: `~/.midoriai/<programname>/cache/<cache_key>/extraction.json`
  - Keys: `meta.input_fingerprint`, `meta.resolution_tier`, `meta.asr_model`
- Run metadata:
  - Path: `~/.midoriai/<programname>/artifacts/runs/<run_id>/meta.json`
  - Keys: `input_fingerprint`, `resolution_tier`, `asr_model`
- Pipeline summary:
  - Path: `~/.midoriai/<programname>/artifacts/runs/<run_id>/pipeline.json`
  - Keys: `meta.input_fingerprint`, `meta.resolution_tier`, `meta.asr_model`
- Review output:
  - Path: `~/.midoriai/<programname>/artifacts/runs/<run_id>/review.json`
  - Keys: `meta.input_fingerprint`, `meta.resolution_tier`

Contract rules:

- Metadata keys and values MUST be stable and machine-parseable.
- `resolution_tier` MUST be one of `mini|low|mid|high`.
- Persisted `resolution_tier` MUST match explicit `--resolution` when provided, or match implicitly selected tier when resolution is omitted.
- `input_fingerprint` MUST be the canonical identity key for same-input matching.
- Omitted-resolution lane scan MUST consider candidates only from caller scope under `~/.midoriai/<programname>/`.
- Candidate eligibility for omitted-resolution scan MUST require matching `input_fingerprint` and valid `resolution_tier` metadata.
- Candidates with missing, malformed, or partial required metadata MUST be ignored during omitted-resolution scan.
- If multiple usable candidates exist in the same tier for the same source type, runtime MUST apply deterministic same-tier candidate ordering from Section 9.6.
- If all candidates are ignored or ineligible, command MUST fail with `RESOLUTION_SOURCE_MISSING`.
- Reads for `review` and `qa` MUST validate persisted `resolution_tier` before processing stage logic.
- If persisted metadata is missing or malformed, command MUST fail with `RESOLUTION_ARTIFACT_MISMATCH`.

## 10. Stage and Source Behavior Contract

### 10.1 Stage Order and Prerequisites

The stage order is deterministic:

1. `init`
2. `transcribe`
3. `review`
4. `qa`

Contract rules:

- `transcribe` MUST produce extraction artifacts keyed by cache inputs and requested resolution tier.
- `review` with explicit `--resolution` MUST read extraction artifacts only from requested lane.
- `review` with omitted `--resolution` MUST select highest eligible lane via caller scope scan, fixed ranking, and input fingerprint matching.
- `qa` with explicit `--resolution` MUST read stage artifacts only from requested lane.
- `qa` with omitted `--resolution` MUST select highest eligible lane via caller scope scan, fixed ranking, and input fingerprint matching.
- `qa` MUST NOT trigger extraction or review side effects.
- `review` and `qa` MUST NOT use cross-tier fallback when explicit `--resolution` is provided.
- `voice-map` and `manage-voice` MAY run independently of stage order.

### 10.2 Source Selection Behavior for `qa`

`qa` MUST apply source policy deterministically:

- `--source auto` with explicit `--resolution`: prefer review in requested lane, else fallback to artifacts in requested lane, else fail.
- `--source auto` with omitted `--resolution`: evaluate lanes in tier order `high > mid > low > mini`, with tier-first tie-break and review-before-artifacts within each tier.
- `--source auto`: if same-tier review is malformed/unusable and same-tier artifacts is usable, fallback MUST stay in the same tier before evaluating lower tiers.
- `--source auto`: same-tier candidate choice MUST follow deterministic ordering defined in Section 9.6.
- `--source auto` with omitted `--resolution`: when implicit lane selection succeeds, emit `IMPLICIT_RESOLUTION_SELECTED` in top-level `warnings[]`.
- `--source review`: require review and cache prerequisites in selected resolution tier.
- `--source artifacts`: require cache prerequisite in selected resolution tier.

When source checks fail, response MUST use stable error codes from Section 9, including `RESOLUTION_SOURCE_MISSING` and `RESOLUTION_ARTIFACT_MISMATCH`.

### 10.3 Operational Contract for Implementers

This section is implementation-agnostic but decision-complete. Future agents MUST be able to implement behavior without external skill code access.

Required runtime dependencies (validated by `init`):

- Speech media toolchain:
  - `ffmpeg`
  - `ffprobe`
- LRM execution backend:
  - `opencode` runtime reachable by the local execution environment
- Voice and repo operations:
  - `git` (required when repo sync is configured)
- Filesystem:
  - Read/write access under `~/.midoriai/<programname>/`

Stage responsibilities and side-effect boundaries:

- `init`:
  - Responsible for bootstrap and dependency/config validation.
  - MUST NOT generate stage artifacts (`extraction.json`, `review.json`, `qa.txt`).
- `transcribe`:
  - Responsible for speech-to-text extraction and lane-tagged cache generation.
  - MUST NOT run review cleanup or final QA synthesis.
- `review`:
  - Responsible for cleanup and review artifacts from existing extraction lane only.
  - MUST NOT perform implicit transcription side effects.
- `qa`:
  - Responsible for answering from existing lane-scoped artifacts.
  - MUST NOT trigger transcription or review generation.
- `voice-map`:
  - Responsible for normalization map maintenance only.
  - MUST NOT mutate stage artifacts directly.
- `manage-voice`:
  - Responsible for profile/sample lifecycle and optional configured repo sync.
  - MUST NOT mutate unrelated stage outputs.

Artifact expectations by stage:

- `transcribe` MUST emit lane-tagged extraction and run metadata artifacts:
  - `cache/<cache_key>/extraction.json`
  - `artifacts/runs/<run_id>/pipeline.json`
  - `artifacts/runs/<run_id>/meta.json`
- `review` MUST emit review outputs in run artifacts:
  - `artifacts/runs/<run_id>/review.json`
  - `artifacts/runs/<run_id>/cleaned.md`
- `qa` SHOULD emit `artifacts/runs/<run_id>/qa.txt` when output policy persists answer text.
- Missing required stage artifacts MUST fail deterministically with machine-parseable errors.

Known-speaker and `voice-map` normalization relationship:

- Voice profiles/samples from `manage-voice` provide speaker enrollment data.
- `voice-map` provides deterministic text-level misspelling and alias normalization.
- `transcribe`, `review`, and `qa` normalization behavior MUST apply both data sources when available.
- Changes to `voice-map` or voice profiles SHOULD affect subsequent runs; they MUST NOT silently rewrite previously persisted artifacts.

Common failure and recovery guidance:

- Missing runtime dependency:
  - `init` MUST fail with actionable dependency diagnostics.
  - Recovery: install missing dependency, rerun `init`.
- Missing lane artifacts for `review`/`qa`:
  - MUST fail with `RESOLUTION_SOURCE_MISSING`.
  - Recovery: run `transcribe --resolution <tier>` then rerun stage.
- Lane metadata mismatch:
  - MUST fail with `RESOLUTION_ARTIFACT_MISMATCH`.
  - Recovery: rerun `transcribe --resolution <tier>` and dependent stages in same tier.
- LRM backend capability limit:
  - MUST keep reasoning at `high` when `xhigh` is unsupported.
  - Recovery: no operator action required unless backend connectivity fails.

## 11. Runbooks and Operator Playbooks

### 11.1 First-Run Workflow

First run on a new machine MUST follow this sequence:

1. Run `init`.
2. Confirm bootstrap created `~/.midoriai/<programname>/config.toml`.
3. Validate dependency checks returned by `init`.
4. Run `transcribe` on a known input file.
5. Run `review`.
6. Run `qa --source auto`.

### 11.2 Normal Session Workflow

Standard operation SHOULD follow:

1. `init` (health check before work)
2. `transcribe`
3. `review`
4. `qa`

Voice operations MAY be performed at any time with `manage-voice` and `voice-map`.

When `voice_repo.remote_url` is configured and local repo is missing, the first mutating `manage-voice` operation MUST auto-clone to `~/.midoriai/<programname>/voices/` before applying sync flow.

### 11.3 Failure Diagnostics Playbook

Operator response MUST be deterministic for common failures:

- Missing config: rerun `init`; bootstrap MUST create defaults and continue.
- Invalid config TOML (parse/type/required key failure): `init` MUST fail with actionable key/path diagnostics; recovery is to fix TOML and rerun `init`.
- Missing review source for `qa --source review` in requested lane: rerun `transcribe --resolution <tier>`, then run `review --resolution <tier>`.
- Missing cache source for `qa --source artifacts` in requested lane: rerun `transcribe --resolution <tier>`.
- Lane metadata mismatch (`RESOLUTION_ARTIFACT_MISMATCH`) in `review` or `qa`: rerun `transcribe --resolution <tier>` and rerun dependent stage using same `--resolution`.
- Dependency validation failure in `init`: fix reported dependency/path issue, then rerun `init`.

### 11.4 Repo-Sync Failure Handling (`manage-voice`)

When repo is configured and sync is active (`pull -> edit -> commit -> push`):

- Pull failure before edit MUST fail the command without partial write.
- Commit or push failure after edit MUST preserve local managed voice changes.
- Sync failure MUST be surfaced in command output and log artifacts.
- Recovery SHOULD be: resolve git issue, rerun same `manage-voice` action, verify `result.repo_sync` status.

Auto-clone failure behavior:

- If required auto-clone fails, mutating `manage-voice` command MUST fail before edit.
- Auto-clone failure MUST be surfaced in command output and logs with actionable clone diagnostics.
- Recovery SHOULD be: fix network/auth/repo URL issue, rerun the same mutating action.

## 12. Validation and Acceptance Criteria

### 12.1 Contract Integrity Checks

The specification is acceptable only if all checks pass:

- Command set is exactly `init`, `transcribe`, `review`, `qa`, `voice-map`, `manage-voice`.
- LRM references are `opencode` only.
- No command accepts a public `--config` argument.
- Config path appears only as `~/.midoriai/<programname>/config.toml`.
- Repo-presence sync rule is documented as automatic with no auto-toggle fields.
- Auto-clone rule is documented: configured `voice_repo.remote_url` plus missing local repo MUST clone to `~/.midoriai/<programname>/voices/`.

### 12.2 Scenario Acceptance Checks

The following scenarios MUST be fully covered in examples or runbooks:

- First run with missing config bootstrap.
- End-to-end stage flow (`init` to `qa`).
- `qa` prerequisite failures for each source mode.
- `manage-voice` repo-sync failure and recovery behavior.
- `manage-voice` auto-clone behavior:
  - When `voice_repo.remote_url` is configured and local repo is missing, first mutating action MUST clone into `~/.midoriai/<programname>/voices/`.
  - After clone, mutating action MUST proceed using `pull -> edit -> commit -> push`.
  - If clone fails, command MUST fail before edit with actionable diagnostics.
- Resolution lane isolation:
  - For same input, each tier (`mini|low|mid|high`) MUST produce a distinct lane with matching persisted `resolution_tier`.
  - Cross-tier reads MUST NOT succeed.
- Cross-stage same-tier success:
  - `transcribe --resolution <tier>` then `review --resolution <tier>` then `qa --resolution <tier>` MUST succeed for each tier.
- Cross-tier mismatch failures:
  - Running `review` or `qa` with a requested tier that does not match located artifact metadata MUST fail with `RESOLUTION_ARTIFACT_MISMATCH`.
- QA source matrix per resolution:
  - For each tier, `qa --source auto|review|artifacts` MUST follow deterministic lane-scoped selection and failure rules.
  - When multiple same-tier candidates exist, selection MUST use deterministic ordering (`timestamp_unix` desc, then `run_id` asc).
  - For `qa --source auto`, when same-tier review is malformed/unusable and same-tier artifacts is usable, same-tier artifacts fallback MUST occur before considering lower tiers.
  - Implicit resolution selection MUST emit exactly one `IMPLICIT_RESOLUTION_SELECTED` warning entry.
- Config bootstrap and invalid-config behavior:
  - Missing config MUST bootstrap and continue.
  - Invalid TOML or missing required keys MUST fail deterministically until corrected.
- LRM high to xhigh capability fallback:
  - With `allow_xhigh_if_supported = true`, runtime MUST use `xhigh` only when capability confirms support.
  - If unsupported, runtime MUST stay at `high` and continue without failure.

### 12.3 Naming and Language Quality Checks

- Single-word brand-token usage is disallowed in this file.
- Allowed brand naming is `Midori AI` or `midoriai`.
- Legacy aliases and migration references MUST NOT appear.

### 12.4 Requirement Trace (Quick Self-Validation)

Use this checklist before accepting spec edits:

- [ ] Command set remains exactly: `init`, `transcribe`, `review`, `qa`, `voice-map`, `manage-voice`.
- [ ] All LRM references remain `opencode` only.
- [ ] Public CLI still rejects/omits `--config`.
- [ ] Fixed config path remains `~/.midoriai/<programname>/config.toml`.
- [ ] Missing config behavior still says: create defaults, then continue.
- [ ] Repo presence still means sync ON for mutating `manage-voice` actions.
- [ ] Sync sequence text remains exactly `pull -> edit -> commit -> push`.
- [ ] Auto-clone contract is explicit: configured `voice_repo.remote_url` + missing local repo clones to `~/.midoriai/<programname>/voices/` before mutating sync.
- [ ] Resolution metadata location contract is explicit and deterministic in cache and run artifacts.
- [ ] `RESOLUTION_ARTIFACT_MISMATCH` applicability is explicit for `review` and all `qa --source` modes.
- [ ] Acceptance scenarios include lane isolation, cross-tier mismatch, qa source matrix, config invalid cases, and LRM high to xhigh fallback.
- [ ] Same-tier candidate tie-break rule is explicit and testable.
- [ ] `qa --source auto` same-tier malformed-review fallback behavior is explicit and testable.
- [ ] Brand naming remains `Midori AI` or `midoriai` only.
