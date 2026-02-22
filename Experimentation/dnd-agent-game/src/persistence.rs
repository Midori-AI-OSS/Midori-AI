use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use uuid::Uuid;

use crate::types::{
    ActorSession, CampaignState, CharacterSheet, DM_ACTOR, HUMAN_ACTOR, NoteEntry, NotesFile,
    PLAYER_AI_ACTORS, RunMode, SessionsFile, TranscriptEvent, Visibility, all_actor_ids,
};

pub const STATE_FORMAT_VERSION: u32 = 1;

#[derive(Clone, Debug)]
pub struct CampaignRuntime {
    pub campaign_id: String,
    pub root: PathBuf,
    pub state: CampaignState,
    pub sessions: SessionsFile,
}

impl CampaignRuntime {
    pub fn create_new(campaign_root: &Path, mode: RunMode) -> Result<Self> {
        fs::create_dir_all(campaign_root)
            .with_context(|| format!("failed to create {}", campaign_root.display()))?;

        let campaign_id = Uuid::new_v4().to_string();
        let root = campaign_root.join(&campaign_id);
        let now = Utc::now();

        fs::create_dir_all(root.join("characters"))
            .with_context(|| format!("failed to create {}", root.display()))?;
        fs::create_dir_all(root.join("notes"))
            .with_context(|| format!("failed to create {}", root.display()))?;
        fs::create_dir_all(root.join("sessions"))
            .with_context(|| format!("failed to create {}", root.display()))?;

        let state = CampaignState {
            format_version: STATE_FORMAT_VERSION,
            campaign_id: campaign_id.clone(),
            created_at: now,
            updated_at: now,
            round_index: 0,
            mode,
        };

        let mut sessions = BTreeMap::new();
        for actor in all_actor_ids() {
            sessions.insert(
                actor.to_string(),
                ActorSession {
                    actor_id: actor.to_string(),
                    thread_id: None,
                    last_message: None,
                    updated_at: now,
                },
            );
        }

        let runtime = Self {
            campaign_id,
            root,
            state,
            sessions: SessionsFile {
                format_version: STATE_FORMAT_VERSION,
                sessions,
            },
        };

        runtime.save_state()?;
        runtime.save_sessions()?;
        runtime.write_bootstrap_files()?;

        Ok(runtime)
    }

    pub fn load(campaign_root: &Path, campaign_id: &str) -> Result<Self> {
        let root = campaign_root.join(campaign_id);
        if !root.exists() {
            return Err(anyhow!("campaign {} does not exist", campaign_id));
        }

        let state: CampaignState = read_json_file(&root.join("campaign_state.json"))
            .with_context(|| "failed to read campaign_state.json")?;
        let sessions: SessionsFile = read_json_file(&root.join("sessions/sessions.json"))
            .with_context(|| "failed to read sessions/sessions.json")?;

        Ok(Self {
            campaign_id: campaign_id.to_string(),
            root,
            state,
            sessions,
        })
    }

    pub fn list_campaign_ids(campaign_root: &Path) -> Result<Vec<String>> {
        if !campaign_root.exists() {
            return Ok(vec![]);
        }

        let mut out = vec![];
        for entry in fs::read_dir(campaign_root)
            .with_context(|| format!("failed to read {}", campaign_root.display()))?
        {
            let entry = entry?;
            if entry.file_type()?.is_dir() {
                out.push(entry.file_name().to_string_lossy().to_string());
            }
        }
        out.sort();
        Ok(out)
    }

    pub fn save_state(&self) -> Result<()> {
        write_json_file(&self.root.join("campaign_state.json"), &self.state)
    }

    pub fn save_sessions(&self) -> Result<()> {
        write_json_file(&self.root.join("sessions/sessions.json"), &self.sessions)
    }

    fn write_bootstrap_files(&self) -> Result<()> {
        for actor in all_actor_ids() {
            let notes = NotesFile {
                format_version: STATE_FORMAT_VERSION,
                actor_id: actor.to_string(),
                entries: vec![],
            };
            write_json_file(
                &self.root.join("notes").join(format!("{}.json", actor)),
                &notes,
            )?;

            let sheet = default_sheet_for_actor(actor);
            write_json_file(
                &self.root.join("characters").join(format!("{}.json", actor)),
                &sheet,
            )?;
        }
        Ok(())
    }

    pub fn append_event(&mut self, event: &TranscriptEvent) -> Result<()> {
        let path = self.root.join("events.jsonl");
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .with_context(|| format!("failed to open {}", path.display()))?;
        let line = serde_json::to_string(event).context("failed to serialize transcript event")?;
        file.write_all(line.as_bytes())?;
        file.write_all(b"\n")?;

        self.state.updated_at = Utc::now();
        self.save_state()?;
        Ok(())
    }

