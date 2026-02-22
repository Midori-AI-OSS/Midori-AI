use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, anyhow, bail};
use chrono::Utc;
use serde_json::Value;

use crate::config::{AppConfig, ResolvedPaths};
use crate::types::{DM_ACTOR, PLAYER_AI_ACTORS, RunMode};

#[derive(Debug, Clone)]
pub struct CodexTurnResult {
    pub thread_id: Option<String>,
    pub last_message: String,
    pub reasoning_text: Vec<String>,
    pub errors: Vec<String>,
    pub raw_events: Vec<Value>,
}

#[derive(Debug)]
pub struct CodexRunner {
    mode: RunMode,
    app_config: AppConfig,
    workdir: PathBuf,
    output_dir: PathBuf,
    local_runtime_home: Option<PathBuf>,
    dm_turn_schema_path: PathBuf,
    player_turn_schema_path: PathBuf,
    whisper_schema_path: PathBuf,
    identity_proposal_schema_path: PathBuf,
    identity_decision_schema_path: PathBuf,
}

impl CodexRunner {
    pub fn new(
        mode: RunMode,
        app_config: AppConfig,
        paths: ResolvedPaths,
        workdir: PathBuf,
    ) -> Result<Self> {
        fs::create_dir_all(&paths.schema_dir)
            .with_context(|| format!("failed to create {}", paths.schema_dir.display()))?;

        let output_dir = paths.app_root.join(".runtime/codex-output");
        fs::create_dir_all(&output_dir)
            .with_context(|| format!("failed to create {}", output_dir.display()))?;

        let dm_turn_schema_path = paths.schema_dir.join("dm_turn.schema.json");
        let player_turn_schema_path = paths.schema_dir.join("player_turn.schema.json");
        let whisper_schema_path = paths.schema_dir.join("dm_whisper_decision.schema.json");
        let identity_proposal_schema_path = paths.schema_dir.join("identity_proposal.schema.json");
        let identity_decision_schema_path = paths.schema_dir.join("identity_decision.schema.json");
        ensure_schema_files(
            &dm_turn_schema_path,
            &player_turn_schema_path,
            &whisper_schema_path,
            &identity_proposal_schema_path,
            &identity_decision_schema_path,
        )?;

        let local_runtime_home = if mode == RunMode::Local {
            ensure_local_codex_template(&paths.codex_local_config)?;
            materialize_codex_home(&paths.codex_local_config, &paths.codex_runtime_home)?;
            Some(paths.codex_runtime_home.clone())
        } else {
            None
        };

        Ok(Self {
            mode,
            app_config,
            workdir,
            output_dir,
            local_runtime_home,
            dm_turn_schema_path,
            player_turn_schema_path,
            whisper_schema_path,
            identity_proposal_schema_path,
            identity_decision_schema_path,
        })
    }

    pub fn mode(&self) -> RunMode {
        self.mode
    }

    pub fn run_actor_turn(
        &self,
        actor_id: &str,
        prompt: &str,
        existing_thread_id: Option<&str>,
    ) -> Result<CodexTurnResult> {
        let profile = self.select_profile(actor_id);
        let schema = if actor_id == DM_ACTOR {
            &self.dm_turn_schema_path
        } else {
            &self.player_turn_schema_path
        };
        self.run_codex(profile, prompt, existing_thread_id, Some(schema))
    }

    pub fn run_dm_whisper_approval(
        &self,
        prompt: &str,
        existing_thread_id: Option<&str>,
    ) -> Result<CodexTurnResult> {
        let profile = self.select_profile(DM_ACTOR);
        self.run_codex(
            profile,
            prompt,
            existing_thread_id,
            Some(&self.whisper_schema_path),
        )
    }

    pub fn run_identity_proposal(
        &self,
        actor_id: &str,
        prompt: &str,
        existing_thread_id: Option<&str>,
    ) -> Result<CodexTurnResult> {
        let profile = self.select_profile(actor_id);
        self.run_codex(
            profile,
            prompt,
            existing_thread_id,
            Some(&self.identity_proposal_schema_path),
        )
    }

    pub fn run_identity_decision(
        &self,
        prompt: &str,
        existing_thread_id: Option<&str>,
    ) -> Result<CodexTurnResult> {
        let profile = self.select_profile(DM_ACTOR);
        self.run_codex(
            profile,
            prompt,
            existing_thread_id,
            Some(&self.identity_decision_schema_path),
        )
    }

