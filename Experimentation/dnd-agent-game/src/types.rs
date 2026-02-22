use std::collections::BTreeMap;

use chrono::{DateTime, Utc};
use clap::ValueEnum;
use serde::{Deserialize, Serialize};

pub const DM_ACTOR: &str = "dm_agent";
pub const HUMAN_ACTOR: &str = "human_player";
pub const PLAYER_AI_ACTORS: [&str; 4] =
    ["player_ai_1", "player_ai_2", "player_ai_3", "player_ai_4"];

pub fn all_actor_ids() -> Vec<&'static str> {
    let mut ids = vec![DM_ACTOR];
    ids.extend(PLAYER_AI_ACTORS);
    ids.push(HUMAN_ACTOR);
    ids
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, ValueEnum, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum RunMode {
    Local,
    Remote,
}

impl std::fmt::Display for RunMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RunMode::Local => write!(f, "local"),
            RunMode::Remote => write!(f, "remote"),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Visibility {
    Public,
    Whisper { sender: String, target: String },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TranscriptEvent {
    pub timestamp: DateTime<Utc>,
    pub speaker: String,
    pub message: String,
    pub visibility: Visibility,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CampaignState {
    pub format_version: u32,
    pub campaign_id: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub round_index: u64,
    pub mode: RunMode,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ActorIdentity {
    pub actor_id: String,
    pub display_name: String,
    pub pronouns: String,
    pub approved_by_dm: bool,
    pub updated_at: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IdentitiesFile {
    pub format_version: u32,
    pub identities: BTreeMap<String, ActorIdentity>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ActorSession {
    pub actor_id: String,
    pub thread_id: Option<String>,
    pub last_message: Option<String>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SessionsFile {
    pub format_version: u32,
    pub sessions: BTreeMap<String, ActorSession>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NoteEntry {
    pub timestamp: DateTime<Utc>,
    pub text: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NotesFile {
    pub format_version: u32,
    pub actor_id: String,
    pub entries: Vec<NoteEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CharacterSheet {
    pub format_version: u32,
    pub actor_id: String,
    pub class_name: String,
    pub level: u8,
    pub armor_class: u16,
    pub max_hp: i32,
    pub current_hp: i32,
    pub strength: i16,
    pub dexterity: i16,
    pub constitution: i16,
    pub intelligence: i16,
    pub wisdom: i16,
    pub charisma: i16,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentTurnResponse {
    pub public_message: String,
    #[serde(default)]
    pub actions: Vec<AgentAction>,
    #[serde(default)]
    pub next_actor_id: Option<String>,
    #[serde(default)]
    pub note: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum AgentAction {
    RequestMessagePlayer {
        #[serde(default)]
        target: Option<String>,
        #[serde(default)]
        targets: Vec<String>,
        message: String,
        #[serde(default)]
        reason: Option<String>,
    },
    NoteWrite {
        text: String,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WhisperDecision {
    pub approve: bool,
    #[serde(default)]
    pub reason: Option<String>,
}
