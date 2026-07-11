use cxx_qt_lib::QString;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Component, Path, PathBuf};
use std::pin::Pin;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
use walkdir::{DirEntry, WalkDir};

const APP_DIR: &str = "midori-ai-radio-studio";
const PROMPT_HISTORY_LIMIT: usize = 40;
const FEEDBACK_CONTEXT_LIMIT: usize = 30;

const TAG_WHY_MADE: &str = "midori_ai_why_made";
const TAG_BACKSTORY: &str = "midori_ai_backstory";
const TAG_RADIO_REASON: &str = "midori_ai_radio_reason";
const TAG_MUSIC_THEME: &str = "midori_ai_music_theme";
const TAG_LISTENER_TAKEAWAY: &str = "midori_ai_listener_takeaway";
const TAG_VIBE_ANALYSIS: &str = "midori_ai_vibe_analysis";
const TAG_VIBE_SUMMARY: &str = "midori_ai_vibe_summary";
const TAG_VIBE_CACHED_AT_EPOCH: &str = "midori_ai_vibe_cached_at_epoch";
const TAG_VIBE_CACHE_SCHEMA: &str = "midori_ai_vibe_cache_schema";

#[cxx_qt::bridge]
mod ffi {
    unsafe extern "C++" {
        include!("cxx-qt-lib/qstring.h");
        type QString = cxx_qt_lib::QString;
    }

    #[auto_cxx_name]
    unsafe extern "RustQt" {
        #[qobject]
        #[qml_element]
        type RadioBackend = super::RadioBackendStruct;

        #[qinvokable]
        fn load_settings(self: Pin<&mut RadioBackend>) -> QString;

        #[qinvokable]
        fn save_settings(self: Pin<&mut RadioBackend>, payload_json: QString) -> QString;

        #[qinvokable]
        fn environment_status(self: Pin<&mut RadioBackend>) -> QString;

        #[qinvokable]
        fn scan_library(
            self: Pin<&mut RadioBackend>,
            root: QString,
            include_blocked: bool,
        ) -> QString;

        #[qinvokable]
        fn scan_channels(self: Pin<&mut RadioBackend>, root: QString) -> QString;

        #[qinvokable]
        fn recent_downloads(
            self: Pin<&mut RadioBackend>,
            root: QString,
            downloads_dir: QString,
        ) -> QString;

        #[qinvokable]
        fn inspect_song(self: Pin<&mut RadioBackend>, path: QString) -> QString;

        #[qinvokable]
        fn save_song_metadata(
            self: Pin<&mut RadioBackend>,
            payload_json: QString,
        ) -> QString;

        #[qinvokable]
        fn import_songs(self: Pin<&mut RadioBackend>, payload_json: QString) -> QString;

        #[qinvokable]
        fn play_song(self: Pin<&mut RadioBackend>, path: QString) -> QString;

        #[qinvokable]
        fn trash_song(self: Pin<&mut RadioBackend>, path: QString) -> QString;

        #[qinvokable]
        fn set_channel_blocked(
            self: Pin<&mut RadioBackend>,
            payload_json: QString,
        ) -> QString;

        #[qinvokable]
        fn load_prompt_state(self: Pin<&mut RadioBackend>) -> QString;

        #[qinvokable]
        fn record_feedback(self: Pin<&mut RadioBackend>, payload_json: QString) -> QString;

        #[qinvokable]
        fn update_prompts(self: Pin<&mut RadioBackend>, payload_json: QString) -> QString;

        #[qinvokable]
        fn reset_prompt(self: Pin<&mut RadioBackend>, prompt_key: QString) -> QString;

        #[qinvokable]
        fn run_song_prompt(self: Pin<&mut RadioBackend>, payload_json: QString) -> QString;

        #[qinvokable]
        fn open_path(self: Pin<&mut RadioBackend>, path: QString) -> QString;
    }
}

#[derive(Default)]
pub struct RadioBackendStruct {}

impl ffi::RadioBackend {
    pub fn load_settings(self: Pin<&mut Self>) -> QString {
        let _ = self;
        match load_or_create_settings() {
            Ok(settings) => ok("Settings loaded.", settings),
            Err(error) => fail(error),
        }
    }