    fn select_profile(&self, actor_id: &str) -> Option<&'static str> {
        if self.mode == RunMode::Remote {
            return None;
        }
        if actor_id == DM_ACTOR {
            Some("dm_local")
        } else if PLAYER_AI_ACTORS.contains(&actor_id) {
            Some("player_local")
        } else {
            None
        }
    }

    fn run_codex(
        &self,
        profile: Option<&str>,
        prompt: &str,
        existing_thread_id: Option<&str>,
        schema_path: Option<&Path>,
    ) -> Result<CodexTurnResult> {
        let ts = Utc::now().timestamp_millis();
        let output_message_path = self.output_dir.join(format!("last-message-{}.txt", ts));

        let mut cmd = Command::new("codex");
        cmd.current_dir(&self.workdir);

        if self.mode == RunMode::Local {
            let api_key = self.app_config.secrets.local_openai_api_key.trim();
            if api_key.is_empty() {
                bail!("config.toml secret local_openai_api_key must not be empty for local mode");
            }

            cmd.env("OPENAI_API_KEY", api_key);
            let Some(home) = &self.local_runtime_home else {
                return Err(anyhow!("local runtime home missing"));
            };
            cmd.env("CODEX_HOME", home);
        }

        cmd.arg("exec")
            .arg("--skip-git-repo-check")
            .arg("--json")
            .arg("-o")
            .arg(&output_message_path);

        if let Some(schema) = schema_path {
            cmd.arg("--output-schema").arg(schema);
        }

        if let Some(p) = profile {
            cmd.arg("-p").arg(p);
        }

        if let Some(thread_id) = existing_thread_id {
            cmd.arg("resume").arg(thread_id).arg(prompt);
        } else {
            cmd.arg(prompt);
        }

        let output = cmd
            .output()
            .with_context(|| "failed to execute codex subprocess")?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();

        let mut raw_events = Vec::new();
        let mut errors = Vec::new();
        let mut thread_id: Option<String> = None;
        let mut last_agent_message: Option<String> = None;
        let mut reasoning_text = Vec::new();

        for line in stdout.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }

            let Ok(json) = serde_json::from_str::<Value>(line) else {
                continue;
            };

            if let Some(kind) = json.get("type").and_then(Value::as_str) {
                if kind == "thread.started" {
                    if let Some(id) = json.get("thread_id").and_then(Value::as_str) {
                        thread_id = Some(id.to_string());
                    }
                } else if kind == "error" {
                    if let Some(msg) = json.get("message").and_then(Value::as_str) {
                        errors.push(msg.to_string());
                    }
                } else if kind == "turn.failed" {
                    if let Some(msg) = json
                        .get("error")
                        .and_then(|e| e.get("message"))
                        .and_then(Value::as_str)
                    {
                        errors.push(msg.to_string());
                    }
                }
            }

            if let Some(item) = json.get("item") {
                let item_type = item.get("type").and_then(Value::as_str);
                let text = item.get("text").and_then(Value::as_str);
                if item_type == Some("agent_message") {
                    if let Some(text) = text {
                        last_agent_message = Some(text.to_string());
                    }
                }
                if item_type == Some("reasoning") {
                    if let Some(text) = text {
                        reasoning_text.push(text.to_string());
                    }
                }
                if item_type == Some("error") {
                    if let Some(msg) = item.get("message").and_then(Value::as_str) {
                        errors.push(msg.to_string());
                    }
                }
            }

            raw_events.push(json);
        }

        let fallback_last_message = if output_message_path.exists() {
            let raw = fs::read_to_string(&output_message_path)
                .with_context(|| format!("failed reading {}", output_message_path.display()))?;
            let trimmed = raw.trim().to_string();
            if trimmed.is_empty() {
                None
            } else {
                Some(trimmed)
            }
        } else {
            None
        };

        let last_message = fallback_last_message
            .or(last_agent_message)
            .unwrap_or_else(|| "".to_string());

        if !output.status.success() {
            if errors.is_empty() {
                errors.push(format!(
                    "codex failed (status {}) stderr: {}",
                    output.status,
                    stderr.trim()
                ));
            }
        }

        if last_message.is_empty() && !errors.is_empty() {
            return Err(anyhow!(errors.join(" | ")));
        }

        Ok(CodexTurnResult {
            thread_id,
            last_message,
            reasoning_text,
            errors,
            raw_events,
        })
    }
}

fn ensure_local_codex_template(path: &Path) -> Result<()> {
    if path.exists() {
        return Ok(());
    }

    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }

    let template = r#"# Codex-only local profiles for dnd-agent-game.
# Edit base_url and model choices if needed.
# Keep this file focused on Codex settings only.

model_provider = "localapi"
model_auto_compact_token_limit = 80000

[features]
enable_request_compression = false

[model_providers.localapi]
name = "LocalAPI"
base_url = "http://192.168.10.163:1234/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
requires_openai_auth = false

