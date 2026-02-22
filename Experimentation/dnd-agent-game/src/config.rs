use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};

use crate::types::RunMode;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AppConfig {
    pub runtime: RuntimeConfig,
    pub secrets: SecretsConfig,
    pub paths: PathsConfig,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RuntimeConfig {
    pub default_mode: RunMode,
    pub show_debug_default: bool,
    pub no_turn_timeout: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SecretsConfig {
    pub local_openai_api_key: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PathsConfig {
    pub campaign_root: String,
    pub codex_local_config: String,
    pub codex_runtime_home: String,
    pub schema_dir: String,
}

#[derive(Clone, Debug)]
pub struct ResolvedPaths {
    pub app_root: PathBuf,
    pub campaign_root: PathBuf,
    pub codex_local_config: PathBuf,
    pub codex_runtime_home: PathBuf,
    pub schema_dir: PathBuf,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            runtime: RuntimeConfig {
                default_mode: RunMode::Local,
                show_debug_default: false,
                no_turn_timeout: true,
            },
            secrets: SecretsConfig {
                local_openai_api_key: "sx-xxx".to_string(),
            },
            paths: PathsConfig {
                campaign_root: "data/campaigns".to_string(),
                codex_local_config: "local-config.toml".to_string(),
                codex_runtime_home: ".runtime/codex-local-home".to_string(),
                schema_dir: "schemas".to_string(),
            },
        }
    }
}

impl AppConfig {
    pub fn resolve_paths(&self, config_path: &Path) -> Result<ResolvedPaths> {
        let app_root = config_path
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));

        let campaign_root = app_root.join(&self.paths.campaign_root);
        let codex_local_config = app_root.join(&self.paths.codex_local_config);
        let codex_runtime_home = app_root.join(&self.paths.codex_runtime_home);
        let schema_dir = app_root.join(&self.paths.schema_dir);

        Ok(ResolvedPaths {
            app_root,
            campaign_root,
            codex_local_config,
            codex_runtime_home,
            schema_dir,
        })
    }
}

pub fn load_or_init_config(config_path: &Path) -> Result<AppConfig> {
    if !config_path.exists() {
        let parent = config_path
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));
        fs::create_dir_all(&parent)
            .with_context(|| format!("failed to create config parent: {}", parent.display()))?;

        let template = toml::to_string_pretty(&AppConfig::default())
            .context("failed to render default app config")?;
        fs::write(config_path, template)
            .with_context(|| format!("failed to write {}", config_path.display()))?;
    }

    let raw = fs::read_to_string(config_path)
        .with_context(|| format!("failed reading {}", config_path.display()))?;
    let mut cfg: AppConfig = toml::from_str(&raw)
        .with_context(|| format!("invalid TOML in {}", config_path.display()))?;

    // Migrate early templates to the local default key expected by this prototype.
    if cfg.secrets.local_openai_api_key.trim() == "replace-me-local-key" {
        cfg.secrets.local_openai_api_key = "sx-xxx".to_string();
        let rewritten = toml::to_string_pretty(&cfg).context("failed to rewrite app config")?;
        fs::write(config_path, rewritten)
            .with_context(|| format!("failed to update {}", config_path.display()))?;
    }

    if cfg.runtime.no_turn_timeout {
        // This flag is required by the agreed design; keep it explicit.
    } else {
        bail!(
            "runtime.no_turn_timeout must remain true for this prototype (no per-turn agent timeout)"
        );
    }

    Ok(cfg)
}