    pub fn save_settings(self: Pin<&mut Self>, payload_json: QString) -> QString {
        let _ = self;
        let parsed: Result<AppSettings, _> = serde_json::from_str(&payload_json.to_string());
        match parsed {
            Ok(settings) => match save_json_atomic(&settings_path(), &settings) {
                Ok(()) => ok("Settings saved.", settings),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read settings: {error}")),
        }
    }

    pub fn environment_status(self: Pin<&mut Self>) -> QString {
        let _ = self;
        let config = config_dir();
        let data = data_dir();
        ok(
            "Environment checked.",
            json!({
                "ffmpeg": command_exists("ffmpeg"),
                "ffprobe": command_exists("ffprobe"),
                "opencode": command_exists("opencode"),
                "mpv": command_exists("mpv"),
                "vlc": command_exists("vlc"),
                "ffplay": command_exists("ffplay"),
                "kioTrash": command_exists("kioclient6") || command_exists("kioclient") || command_exists("kioclient5"),
                "gioTrash": command_exists("gio"),
                "configDir": config.to_string_lossy(),
                "dataDir": data.to_string_lossy(),
            }),
        )
    }

    pub fn scan_library(
        self: Pin<&mut Self>,
        root: QString,
        include_blocked: bool,
    ) -> QString {
        let _ = self;
        let root = PathBuf::from(root.to_string());
        match scan_library_impl(&root, include_blocked) {
            Ok(songs) => ok(
                format!("Loaded {} songs from Midori AI Radio.", songs.len()),
                songs,
            ),
            Err(error) => fail(error),
        }
    }

    pub fn scan_channels(self: Pin<&mut Self>, root: QString) -> QString {
        let _ = self;
        let root = PathBuf::from(root.to_string());
        match scan_channels_impl(&root) {
            Ok(channels) => ok(format!("Loaded {} radio channels.", channels.len()), channels),
            Err(error) => fail(error),
        }
    }

    pub fn recent_downloads(
        self: Pin<&mut Self>,
        root: QString,
        downloads_dir: QString,
    ) -> QString {
        let _ = self;
        let root = PathBuf::from(root.to_string());
        let downloads = PathBuf::from(downloads_dir.to_string());
        match recent_downloads_impl(&root, &downloads, 20) {
            Ok(files) => ok(format!("Found {} recent downloads.", files.len()), files),
            Err(error) => fail(error),
        }
    }

    pub fn inspect_song(self: Pin<&mut Self>, path: QString) -> QString {
        let _ = self;
        let path = PathBuf::from(path.to_string());
        match inspect_song_impl(&path, None) {
            Ok(song) => ok("Song metadata loaded.", song),
            Err(error) => fail(error),
        }
    }

    pub fn save_song_metadata(
        self: Pin<&mut Self>,
        payload_json: QString,
    ) -> QString {
        let _ = self;
        let payload: Result<SaveMetadataRequest, _> =
            serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match save_song_metadata_impl(&payload) {
                Ok(song) => ok("Metadata saved to the MP3.", song),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read metadata form: {error}")),
        }
    }

    pub fn import_songs(self: Pin<&mut Self>, payload_json: QString) -> QString {
        let _ = self;
        let payload: Result<ImportRequest, _> = serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match import_songs_impl(&payload) {
                Ok(imported) => ok(format!("Imported {} song(s).", imported.len()), imported),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read import request: {error}")),
        }
    }

    pub fn play_song(self: Pin<&mut Self>, path: QString) -> QString {
        let _ = self;
        let path = PathBuf::from(path.to_string());
        match play_song_impl(&path) {
            Ok(player) => ok(format!("Opened song with {player}."), json!({ "player": player })),
            Err(error) => fail(error),
        }
    }

    pub fn trash_song(self: Pin<&mut Self>, path: QString) -> QString {
        let _ = self;
        let path = PathBuf::from(path.to_string());
        match trash_song_impl(&path) {
            Ok(tool) => ok(format!("Moved song to Trash with {tool}."), json!({ "tool": tool })),
            Err(error) => fail(error),
        }
    }

    pub fn set_channel_blocked(
        self: Pin<&mut Self>,
        payload_json: QString,
    ) -> QString {
        let _ = self;
        let payload: Result<ChannelBlockRequest, _> =
            serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match set_channel_blocked_impl(&payload) {
                Ok(()) => ok(
                    if payload.blocked {
                        "Channel blocked."
                    } else {
                        "Channel unblocked."
                    },
                    payload,
                ),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read channel request: {error}")),
        }
    }

    pub fn load_prompt_state(self: Pin<&mut Self>) -> QString {
        let _ = self;
        match load_prompt_state_impl() {
            Ok(state) => ok("Prompt state loaded.", state),
            Err(error) => fail(error),
        }
    }

    pub fn record_feedback(self: Pin<&mut Self>, payload_json: QString) -> QString {
        let _ = self;
        let payload: Result<FeedbackRequest, _> =
            serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match record_feedback_impl(&payload) {
                Ok(entry) => ok("Feedback recorded for the next prompt update.", entry),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read feedback: {error}")),
        }
    }

    pub fn update_prompts(self: Pin<&mut Self>, payload_json: QString) -> QString {
        let _ = self;
        let payload: Result<UpdatePromptRequest, _> =
            serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match update_prompt_impl(&payload) {
                Ok(result) => ok("Prompt updated and versioned.", result),
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read prompt update request: {error}")),
        }
    }

    pub fn reset_prompt(self: Pin<&mut Self>, prompt_key: QString) -> QString {
        let _ = self;
        match reset_prompt_impl(&prompt_key.to_string()) {
            Ok(result) => ok("Prompt reset to its built-in default.", result),
            Err(error) => fail(error),
        }
    }

    pub fn run_song_prompt(self: Pin<&mut Self>, payload_json: QString) -> QString {
        let _ = self;
        let payload: Result<RunPromptRequest, _> =
            serde_json::from_str(&payload_json.to_string());
        match payload {
            Ok(payload) => match run_song_prompt_impl(&payload) {
                Ok(result) => {
                    let message = if result.warning.is_empty() {
                        "Prompt completed.".to_owned()
                    } else {
                        result.warning.clone()
                    };
                    ok(message, result)
                }
                Err(error) => fail(error),
            },
            Err(error) => fail(format!("Could not read prompt request: {error}")),
        }
    }

    pub fn open_path(self: Pin<&mut Self>, path: QString) -> QString {
        let _ = self;
        let path = PathBuf::from(path.to_string());
        match open_path_impl(&path) {
            Ok(tool) => ok(format!("Opened with {tool}."), json!({ "tool": tool })),
            Err(error) => fail(error),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AppSettings {
    library_root: String,
    downloads_dir: String,
    model: String,
    variant: String,
    fallback_model: String,
    fallback_variant: String,
    include_blocked: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        let radio_root = home.join("Music").join("Midori AI Radio");
        let library_root = if radio_root.is_dir() {
            radio_root
        } else {
            home.join("Music")
        };

        Self {
            library_root: library_root.to_string_lossy().into_owned(),
            downloads_dir: home.join("Downloads").to_string_lossy().into_owned(),
            model: "lm-studio/qwen/qwen3.6-27b".to_owned(),
            variant: "xhigh".to_owned(),
            fallback_model: "deepseek/deepseek-v4-flash".to_owned(),
            fallback_variant: "max".to_owned(),
            include_blocked: false,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SongRecord {
    path: String,
    relative_path: String,
    file_name: String,
    channel: String,
    title: String,
    artist: String,
    album: String,
    genre: String,
    comment: String,
    lyrics: String,
    why_made: String,
    backstory: String,
    radio_reason: String,
    music_theme: String,
    listener_takeaway: String,
    vibe_analysis: String,
    vibe_summary: String,
    vibe_cached_at_epoch: String,
    vibe_cache_schema: String,
    duration_seconds: f64,
    modified_epoch: u64,
    stale_comment: bool,
    blocked_channel: bool,
    search_text: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ChannelRecord {
    name: String,
    path: String,
    song_count: usize,
    stale_count: usize,
    blocked: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DownloadRecord {
    path: String,
    file_name: String,
    modified_epoch: u64,
    already_imported: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SaveMetadataRequest {
    path: String,
    title: String,
    artist: String,
    album: String,
    genre: String,
    comment: String,
    why_made: String,
    backstory: String,
    radio_reason: String,
    music_theme: String,
    listener_takeaway: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ImportRequest {
    root: String,
    channel: String,
    sources: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ChannelBlockRequest {
    root: String,
    channel: String,
    blocked: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct FeedbackEntry {
    id: String,
    created_at_epoch: u64,
    prompt_key: String,
    song_path: String,
    output: String,
    feedback: String,
    rating: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct FeedbackRequest {
    prompt_key: String,
    song_path: String,
    output: String,
    feedback: String,
    rating: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PromptStore {
    version: u64,
    updated_at_epoch: u64,
    prompts: BTreeMap<String, String>,
}

impl Default for PromptStore {
    fn default() -> Self {
        Self {
            version: 1,
            updated_at_epoch: now_epoch(),
            prompts: default_prompts(),
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct PromptState {
    store: PromptStore,
    feedback: Vec<FeedbackEntry>,
    config_dir: String,
    data_dir: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdatePromptRequest {
    root: String,
    prompt_key: String,
    current_prompt: String,
    model: String,
    variant: String,
    fallback_model: String,
    fallback_variant: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct PromptUpdateResult {
    prompt_key: String,
    prompt: String,
    version: u64,
    updated_at_epoch: u64,
    feedback_used: usize,
    used_model: String,
    used_fallback_synthesis: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RunPromptRequest {
    root: String,
    prompt_key: String,
    song_path: String,
    notes: String,
    model: String,
    variant: String,
    fallback_model: String,
    fallback_variant: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RunPromptResult {
    output: String,
    prompt_preview: String,
    used_model: String,
    warning: String,
}

#[derive(Debug, Deserialize)]
struct ProbeRoot {
    format: Option<ProbeFormat>,
}

#[derive(Debug, Deserialize)]
struct ProbeFormat {
    duration: Option<String>,
    tags: Option<HashMap<String, String>>,
}

fn ok<T: Serialize>(message: impl Into<String>, data: T) -> QString {
    to_qstring(json!({
        "ok": true,
        "message": message.into(),
        "data": data,
    }))
}

fn fail(message: impl Into<String>) -> QString {
    to_qstring(json!({
        "ok": false,
        "message": message.into(),
        "data": Value::Null,
    }))
}

fn to_qstring(value: Value) -> QString {
    QString::from(&serde_json::to_string(&value).unwrap_or_else(|_| {
        "{\"ok\":false,\"message\":\"Internal JSON serialization error.\",\"data\":null}"
            .to_owned()
    }))
}

fn now_epoch() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn now_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0)
}

fn modified_epoch(path: &Path) -> u64 {
    fs::metadata(path)
        .and_then(|metadata| metadata.modified())
        .ok()
        .and_then(|time| time.duration_since(UNIX_EPOCH).ok())
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn config_dir() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(APP_DIR)
}

fn data_dir() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(APP_DIR)
}

fn settings_path() -> PathBuf {
    config_dir().join("settings.json")
}

fn prompts_path() -> PathBuf {
    config_dir().join("prompts.json")
}

fn feedback_path() -> PathBuf {
    data_dir().join("feedback.jsonl")
}

fn prompt_history_dir() -> PathBuf {
    data_dir().join("prompt-history")
}

fn load_or_create_settings() -> Result<AppSettings, String> {
    let path = settings_path();
    if path.is_file() {
        let contents = fs::read_to_string(&path)
            .map_err(|error| format!("Could not read {}: {error}", path.display()))?;
        return serde_json::from_str(&contents)
            .map_err(|error| format!("Could not parse {}: {error}", path.display()));
    }

    let settings = AppSettings::default();
    save_json_atomic(&path, &settings)?;
    Ok(settings)
}

fn save_json_atomic<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("No parent directory for {}", path.display()))?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("Could not create {}: {error}", parent.display()))?;

    let temp = parent.join(format!(
        ".{}.{}.tmp",
        path.file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("state"),
        now_millis()
    ));
    let serialized = serde_json::to_string_pretty(value)
        .map_err(|error| format!("Could not serialize {}: {error}", path.display()))?;
    fs::write(&temp, serialized)
        .map_err(|error| format!("Could not write {}: {error}", temp.display()))?;
    fs::rename(&temp, path).map_err(|error| {
        let _ = fs::remove_file(&temp);
        format!("Could not replace {}: {error}", path.display())
    })
}

fn load_prompt_store() -> Result<PromptStore, String> {
    let path = prompts_path();
    if path.is_file() {
        let contents = fs::read_to_string(&path)
            .map_err(|error| format!("Could not read {}: {error}", path.display()))?;
        let mut store: PromptStore = serde_json::from_str(&contents)
            .map_err(|error| format!("Could not parse {}: {error}", path.display()))?;
        for (key, prompt) in default_prompts() {
            store.prompts.entry(key).or_insert(prompt);
        }
        return Ok(store);
    }

    let store = PromptStore::default();
    save_json_atomic(&path, &store)?;
    Ok(store)
}

fn load_feedback() -> Result<Vec<FeedbackEntry>, String> {
    let path = feedback_path();
    if !path.is_file() {
        return Ok(Vec::new());
    }

    let file = File::open(&path)
        .map_err(|error| format!("Could not read {}: {error}", path.display()))?;
    let mut entries = Vec::new();
    for line in BufReader::new(file).lines() {
        let line = line.map_err(|error| format!("Could not read feedback: {error}"))?;
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(entry) = serde_json::from_str::<FeedbackEntry>(&line) {
            entries.push(entry);
        }
    }
    entries.sort_by_key(|entry| entry.created_at_epoch);
    Ok(entries)
}

fn load_prompt_state_impl() -> Result<PromptState, String> {
    Ok(PromptState {
        store: load_prompt_store()?,
        feedback: load_feedback()?,
        config_dir: config_dir().to_string_lossy().into_owned(),
        data_dir: data_dir().to_string_lossy().into_owned(),
    })
}

fn default_prompts() -> BTreeMap<String, String> {
    BTreeMap::from([
        (
            "comment".to_owned(),
            "Write exactly one natural sentence describing this song. Use confirmed lyrics and metadata first. Plainly explain the story, subject, or emotional movement; for an instrumental, name a supported motif, source, arrangement idea, or restrained atmosphere. Keep the sentence about the song itself. Do not add station, collection, productivity, listener-use, production-history, or model-generation boilerplate. Use names exactly as the evidence supports: Luna Midori is a person and Midori AI is a group. Return only the sentence."
                .to_owned(),
        ),
        (
            "refine_comment".to_owned(),
            "Revise the current draft into exactly one natural sentence that stays true to the song. Follow the supplied feedback, preserve supported details, and remove station, collection, productivity, listener-use, production-history, and model-generation boilerplate. Return only the revised sentence."
                .to_owned(),
        ),
        (
            "qna_cleanup".to_owned(),
            "Polish the supplied metadata answer into one or two natural sentences. Preserve its meaning, use confirmed song and library evidence, and do not add unsupported facts. Use names exactly as the evidence supports. Return only the answer."
                .to_owned(),
        ),
        (
            "qna_guess".to_owned(),
            "Answer the missing Midori AI Radio metadata field in one or two natural sentences. Prefer confirmed lyrics, existing metadata, and related library tracks. If evidence is thin, make a cautious inference rather than inventing details. Return only the answer."
                .to_owned(),
        ),
        (
            "channel_recommendation".to_owned(),
            "Choose exactly one channel from the supplied Midori AI Radio channel list. Base the choice on the song title, filename, theme, lyrics, and existing metadata. Do not create a new channel name. Return only the chosen channel."
                .to_owned(),
        ),
    ])
}

fn scan_library_impl(root: &Path, include_blocked: bool) -> Result<Vec<SongRecord>, String> {
    validate_library_root(root)?;

    let walker = WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| should_descend(entry, root, include_blocked));

    let mut songs = Vec::new();
    for entry in walker.filter_map(Result::ok) {
        if !entry.file_type().is_file() || !is_mp3(entry.path()) {
            continue;
        }
        match inspect_song_impl(entry.path(), Some(root)) {
            Ok(song) => songs.push(song),
            Err(error) => eprintln!("Midori AI Radio Studio: {error}"),
        }
    }

    songs.sort_by(|left, right| {
        left.channel
            .to_lowercase()
            .cmp(&right.channel.to_lowercase())
            .then_with(|| left.title.to_lowercase().cmp(&right.title.to_lowercase()))
    });
    Ok(songs)
}

fn should_descend(entry: &DirEntry, root: &Path, include_blocked: bool) -> bool {
    if include_blocked || entry.path() == root || !entry.file_type().is_dir() {
        return true;
    }
    !entry.path().join(".blocked").is_file()
}

fn scan_channels_impl(root: &Path) -> Result<Vec<ChannelRecord>, String> {
    validate_library_root(root)?;
    let mut channels = Vec::new();
    let entries = fs::read_dir(root)
        .map_err(|error| format!("Could not read {}: {error}", root.display()))?;

    for entry in entries {
        let entry = entry.map_err(|error| format!("Could not read channel entry: {error}"))?;
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        let blocked = path.join(".blocked").is_file();
        let mut song_count = 0usize;
        let mut stale_count = 0usize;
        for child in WalkDir::new(&path)
            .follow_links(false)
            .into_iter()
            .filter_map(Result::ok)
        {
            if !child.file_type().is_file() || !is_mp3(child.path()) {
                continue;
            }
            song_count += 1;
            if let Ok(record) = inspect_song_impl(child.path(), Some(root)) {
                if record.stale_comment {
                    stale_count += 1;
                }
            }
        }
        channels.push(ChannelRecord {
            name,
            path: path.to_string_lossy().into_owned(),
            song_count,
            stale_count,
            blocked,
        });
    }

    channels.sort_by(|left, right| left.name.to_lowercase().cmp(&right.name.to_lowercase()));
    Ok(channels)
}

fn recent_downloads_impl(
    root: &Path,
    downloads_dir: &Path,
    limit: usize,
) -> Result<Vec<DownloadRecord>, String> {
    if !downloads_dir.is_dir() {
        return Err(format!(
            "Downloads directory does not exist: {}",
            downloads_dir.display()
        ));
    }

    let mut imported_names = HashSet::new();
    if root.is_dir() {
        for entry in WalkDir::new(root)
            .follow_links(false)
            .into_iter()
            .filter_map(Result::ok)
        {
            if entry.file_type().is_file() && is_mp3(entry.path()) {
                if let Some(name) = entry.path().file_name().and_then(|name| name.to_str()) {
                    imported_names.insert(name.to_lowercase());
                }
            }
        }
    }

    let mut downloads = Vec::new();
    for entry in fs::read_dir(downloads_dir)
        .map_err(|error| format!("Could not read {}: {error}", downloads_dir.display()))?
    {
        let entry = entry.map_err(|error| format!("Could not read download entry: {error}"))?;
        let path = entry.path();
        if !path.is_file() || !is_mp3(&path) {
            continue;
        }
        let file_name = entry.file_name().to_string_lossy().into_owned();
        let already_imported = imported_names.contains(&file_name.to_lowercase());
        downloads.push(DownloadRecord {
            path: path.to_string_lossy().into_owned(),
            file_name,
            modified_epoch: modified_epoch(&path),
            already_imported,
        });
    }

    downloads.sort_by(|left, right| right.modified_epoch.cmp(&left.modified_epoch));
    downloads.truncate(limit);
    Ok(downloads)
}

fn inspect_song_impl(path: &Path, root: Option<&Path>) -> Result<SongRecord, String> {
    if !path.is_file() {
        return Err(format!("Song does not exist: {}", path.display()));
    }
    if !is_mp3(path) {
        return Err(format!("Only MP3 files are supported: {}", path.display()));
    }
    if !command_exists("ffprobe") {
        return Err("ffprobe is required to read MP3 metadata.".to_owned());
    }

    let output = Command::new("ffprobe")
        .args([
            "-v",
            "error",
            "-show_entries",
            "format=duration:format_tags",
            "-of",
            "json",
        ])
        .arg(path)
        .output()
        .map_err(|error| format!("Could not start ffprobe: {error}"))?;

    if !output.status.success() {
        return Err(format!(
            "ffprobe failed for {}: {}",
            path.display(),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    let probe: ProbeRoot = serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("Could not parse ffprobe output: {error}"))?;
    let format = probe.format.unwrap_or(ProbeFormat {
        duration: None,
        tags: None,
    });
    let tags = format.tags.unwrap_or_default();

    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or_default()
        .to_owned();
    let fallback_title = path
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or_default()
        .to_owned();
    let relative_path = root
        .and_then(|root| path.strip_prefix(root).ok())
        .unwrap_or(path)
        .to_string_lossy()
        .into_owned();
    let channel = root
        .and_then(|root| path.strip_prefix(root).ok())
        .and_then(|relative| relative.components().next())
        .and_then(|component| match component {
            Component::Normal(name) => Some(name.to_string_lossy().into_owned()),
            _ => None,
        })
        .unwrap_or_else(|| {
            path.parent()
                .and_then(Path::file_name)
                .and_then(|name| name.to_str())
                .unwrap_or("Unsorted")
                .to_owned()
        });
    let blocked_channel = root
        .map(|root| root.join(&channel).join(".blocked").is_file())
        .unwrap_or(false);

    let title = tag(&tags, "title").unwrap_or(fallback_title);
    let artist = tag(&tags, "artist").unwrap_or_default();
    let album = tag(&tags, "album").unwrap_or_default();
    let genre = tag(&tags, "genre").unwrap_or_default();
    let comment = tag(&tags, "comment").unwrap_or_default();
    let lyrics = tag(&tags, "lyrics-eng")
        .or_else(|| tag(&tags, "lyrics"))
        .unwrap_or_default();
    let why_made = tag(&tags, TAG_WHY_MADE).unwrap_or_default();
    let backstory = tag(&tags, TAG_BACKSTORY).unwrap_or_default();
    let radio_reason = tag(&tags, TAG_RADIO_REASON).unwrap_or_default();
    let music_theme = tag(&tags, TAG_MUSIC_THEME).unwrap_or_default();
    let listener_takeaway = tag(&tags, TAG_LISTENER_TAKEAWAY).unwrap_or_default();
    let vibe_analysis = tag(&tags, TAG_VIBE_ANALYSIS).unwrap_or_default();
    let vibe_summary = tag(&tags, TAG_VIBE_SUMMARY).unwrap_or_default();
    let vibe_cached_at_epoch = tag(&tags, TAG_VIBE_CACHED_AT_EPOCH).unwrap_or_default();
    let vibe_cache_schema = tag(&tags, TAG_VIBE_CACHE_SCHEMA).unwrap_or_default();
    let duration_seconds = format
        .duration
        .and_then(|duration| duration.parse::<f64>().ok())
        .unwrap_or(0.0);
    let stale_comment = is_stale_comment(&comment);

    let search_text = [
        &title,
        &artist,
        &album,
        &genre,
        &comment,
        &why_made,
        &backstory,
        &radio_reason,
        &music_theme,
        &listener_takeaway,
        &vibe_summary,
        &file_name,
        &channel,
    ]
    .join(" ")
    .to_lowercase();

    Ok(SongRecord {
        path: path.to_string_lossy().into_owned(),
        relative_path,
        file_name,
        channel,
        title,
        artist,
        album,
        genre,
        comment,
        lyrics,
        why_made,
        backstory,
        radio_reason,
        music_theme,
        listener_takeaway,
        vibe_analysis,
        vibe_summary,
        vibe_cached_at_epoch,
        vibe_cache_schema,
        duration_seconds,
        modified_epoch: modified_epoch(path),
        stale_comment,
        blocked_channel,
        search_text,
    })
}

fn tag(tags: &HashMap<String, String>, wanted: &str) -> Option<String> {
    tags.iter()
        .find(|(key, _)| key.eq_ignore_ascii_case(wanted))
        .map(|(_, value)| value.trim().to_owned())
        .filter(|value| !value.is_empty())
}

fn is_stale_comment(comment: &str) -> bool {
    let lower = comment.trim().to_lowercase();
    lower.contains("made with suno")
        || lower.contains("produced with suno")
        || lower.contains("from midori ai radio")
}

fn save_song_metadata_impl(payload: &SaveMetadataRequest) -> Result<SongRecord, String> {
    if !command_exists("ffmpeg") {
        return Err("ffmpeg is required to write MP3 metadata.".to_owned());
    }
    let path = PathBuf::from(&payload.path);
    if !path.is_file() || !is_mp3(&path) {
        return Err(format!("Song is not a readable MP3: {}", path.display()));
    }
    let parent = path
        .parent()
        .ok_or_else(|| format!("Song has no parent directory: {}", path.display()))?;
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("song.mp3");
    let temp = parent.join(format!(
        ".{file_name}.midori-radio-{}.tmp.mp3",
        now_millis()
    ));
    let backup = parent.join(format!(
        ".{file_name}.midori-radio-{}.bak",
        now_millis()
    ));

    let metadata_pairs = [
        ("title", payload.title.as_str()),
        ("artist", payload.artist.as_str()),
        ("album", payload.album.as_str()),
        ("genre", payload.genre.as_str()),
        ("comment", payload.comment.as_str()),
        (TAG_WHY_MADE, payload.why_made.as_str()),
        (TAG_BACKSTORY, payload.backstory.as_str()),
        (TAG_RADIO_REASON, payload.radio_reason.as_str()),
        (TAG_MUSIC_THEME, payload.music_theme.as_str()),
        (TAG_LISTENER_TAKEAWAY, payload.listener_takeaway.as_str()),
    ];

    let mut command = Command::new("ffmpeg");
    command.args(["-hide_banner", "-loglevel", "error", "-y", "-i"]);
    command.arg(&path);
    command.args([
        "-map",
        "0",
        "-map_metadata",
        "0",
        "-c",
        "copy",
        "-id3v2_version",
        "3",
    ]);
    for (key, value) in metadata_pairs {
        command.arg("-metadata");
        command.arg(format!("{key}={value}"));
    }
    command.arg(&temp);

    let output = command
        .output()
        .map_err(|error| format!("Could not start ffmpeg: {error}"))?;
    if !output.status.success() {
        let _ = fs::remove_file(&temp);
        return Err(format!(
            "ffmpeg could not update {}: {}",
            path.display(),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    if let Ok(metadata) = fs::metadata(&path) {
        let _ = fs::set_permissions(&temp, metadata.permissions());
    }

    fs::rename(&path, &backup)
        .map_err(|error| format!("Could not create a safe replacement backup: {error}"))?;
    if let Err(error) = fs::rename(&temp, &path) {
        let _ = fs::rename(&backup, &path);
        let _ = fs::remove_file(&temp);
        return Err(format!("Could not replace the original MP3: {error}"));
    }
    let _ = fs::remove_file(&backup);

    inspect_song_impl(&path, None)
}

fn import_songs_impl(payload: &ImportRequest) -> Result<Vec<SongRecord>, String> {
    let root = PathBuf::from(&payload.root);
    validate_library_root(&root)?;
    validate_channel_name(&payload.channel)?;
    if payload.sources.is_empty() {
        return Err("Choose at least one MP3 to import.".to_owned());
    }

    let destination_dir = root.join(&payload.channel);
    fs::create_dir_all(&destination_dir).map_err(|error| {
        format!(
            "Could not create channel directory {}: {error}",
            destination_dir.display()
        )
    })?;

    let mut imported = Vec::new();
    for source_text in &payload.sources {
        let source = PathBuf::from(source_text);
        if !source.is_file() || !is_mp3(&source) {
            return Err(format!("Import source is not an MP3: {}", source.display()));
        }
        let file_name = source
            .file_name()
            .ok_or_else(|| format!("Import source has no filename: {}", source.display()))?;
        let destination = unique_destination(&destination_dir.join(file_name));
        fs::copy(&source, &destination).map_err(|error| {
            format!(
                "Could not import {} to {}: {error}",
                source.display(),
                destination.display()
            )
        })?;
        imported.push(inspect_song_impl(&destination, Some(&root))?);
    }
    Ok(imported)
}

fn unique_destination(path: &Path) -> PathBuf {
    if !path.exists() {
        return path.to_path_buf();
    }
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let stem = path
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or("song");
    let extension = path
        .extension()
        .and_then(|name| name.to_str())
        .unwrap_or("mp3");
    for index in 2..10_000 {
        let candidate = parent.join(format!("{stem} ({index}).{extension}"));
        if !candidate.exists() {
            return candidate;
        }
    }
    parent.join(format!("{stem}-{}.{}", now_millis(), extension))
}

fn play_song_impl(path: &Path) -> Result<String, String> {
    if !path.is_file() {
        return Err(format!("Song does not exist: {}", path.display()));
    }
    let choices: [(&str, &[&str]); 4] = [
        ("mpv", &["--no-terminal"]),
        ("vlc", &["--started-from-file"]),
        ("ffplay", &["-autoexit", "-nodisp"]),
        ("xdg-open", &[]),
    ];
    for (program, args) in choices {
        if !command_exists(program) {
            continue;
        }
        Command::new(program)
            .args(args)
            .arg(path)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("Could not start {program}: {error}"))?;
        return Ok(program.to_owned());
    }
    Err("No supported player was found. Install mpv, VLC, or ffplay.".to_owned())
}

fn trash_song_impl(path: &Path) -> Result<String, String> {
    if !path.is_file() {
        return Err(format!("Song does not exist: {}", path.display()));
    }

    for program in ["kioclient6", "kioclient", "kioclient5"] {
        if command_exists(program)
            && Command::new(program)
                .arg("move")
                .arg(path)
                .arg("trash:/")
                .status()
                .map(|status| status.success())
                .unwrap_or(false)
        {
            return Ok(program.to_owned());
        }
    }

    if command_exists("gio")
        && Command::new("gio")
            .arg("trash")
            .arg(path)
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    {
        return Ok("gio".to_owned());
    }

    Err("Could not move the song to Trash. KDE KIO and gio both failed or were unavailable."
        .to_owned())
}

fn set_channel_blocked_impl(payload: &ChannelBlockRequest) -> Result<(), String> {
    let root = PathBuf::from(&payload.root);
    validate_library_root(&root)?;
    validate_channel_name(&payload.channel)?;
    let channel = root.join(&payload.channel);
    if !channel.is_dir() {
        return Err(format!("Channel does not exist: {}", channel.display()));
    }
    let marker = channel.join(".blocked");
    if payload.blocked {
        fs::write(&marker, b"Blocked by Midori AI Radio Studio.\n")
            .map_err(|error| format!("Could not write {}: {error}", marker.display()))?;
    } else if marker.exists() {
        fs::remove_file(&marker)
            .map_err(|error| format!("Could not remove {}: {error}", marker.display()))?;
    }
    Ok(())
}

fn record_feedback_impl(payload: &FeedbackRequest) -> Result<FeedbackEntry, String> {
    let prompt_key = payload.prompt_key.trim();
    if !default_prompts().contains_key(prompt_key) {
        return Err(format!("Unknown prompt key: {prompt_key}"));
    }
    if payload.feedback.trim().is_empty() && payload.rating.trim().is_empty() {
        return Err("Add a rating or write feedback before recording it.".to_owned());
    }

    let entry = FeedbackEntry {
        id: format!("{}-{}", now_epoch(), now_millis()),
        created_at_epoch: now_epoch(),
        prompt_key: prompt_key.to_owned(),
        song_path: payload.song_path.trim().to_owned(),
        output: payload.output.trim().to_owned(),
        feedback: payload.feedback.trim().to_owned(),
        rating: payload.rating.trim().to_owned(),
    };

    let path = feedback_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Could not create {}: {error}", parent.display()))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| format!("Could not open {}: {error}", path.display()))?;
    let line = serde_json::to_string(&entry)
        .map_err(|error| format!("Could not serialize feedback: {error}"))?;
    writeln!(file, "{line}")
        .map_err(|error| format!("Could not append feedback: {error}"))?;
    Ok(entry)
}

fn update_prompt_impl(payload: &UpdatePromptRequest) -> Result<PromptUpdateResult, String> {
    let key = payload.prompt_key.trim();
    if !default_prompts().contains_key(key) {
        return Err(format!("Unknown prompt key: {key}"));
    }

    let mut store = load_prompt_store()?;
    let current_prompt = if payload.current_prompt.trim().is_empty() {
        store
            .prompts
            .get(key)
            .cloned()
            .or_else(|| default_prompts().get(key).cloned())
            .unwrap_or_default()
    } else {
        payload.current_prompt.trim().to_owned()
    };

    let mut feedback: Vec<FeedbackEntry> = load_feedback()?
        .into_iter()
        .filter(|entry| entry.prompt_key == key)
        .collect();
    feedback.sort_by_key(|entry| entry.created_at_epoch);
    if feedback.len() > FEEDBACK_CONTEXT_LIMIT {
        feedback = feedback.split_off(feedback.len() - FEEDBACK_CONTEXT_LIMIT);
    }
    if feedback.is_empty() {
        return Err("No recorded feedback exists for this prompt yet.".to_owned());
    }

    backup_prompt_store(&store)?;

    let feedback_text = feedback
        .iter()
        .enumerate()
        .map(|(index, entry)| {
            format!(
                "Example {}\nRating: {}\nOutput: {}\nFeedback: {}",
                index + 1,
                nonempty(&entry.rating, "not rated"),
                nonempty(&entry.output, "not supplied"),
                nonempty(&entry.feedback, "not supplied")
            )
        })
        .collect::<Vec<_>>()
        .join("\n\n");

    let meta_prompt = format!(
        "You maintain one reusable instruction template for Midori AI Radio Studio. Improve the template using the operator feedback below. Preserve the template's purpose and all accuracy constraints. Do not weaken requirements to use confirmed evidence, avoid unsupported facts, keep Midori AI Radio naming exact, or return only the requested deliverable. Resolve repeated feedback into clear general rules instead of mentioning individual songs. Do not include analysis, headings, markdown fences, changelogs, or commentary. Return only the complete replacement prompt.\n\nPrompt key: {key}\n\nCurrent prompt:\n{current_prompt}\n\nOperator feedback:\n{feedback_text}"
    );

    let mut used_model = String::new();
    let mut used_fallback_synthesis = false;
    let updated_prompt = match run_with_model_fallback(
        &payload.root,
        &payload.model,
        &payload.variant,
        &payload.fallback_model,
        &payload.fallback_variant,
        &meta_prompt,
    ) {
        Ok((output, model)) if !output.trim().is_empty() => {
            used_model = model;
            clean_model_output(&output)
        }
        _ => {
            used_fallback_synthesis = true;
            synthesize_prompt_locally(&current_prompt, &feedback)
        }
    };

    store.version = store.version.saturating_add(1);
    store.updated_at_epoch = now_epoch();
    store
        .prompts
        .insert(key.to_owned(), updated_prompt.clone());
    save_json_atomic(&prompts_path(), &store)?;
    prune_prompt_history()?;

    Ok(PromptUpdateResult {
        prompt_key: key.to_owned(),
        prompt: updated_prompt,
        version: store.version,
        updated_at_epoch: store.updated_at_epoch,
        feedback_used: feedback.len(),
        used_model,
        used_fallback_synthesis,
    })
}

fn reset_prompt_impl(prompt_key: &str) -> Result<PromptUpdateResult, String> {
    let defaults = default_prompts();
    let prompt = defaults
        .get(prompt_key)
        .cloned()
        .ok_or_else(|| format!("Unknown prompt key: {prompt_key}"))?;
    let mut store = load_prompt_store()?;
    backup_prompt_store(&store)?;
    store.version = store.version.saturating_add(1);
    store.updated_at_epoch = now_epoch();
    store
        .prompts
        .insert(prompt_key.to_owned(), prompt.clone());
    save_json_atomic(&prompts_path(), &store)?;
    prune_prompt_history()?;
    Ok(PromptUpdateResult {
        prompt_key: prompt_key.to_owned(),
        prompt,
        version: store.version,
        updated_at_epoch: store.updated_at_epoch,
        feedback_used: 0,
        used_model: String::new(),
        used_fallback_synthesis: true,
    })
}

fn run_song_prompt_impl(payload: &RunPromptRequest) -> Result<RunPromptResult, String> {
    let store = load_prompt_store()?;
    let template = store
        .prompts
        .get(payload.prompt_key.trim())
        .cloned()
        .ok_or_else(|| format!("Unknown prompt key: {}", payload.prompt_key))?;
    let song_path = PathBuf::from(&payload.song_path);
    let song = inspect_song_impl(&song_path, Some(Path::new(&payload.root)))?;

    let prompt_preview = format!(
        "{template}\n\nRead the target song's lyrics and metadata before answering. You may inspect related MP3 files inside the selected Midori AI Radio library when the connection is supported by evidence. Never mention this research process.\n\nSong path: {}\nTitle: {}\nArtist: {}\nChannel: {}\nCurrent comment: {}\nWhy made: {}\nBackstory: {}\nRadio reason: {}\nMusic theme: {}\nListener takeaway: {}\nVibe summary: {}\nOperator notes: {}",
        song.path,
        nonempty(&song.title, "unknown"),
        nonempty(&song.artist, "unknown"),
        nonempty(&song.channel, "unknown"),
        nonempty(&song.comment, "none"),
        nonempty(&song.why_made, "none"),
        nonempty(&song.backstory, "none"),
        nonempty(&song.radio_reason, "none"),
        nonempty(&song.music_theme, "none"),
        nonempty(&song.listener_takeaway, "none"),
        nonempty(&song.vibe_summary, "none"),
        nonempty(&payload.notes, "none"),
    );

    match run_with_model_fallback(
        &payload.root,
        &payload.model,
        &payload.variant,
        &payload.fallback_model,
        &payload.fallback_variant,
        &prompt_preview,
    ) {
        Ok((output, model)) => Ok(RunPromptResult {
            output: clean_model_output(&output),
            prompt_preview,
            used_model: model,
            warning: String::new(),
        }),
        Err(error) => Ok(RunPromptResult {
            output: String::new(),
            prompt_preview,
            used_model: String::new(),
            warning: format!(
                "{error} The complete prompt is ready in Prompt Preview for manual use."
            ),
        }),
    }
}

fn backup_prompt_store(store: &PromptStore) -> Result<(), String> {
    let directory = prompt_history_dir();
    fs::create_dir_all(&directory)
        .map_err(|error| format!("Could not create {}: {error}", directory.display()))?;
    let path = directory.join(format!(
        "prompts-v{}-{}.json",
        store.version,
        now_millis()
    ));
    save_json_atomic(&path, store)
}

fn prune_prompt_history() -> Result<(), String> {
    let directory = prompt_history_dir();
    if !directory.is_dir() {
        return Ok(());
    }
    let mut files = fs::read_dir(&directory)
        .map_err(|error| format!("Could not read {}: {error}", directory.display()))?
        .filter_map(Result::ok)
        .filter(|entry| entry.path().is_file())
        .collect::<Vec<_>>();
    files.sort_by_key(|entry| modified_epoch(&entry.path()));
    let remove_count = files.len().saturating_sub(PROMPT_HISTORY_LIMIT);
    for entry in files.into_iter().take(remove_count) {
        let _ = fs::remove_file(entry.path());
    }
    Ok(())
}

fn synthesize_prompt_locally(current_prompt: &str, feedback: &[FeedbackEntry]) -> String {
    let mut rules = Vec::new();
    let mut seen = HashSet::new();
    for entry in feedback.iter().rev() {
        let mut guidance = entry
            .feedback
            .trim()
            .replace('\r', " ")
            .replace('\n', " ");
        if guidance.is_empty() {
            guidance = match entry.rating.trim().to_lowercase().as_str() {
                "too long" => {
                    "Prefer a shorter answer while preserving supported details.".to_owned()
                }
                "too vague" => {
                    "Use more specific supported details from the song evidence.".to_owned()
                }
                "too formal" => "Use a more natural, less formal voice.".to_owned(),
                "wrong facts" => {
                    "Do not state details unless the song or library evidence supports them."
                        .to_owned()
                }
                "good" => {
                    "Preserve the qualities that made the accepted output effective.".to_owned()
                }
                other if !other.is_empty() => {
                    format!("Account for operator rating: {other}.")
                }
                _ => continue,
            };
        }
        if guidance.len() > 280 {
            guidance.truncate(280);
            guidance.push_str("…");
        }
        let normalized = guidance.to_lowercase();
        if seen.insert(normalized) {
            rules.push(guidance);
        }
        if rules.len() >= 8 {
            break;
        }
    }
    rules.reverse();
    if rules.is_empty() {
        return current_prompt.trim().to_owned();
    }
    format!(
        "{}\n\nOperator-learned guidance:\n{}",
        current_prompt.trim(),
        rules
            .into_iter()
            .map(|rule| format!("- {rule}"))
            .collect::<Vec<_>>()
            .join("\n")
    )
}

fn run_with_model_fallback(
    root: &str,
    model: &str,
    variant: &str,
    fallback_model: &str,
    fallback_variant: &str,
    prompt: &str,
) -> Result<(String, String), String> {
    let primary = model.trim();
    if !primary.is_empty() {
        match run_opencode(root, primary, variant, prompt) {
            Ok(output) => return Ok((output, primary.to_owned())),
            Err(primary_error) => {
                let fallback = fallback_model.trim();
                if fallback.is_empty() || fallback == primary {
                    return Err(primary_error);
                }
                return run_opencode(root, fallback, fallback_variant, prompt)
                    .map(|output| (output, fallback.to_owned()))
                    .map_err(|fallback_error| {
                        format!(
                            "Primary model failed: {primary_error}\nFallback model failed: {fallback_error}"
                        )
                    });
            }
        }
    }
    Err("No OpenCode model is configured.".to_owned())
}

fn run_opencode(root: &str, model: &str, variant: &str, prompt: &str) -> Result<String, String> {
    if !command_exists("opencode") {
        return Err("The opencode CLI was not found in PATH.".to_owned());
    }
    let mut command = Command::new("opencode");
    command.arg("run");
    if Path::new(root).is_dir() {
        command.arg("--dir").arg(root);
    }
    if !variant.trim().is_empty() {
        command.arg("--variant").arg(variant.trim());
    }
    command.arg("-m").arg(model.trim());
    command.args(["--thinking", "--format", "json"]);
    command.arg(prompt);

    let output = command
        .output()
        .map_err(|error| format!("Could not start opencode: {error}"))?;
    if !output.status.success() {
        return Err(format!(
            "opencode exited with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut latest = String::new();
    for line in stdout.lines() {
        if let Ok(value) = serde_json::from_str::<Value>(line) {
            if value.get("type").and_then(Value::as_str) == Some("text") {
                if let Some(text) = value
                    .get("part")
                    .and_then(|part| part.get("text"))
                    .and_then(Value::as_str)
                    .or_else(|| value.get("text").and_then(Value::as_str))
                {
                    if !text.trim().is_empty() {
                        latest = text.to_owned();
                    }
                }
            }
        }
    }
    if latest.trim().is_empty() {
        latest = stdout.trim().to_owned();
    }
    if latest.trim().is_empty() {
        return Err("opencode returned no text.".to_owned());
    }
    Ok(latest)
}

fn clean_model_output(output: &str) -> String {
    let think_re = Regex::new(r"(?s)<think>.*?</think>").expect("valid regex");
    let mut cleaned = think_re.replace_all(output, "").trim().to_owned();
    if cleaned.starts_with("```") && cleaned.ends_with("```") {
        cleaned = cleaned
            .trim_start_matches("```")
            .trim_end_matches("```")
            .trim()
            .to_owned();
        if let Some(newline) = cleaned.find('\n') {
            let first_line = &cleaned[..newline];
            if first_line
                .chars()
                .all(|character| character.is_ascii_alphabetic())
            {
                cleaned = cleaned[newline + 1..].trim().to_owned();
            }
        }
    }
    cleaned
}

fn open_path_impl(path: &Path) -> Result<String, String> {
    let target = if path.exists() {
        path.to_path_buf()
    } else {
        fs::create_dir_all(path)
            .map_err(|error| format!("Could not create {}: {error}", path.display()))?;
        path.to_path_buf()
    };

    for program in ["kioclient6", "kioclient", "kioclient5"] {
        if command_exists(program) {
            Command::new(program)
                .arg("exec")
                .arg(&target)
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .map_err(|error| format!("Could not start {program}: {error}"))?;
            return Ok(program.to_owned());
        }
    }
    if command_exists("xdg-open") {
        Command::new("xdg-open")
            .arg(&target)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("Could not start xdg-open: {error}"))?;
        return Ok("xdg-open".to_owned());
    }
    Err("No desktop opener was found.".to_owned())
}

fn command_exists(program: &str) -> bool {
    Command::new("sh")
        .arg("-c")
        .arg("command -v \"$1\" >/dev/null 2>&1")
        .arg("sh")
        .arg(program)
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn validate_library_root(root: &Path) -> Result<(), String> {
    if root.as_os_str().is_empty() {
        return Err("Choose the Midori AI Radio music library folder first.".to_owned());
    }
    if !root.is_dir() {
        return Err(format!("Library folder does not exist: {}", root.display()));
    }
    Ok(())
}

fn validate_channel_name(channel: &str) -> Result<(), String> {
    let path = Path::new(channel);
    if channel.trim().is_empty()
        || path.is_absolute()
        || path.components().count() != 1
        || matches!(
            path.components().next(),
            Some(Component::ParentDir | Component::CurDir)
        )
    {
        return Err("Choose a valid top-level Midori AI Radio channel.".to_owned());
    }
    Ok(())
}

fn is_mp3(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("mp3"))
        .unwrap_or(false)
}

fn nonempty<'a>(value: &'a str, fallback: &'a str) -> &'a str {
    if value.trim().is_empty() {
        fallback
    } else {
        value.trim()
    }
}