[profiles.dm_local]
model = "openai/gpt-oss-120b"
model_reasoning_effort = "xhigh"
model_reasoning_summary = "detailed"
show_raw_agent_reasoning = true
model_auto_compact_token_limit = 80000

[profiles.player_local]
model = "openai/gpt-oss-20b"
model_reasoning_effort = "xhigh"
model_reasoning_summary = "detailed"
show_raw_agent_reasoning = true
model_auto_compact_token_limit = 80000
"#;

    fs::write(path, template).with_context(|| format!("failed to write {}", path.display()))?;
    Ok(())
}

fn materialize_codex_home(local_config: &Path, runtime_home: &Path) -> Result<()> {
    fs::create_dir_all(runtime_home)
        .with_context(|| format!("failed to create {}", runtime_home.display()))?;

    let contents = fs::read_to_string(local_config)
        .with_context(|| format!("failed to read {}", local_config.display()))?;

    let target = runtime_home.join("config.toml");
    fs::write(&target, contents)
        .with_context(|| format!("failed to write {}", target.display()))?;
    Ok(())
}

fn ensure_schema_files(
    dm_turn_schema: &Path,
    player_turn_schema: &Path,
    whisper_schema: &Path,
    identity_proposal_schema: &Path,
    identity_decision_schema: &Path,
) -> Result<()> {
    let dm_turn_schema_contents = r#"{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "public_message": { "type": "string" },
    "actions": {
      "type": "array",
      "items": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "type": { "const": "request_message_player" },
              "target": { "type": "string" },
              "targets": {
                "type": "array",
                "items": { "type": "string" },
                "minItems": 1
              },
              "message": { "type": "string" },
              "reason": { "type": "string" }
            },
            "required": ["type", "message"],
            "anyOf": [
              { "required": ["target"] },
              { "required": ["targets"] }
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "type": { "const": "note_write" },
              "text": { "type": "string" }
            },
            "required": ["type", "text"],
            "additionalProperties": false
          }
        ]
      }
    },
    "next_actor_id": {
      "type": "string",
      "enum": [
        "dm_agent",
        "player_ai_1",
        "player_ai_2",
        "player_ai_3",
        "player_ai_4",
        "human_player"
      ]
    },
    "note": { "type": "string" }
  },
  "required": ["public_message", "actions", "next_actor_id"],
  "additionalProperties": false
}
"#;
    fs::write(dm_turn_schema, dm_turn_schema_contents)
        .with_context(|| format!("failed to write {}", dm_turn_schema.display()))?;

    let player_turn_schema_contents = r#"{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "public_message": { "type": "string" },
    "actions": {
      "type": "array",
      "items": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "type": { "const": "request_message_player" },
              "target": { "type": "string" },
              "targets": {
                "type": "array",
                "items": { "type": "string" },
                "minItems": 1
              },
              "message": { "type": "string" },
              "reason": { "type": "string" }
            },
            "required": ["type", "message"],
            "anyOf": [
              { "required": ["target"] },
              { "required": ["targets"] }
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "type": { "const": "note_write" },
              "text": { "type": "string" }
            },
            "required": ["type", "text"],
            "additionalProperties": false
          }
        ]
      }
    },
    "next_actor_id": { "type": "string" },
    "note": { "type": "string" }
  },
  "required": ["public_message", "actions"],
  "additionalProperties": false
}
"#;
    fs::write(player_turn_schema, player_turn_schema_contents)
        .with_context(|| format!("failed to write {}", player_turn_schema.display()))?;

    let whisper_schema_contents = r#"{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "approve": { "type": "boolean" },
    "reason": { "type": "string" }
  },
  "required": ["approve"],
  "additionalProperties": false
}
"#;
    fs::write(whisper_schema, whisper_schema_contents)
        .with_context(|| format!("failed to write {}", whisper_schema.display()))?;

    let identity_proposal_schema_contents = r#"{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "name": { "type": "string", "minLength": 1 },
    "pronouns": { "type": "string", "minLength": 1 }
  },
  "required": ["name", "pronouns"],
  "additionalProperties": false
}
"#;
    fs::write(identity_proposal_schema, identity_proposal_schema_contents)
        .with_context(|| format!("failed to write {}", identity_proposal_schema.display()))?;

    let identity_decision_schema_contents = r#"{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "final_name": { "type": "string", "minLength": 1 },
    "final_pronouns": { "type": "string", "minLength": 1 },
    "reason": { "type": "string" }
  },
  "required": ["final_name", "final_pronouns"],
  "additionalProperties": false
}
"#;
    fs::write(identity_decision_schema, identity_decision_schema_contents)
        .with_context(|| format!("failed to write {}", identity_decision_schema.display()))?;

    Ok(())
}