    pub fn read_recent_events(&self, limit: usize) -> Result<Vec<TranscriptEvent>> {
        let path = self.root.join("events.jsonl");
        if !path.exists() {
            return Ok(vec![]);
        }

        let file =
            File::open(&path).with_context(|| format!("failed to open {}", path.display()))?;
        let reader = BufReader::new(file);

        let mut events = vec![];
        for line in reader.lines() {
            let line = line?;
            let event: TranscriptEvent = serde_json::from_str(&line)
                .with_context(|| "failed to parse transcript event line")?;
            events.push(event);
        }

        if events.len() > limit {
            Ok(events.split_off(events.len() - limit))
        } else {
            Ok(events)
        }
    }

    pub fn set_thread_id(&mut self, actor_id: &str, thread_id: String) -> Result<()> {
        let Some(session) = self.sessions.sessions.get_mut(actor_id) else {
            return Err(anyhow!("unknown actor {}", actor_id));
        };
        session.thread_id = Some(thread_id);
        session.updated_at = Utc::now();
        self.save_sessions()
    }

    pub fn set_last_message(&mut self, actor_id: &str, message: String) -> Result<()> {
        let Some(session) = self.sessions.sessions.get_mut(actor_id) else {
            return Err(anyhow!("unknown actor {}", actor_id));
        };
        session.last_message = Some(message);
        session.updated_at = Utc::now();
        self.save_sessions()
    }

    pub fn get_thread_id(&self, actor_id: &str) -> Option<String> {
        self.sessions
            .sessions
            .get(actor_id)
            .and_then(|s| s.thread_id.clone())
    }

    pub fn append_note(&self, actor_id: &str, text: &str) -> Result<()> {
        let path = self.root.join("notes").join(format!("{}.json", actor_id));
        let mut notes: NotesFile = read_json_file(&path)?;
        notes.entries.push(NoteEntry {
            timestamp: Utc::now(),
            text: text.to_string(),
        });
        write_json_file(&path, &notes)
    }

    pub fn read_notes(&self, actor_id: &str) -> Result<NotesFile> {
        let path = self.root.join("notes").join(format!("{}.json", actor_id));
        read_json_file(&path)
    }

    pub fn read_character_sheet(&self, actor_id: &str) -> Result<CharacterSheet> {
        let path = self
            .root
            .join("characters")
            .join(format!("{}.json", actor_id));
        read_json_file(&path)
    }

    pub fn visible_events_for_actor(
        &self,
        actor_id: &str,
        limit: usize,
    ) -> Result<Vec<TranscriptEvent>> {
        let events = self.read_recent_events(limit)?;
        let filtered = events
            .into_iter()
            .filter(|e| match &e.visibility {
                Visibility::Public => true,
                Visibility::Whisper { sender, target } => {
                    actor_id == DM_ACTOR || actor_id == sender || actor_id == target
                }
            })
            .collect();
        Ok(filtered)
    }

    pub fn add_public_message(&mut self, speaker: &str, message: &str) -> Result<()> {
        let event = TranscriptEvent {
            timestamp: Utc::now(),
            speaker: speaker.to_string(),
            message: message.to_string(),
            visibility: Visibility::Public,
        };
        self.append_event(&event)
    }

    pub fn add_whisper(&mut self, sender: &str, target: &str, message: &str) -> Result<()> {
        let event = TranscriptEvent {
            timestamp: Utc::now(),
            speaker: sender.to_string(),
            message: message.to_string(),
            visibility: Visibility::Whisper {
                sender: sender.to_string(),
                target: target.to_string(),
            },
        };
        self.append_event(&event)
    }

    pub fn bump_round(&mut self) -> Result<()> {
        self.state.round_index = self.state.round_index.saturating_add(1);
        self.state.updated_at = Utc::now();
        self.save_state()
    }
}

fn default_sheet_for_actor(actor: &str) -> CharacterSheet {
    let (class_name, level) = if actor == DM_ACTOR {
        ("npc_director".to_string(), 20)
    } else if actor == HUMAN_ACTOR {
        ("fighter".to_string(), 1)
    } else if PLAYER_AI_ACTORS.contains(&actor) {
        ("adventurer".to_string(), 1)
    } else {
        ("commoner".to_string(), 1)
    };

    CharacterSheet {
        format_version: STATE_FORMAT_VERSION,
        actor_id: actor.to_string(),
        class_name,
        level,
        armor_class: 12,
        max_hp: 12,
        current_hp: 12,
        strength: 10,
        dexterity: 10,
        constitution: 10,
        intelligence: 10,
        wisdom: 10,
        charisma: 10,
    }
}

fn read_json_file<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T> {
    let raw =
        fs::read_to_string(path).with_context(|| format!("failed to read {}", path.display()))?;
    let val = serde_json::from_str(&raw)
        .with_context(|| format!("failed to parse JSON {}", path.display()))?;
    Ok(val)
}

fn write_json_file<T: serde::Serialize>(path: &Path, value: &T) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }
    let raw = serde_json::to_string_pretty(value).context("failed to serialize JSON")?;
    fs::write(path, raw).with_context(|| format!("failed to write {}", path.display()))?;
    Ok(())
}
