mod codex_runner;
mod config;
mod persistence;
mod types;

use std::collections::BTreeSet;
use std::fs;
use std::io::{self, IsTerminal, Write};
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result, anyhow, bail};
use clap::Parser;
use indicatif::{ProgressBar, ProgressStyle};
use owo_colors::OwoColorize;
use serde::Deserialize;
use serde::de::DeserializeOwned;

use crate::codex_runner::{CodexRunner, CodexTurnResult};
use crate::config::{AppConfig, ResolvedPaths, load_or_init_config};
use crate::persistence::CampaignRuntime;
use crate::types::{
    AgentAction, AgentTurnResponse, DM_ACTOR, HUMAN_ACTOR, PLAYER_AI_ACTORS, RunMode,
    WhisperDecision, all_actor_ids,
};

const DEFAULT_RECENT_VISIBLE_EVENTS: usize = 40;
const NOTE_WINDOW: usize = 12;
const WHISPER_CONTEXT_EVENTS: usize = 24;
const TURN_OUTPUT_REPAIR_RETRIES: usize = 2;
const THEME_OPTIONS: [&str; 10] = [
    "Classic Heroic Fantasy",
    "Grim Dark Fantasy",
    "Political Intrigue",
    "Mystery and Investigation",
    "Monster Hunter Adventure",
    "Pirates and Naval Chaos",
    "Planar Cosmic Weirdness",
    "Feywild Whimsy",
    "Steampunk Frontier",
    "Dungeon Delve Survival",
];

#[derive(Debug, Parser)]
#[command(
    name = "dnd-agent-game",
    about = "Local/remote 6-player DnD prototype with 1 DM and 5 players."
)]
struct Cli {
    #[arg(long, default_value = "config.toml")]
    config: PathBuf,

    #[arg(long)]
    campaign: Option<String>,

    #[arg(long, value_enum)]
    mode: Option<RunMode>,

    #[arg(long, default_value_t = DEFAULT_RECENT_VISIBLE_EVENTS)]
    recent_events: usize,

    #[arg(long)]
    debug: bool,
}

#[derive(Debug, Clone)]
struct WhisperOutcome {
    approved: bool,
    reason: Option<String>,
}

#[derive(Debug, Clone)]
struct ActorTurnOutcome {
    next_actor_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
struct SchedulerStats {
    actor_turn_counts: std::collections::BTreeMap<String, u64>,
    dm_pick_counts: std::collections::BTreeMap<String, u64>,
    consecutive_dm_self_picks: u32,
}

impl SchedulerStats {
    fn note_actor_turn(&mut self, actor_id: &str) {
        *self
            .actor_turn_counts
            .entry(actor_id.to_string())
            .or_insert(0) += 1;
    }

    fn note_dm_pick(&mut self, actor_id: &str) {
        *self.dm_pick_counts.entry(actor_id.to_string()).or_insert(0) += 1;
        if actor_id == DM_ACTOR {
            self.consecutive_dm_self_picks = self.consecutive_dm_self_picks.saturating_add(1);
        } else {
            self.consecutive_dm_self_picks = 0;
        }
    }

    fn dm_pick_count(&self, actor_id: &str) -> u64 {
        *self.dm_pick_counts.get(actor_id).unwrap_or(&0)
    }
}

#[derive(Debug, Deserialize)]
struct IdentityProposal {
    name: String,
    pronouns: String,
}

#[derive(Debug, Deserialize)]
struct IdentityDecision {
    final_name: String,
    final_pronouns: String,
    #[serde(default)]
    reason: Option<String>,
}

#[derive(Debug, Clone)]
struct HumanIdentity {
    name: String,
    pronouns: String,
    prompt_tag: String,
}

impl HumanIdentity {
    fn new(name: String, pronouns: String) -> Self {
        let prompt_tag = make_prompt_tag(&name);
        Self {
            name,
            pronouns,
            prompt_tag,
        }
    }
}

fn main() {
    if let Err(err) = run() {
        eprintln!("error: {err:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let app_config = load_or_init_config(&cli.config)?;
    let paths = app_config.resolve_paths(&cli.config)?;
    fs::create_dir_all(&paths.campaign_root)
        .with_context(|| format!("failed to create {}", paths.campaign_root.display()))?;

    let show_debug = cli.debug || app_config.runtime.show_debug_default;
    let (mut campaign, is_new) = select_or_create_campaign(&cli, &app_config, &paths)?;
    let human = prompt_human_identity()?;

    let runner = CodexRunner::new(
        campaign.state.mode,
        app_config.clone(),
        paths.clone(),
        std::env::current_dir().context("failed to detect current directory")?,
    )?;

    campaign.set_actor_identity(
        HUMAN_ACTOR,
        human.name.clone(),
        human.pronouns.clone(),
        true,
    )?;

    print_startup_summary(&campaign, &runner, &paths, &human, show_debug);

    if is_new {
        initialize_new_campaign(&mut campaign, &human)?;
    }

    setup_ai_identities(&runner, &mut campaign, &human, show_debug)?;

    game_loop(
        &runner,
        &mut campaign,
        &human,
        show_debug,
        cli.recent_events.max(10),
    )?;

    Ok(())
}

fn prompt_human_identity() -> Result<HumanIdentity> {
    println!("{}", "Player identity setup".bold().bright_blue());

    let raw_name = prompt_line("Your name [Luna]: ")?;
    let display_name = if raw_name.trim().is_empty() {
        "Luna".to_string()
    } else {
        normalize_display_name(raw_name.trim())
    };

    let raw_pronouns = prompt_line("Pronouns [she/her]: ")?;
    let pronouns = if raw_pronouns.trim().is_empty() {
        "she/her".to_string()
    } else {
        raw_pronouns.trim().to_string()
    };

    Ok(HumanIdentity::new(display_name, pronouns))
}

fn normalize_display_name(input: &str) -> String {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return "Luna".to_string();
    }

    let mut chars = trimmed.chars();
    let Some(first) = chars.next() else {
        return "Luna".to_string();
    };
    format!("{}{}", first.to_uppercase(), chars.as_str())
}

fn normalize_name_with_fallback(input: &str, fallback: &str) -> String {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return fallback.to_string();
    }

    let mut chars = trimmed.chars();
    let Some(first) = chars.next() else {
        return fallback.to_string();
    };
    format!("{}{}", first.to_uppercase(), chars.as_str())
}

fn normalize_pronouns(input: &str) -> String {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        "they/them".to_string()
    } else {
        trimmed.to_string()
    }
}

fn select_or_create_campaign(
    cli: &Cli,
    app_config: &AppConfig,
    paths: &ResolvedPaths,
) -> Result<(CampaignRuntime, bool)> {
    if let Some(id) = &cli.campaign {
        let runtime = CampaignRuntime::load(&paths.campaign_root, id)?;
        if let Some(mode) = cli.mode
            && mode != runtime.state.mode
        {
            println!(
                "Campaign {} already uses mode `{}`; ignoring requested mode `{}`.",
                runtime.campaign_id, runtime.state.mode, mode
            );
        }
        return Ok((runtime, false));
    }

    let existing = CampaignRuntime::list_campaign_ids(&paths.campaign_root)?;
    if existing.is_empty() {
        let mode = choose_mode_for_new_campaign(cli.mode, app_config.runtime.default_mode)?;
        let runtime = CampaignRuntime::create_new(&paths.campaign_root, mode)?;
        return Ok((runtime, true));
    }

    println!("Existing campaigns:");
    for (idx, id) in existing.iter().enumerate() {
        println!("  {}. {}", idx + 1, id);
    }
    println!("  n. Create a new campaign");

    loop {
        let raw = prompt_line("Choose a campaign number, campaign id, or `n`: ")?;
        let trimmed = raw.trim();
        if trimmed.eq_ignore_ascii_case("n") || trimmed.eq_ignore_ascii_case("new") {
            let mode = choose_mode_for_new_campaign(cli.mode, app_config.runtime.default_mode)?;
            let runtime = CampaignRuntime::create_new(&paths.campaign_root, mode)?;
            return Ok((runtime, true));
        }

        if let Ok(index) = trimmed.parse::<usize>()
            && (1..=existing.len()).contains(&index)
        {
            let id = &existing[index - 1];
            let runtime = CampaignRuntime::load(&paths.campaign_root, id)?;
            return Ok((runtime, false));
        }

        if existing.iter().any(|id| id == trimmed) {
            let runtime = CampaignRuntime::load(&paths.campaign_root, trimmed)?;
            return Ok((runtime, false));
        }

        println!("Could not match that selection. Try again.");
    }
}

fn choose_mode_for_new_campaign(forced: Option<RunMode>, default_mode: RunMode) -> Result<RunMode> {
    if let Some(mode) = forced {
        return Ok(mode);
    }

    println!(
        "Run mode for new campaign: local or remote (default: {}).",
        default_mode
    );
    loop {
        let raw = prompt_line("Mode [local/remote]: ")?;
        let trimmed = raw.trim().to_ascii_lowercase();
        if trimmed.is_empty() {
            return Ok(default_mode);
        }
        match trimmed.as_str() {
            "l" | "local" => return Ok(RunMode::Local),
            "r" | "remote" => return Ok(RunMode::Remote),
            _ => println!("Please enter `local`, `remote`, or press Enter for default."),
        }
    }
}

fn print_startup_summary(
    campaign: &CampaignRuntime,
    runner: &CodexRunner,
    paths: &ResolvedPaths,
    human: &HumanIdentity,
    show_debug: bool,
) {
    println!(
        "{} {} | {} {} | {} {} | {} ({})",
        "Campaign".bold().bright_blue(),
        campaign.campaign_id,
        "mode".bold().bright_blue(),
        campaign.state.mode,
        "save".bold().bright_blue(),
        campaign.root.display(),
        human.name.bold().bright_cyan(),
        human.pronouns
    );
    if show_debug {
        println!(
            "{} {} | {} {}",
            "debug".bright_yellow().bold(),
            "enabled".bright_yellow(),
            "campaign_root".bright_yellow().bold(),
            paths.campaign_root.display()
        );
        println!("{} {}", "codex_mode".bright_yellow().bold(), runner.mode());
    }
}

fn initialize_new_campaign(campaign: &mut CampaignRuntime, human: &HumanIdentity) -> Result<()> {
    println!();
    println!(
        "{}",
        "Theme checklist. Mark what to remove:".bold().bright_blue()
    );
    for (idx, theme) in THEME_OPTIONS.iter().enumerate() {
        println!("  [ ] {}. {}", idx + 1, theme);
    }
    println!("Type numbers to remove (comma-separated), or Enter to keep all.");

    let kept = choose_theme_shortlist()?;
    let kept_csv = kept.join(", ");

    campaign.append_note(
        DM_ACTOR,
        &format!(
            "Theme shortlist from {}: {kept_csv}. Ask all players what they want to play before opening scene 1, then set final tone.",
            human.name
        ),
    )?;
    campaign.add_public_message(
        "system",
        "A new campaign starts now. DM should ask each player what they want to play.",
    )?;
    campaign.append_note(
        HUMAN_ACTOR,
        "Player commands: `/w target message`, `/pass`, `/history`, `/quit`.",
    )?;
    campaign.append_note(
        DM_ACTOR,
        &format!(
            "Player 5 identity for this session: {} ({})",
            human.name, human.pronouns
        ),
    )?;

    println!("{}", "Kept themes:".bold().green());
    for theme in &kept {
        println!("  - {}", theme.green());
    }

    Ok(())
}

fn choose_theme_shortlist() -> Result<Vec<String>> {
    loop {
        let raw = prompt_line("Remove themes by number: ")?;
        let trimmed = raw.trim();
        if trimmed.is_empty() {
            return Ok(THEME_OPTIONS.iter().map(|s| s.to_string()).collect());
        }

        let mut removed = BTreeSet::new();
        let mut parse_failed = false;
        for token in trimmed.split(',') {
            let t = token.trim();
            if t.is_empty() {
                continue;
            }
            match t.parse::<usize>() {
                Ok(n) if (1..=THEME_OPTIONS.len()).contains(&n) => {
                    removed.insert(n - 1);
                }
                _ => {
                    parse_failed = true;
                    break;
                }
            }
        }

        if parse_failed {
            println!("Invalid list. Example: `2,5,9`.");
            continue;
        }

        let kept: Vec<String> = THEME_OPTIONS
            .iter()
            .enumerate()
            .filter_map(|(idx, theme)| {
                if removed.contains(&idx) {
                    None
                } else {
                    Some((*theme).to_string())
                }
            })
            .collect();

        if kept.is_empty() {
            println!("At least one theme must remain.");
            continue;
        }

        return Ok(kept);
    }
}

fn setup_ai_identities(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    human: &HumanIdentity,
    show_debug: bool,
) -> Result<()> {
    let pending: Vec<&str> = PLAYER_AI_ACTORS
        .iter()
        .copied()
        .filter(|actor_id| !campaign.identity_is_approved(actor_id))
        .collect();
    if pending.is_empty() {
        return Ok(());
    }

    println!();
    println!(
        "{}",
        "Player identity setup (DM finalizes names/pronouns)"
            .bold()
            .bright_blue()
    );

    for actor_id in pending {
        let previous_label = campaign.actor_display_name(actor_id);
        let proposal = collect_identity_proposal(runner, campaign, actor_id, show_debug, human)?;
        let decision =
            collect_dm_identity_decision(runner, campaign, actor_id, &proposal, show_debug, human)?;

        let final_name =
            normalize_name_with_fallback(decision.final_name.trim(), proposal.name.as_str());
        let final_pronouns = normalize_pronouns(decision.final_pronouns.trim());
        campaign.set_actor_identity(actor_id, final_name.clone(), final_pronouns.clone(), true)?;

        campaign.append_note(
            DM_ACTOR,
            &format!(
                "Finalized identity for {}: {} ({})",
                actor_id, final_name, final_pronouns
            ),
        )?;
        if let Some(reason) = decision.reason
            && !reason.trim().is_empty()
        {
            campaign.append_note(
                DM_ACTOR,
                &format!("Identity choice reason for {}: {}", actor_id, reason.trim()),
            )?;
        }

        println!(
            "{} {} {} ({})",
            previous_label.bright_black(),
            "->".bright_black(),
            final_name.bold(),
            final_pronouns
        );
    }

    Ok(())
}

fn collect_identity_proposal(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    actor_id: &str,
    show_debug: bool,
    human: &HumanIdentity,
) -> Result<IdentityProposal> {
    let mut prompt = build_identity_proposal_prompt(campaign, actor_id, human);
    let mut next_thread = campaign.get_thread_id(actor_id);

    for attempt in 0..=TURN_OUTPUT_REPAIR_RETRIES {
        let phase = if attempt == 0 {
            "identity proposal"
        } else {
            "identity proposal repair"
        };
        let subject = format!("{} ({})", actor_label(campaign, actor_id, human), phase);
        let result = run_with_spinner(&subject, || {
            runner.run_identity_proposal(actor_id, &prompt, next_thread.as_deref())
        })?;

        if let Some(thread_id) = result.thread_id.clone() {
            campaign.set_thread_id(actor_id, thread_id.clone())?;
            next_thread = Some(thread_id);
        }
        campaign.set_last_message(actor_id, result.last_message.clone())?;

        if show_debug {
            print_debug_turn(actor_id, &result);
        }

        match parse_schema_json::<IdentityProposal>(&result.last_message) {
            Ok(parsed) => {
                let fallback = campaign.actor_display_name(actor_id);
                let name = normalize_name_with_fallback(parsed.name.trim(), &fallback);
                let pronouns = normalize_pronouns(parsed.pronouns.trim());
                return Ok(IdentityProposal { name, pronouns });
            }
            Err(err) => {
                if attempt >= TURN_OUTPUT_REPAIR_RETRIES {
                    return Err(anyhow!(
                        "{} identity proposal invalid after {} retries: {}",
                        actor_label(campaign, actor_id, human),
                        TURN_OUTPUT_REPAIR_RETRIES,
                        err
                    ));
                }
                prompt = build_identity_proposal_repair_prompt(actor_id, &result.last_message);
            }
        }
    }

    Err(anyhow!("identity proposal retries exhausted"))
}

fn collect_dm_identity_decision(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    actor_id: &str,
    proposal: &IdentityProposal,
    show_debug: bool,
    human: &HumanIdentity,
) -> Result<IdentityDecision> {
    let mut prompt = build_identity_decision_prompt(campaign, actor_id, proposal, human);
    let mut dm_thread = campaign.get_thread_id(DM_ACTOR);

    for attempt in 0..=TURN_OUTPUT_REPAIR_RETRIES {
        let phase = if attempt == 0 {
            "identity decision"
        } else {
            "identity decision repair"
        };
        let subject = format!("DM ({})", phase);
        let result = run_with_spinner(&subject, || {
            runner.run_identity_decision(&prompt, dm_thread.as_deref())
        })?;

        if let Some(thread_id) = result.thread_id.clone() {
            campaign.set_thread_id(DM_ACTOR, thread_id.clone())?;
            dm_thread = Some(thread_id);
        }
        campaign.set_last_message(DM_ACTOR, result.last_message.clone())?;

        if show_debug {
            print_debug_turn("dm_identity_decision", &result);
        }

        match parse_schema_json::<IdentityDecision>(&result.last_message) {
            Ok(parsed) => {
                let final_name =
                    normalize_name_with_fallback(parsed.final_name.trim(), proposal.name.as_str());
                let final_pronouns = normalize_pronouns(parsed.final_pronouns.trim());
                return Ok(IdentityDecision {
                    final_name,
                    final_pronouns,
                    reason: parsed.reason,
                });
            }
            Err(err) => {
                if attempt >= TURN_OUTPUT_REPAIR_RETRIES {
                    return Err(anyhow!(
                        "DM identity decision invalid after {} retries: {}",
                        TURN_OUTPUT_REPAIR_RETRIES,
                        err
                    ));
                }
                prompt = build_identity_decision_repair_prompt(actor_id, &result.last_message);
            }
        }
    }

    Err(anyhow!("identity decision retries exhausted"))
}

fn build_identity_proposal_prompt(
    campaign: &CampaignRuntime,
    actor_id: &str,
    human: &HumanIdentity,
) -> String {
    let current = campaign.actor_display_name(actor_id);
    format!(
        "You are actor `{}` in DnD setup. Your temporary label is `{}`.\n\
         Propose your player identity.\n\
         Return ONLY JSON:\n\
         {{\"name\":\"string\",\"pronouns\":\"string\"}}\n\
         Rules:\n\
         - Keep the name concise (1-3 words).\n\
         - Do not include markdown.\n\
         - Keep pronouns concise.\n\
         - Player 5 is {} ({}).\n",
        actor_id, current, human.name, human.pronouns
    )
}

fn build_identity_decision_prompt(
    campaign: &CampaignRuntime,
    actor_id: &str,
    proposal: &IdentityProposal,
    human: &HumanIdentity,
) -> String {
    let current = campaign.actor_display_name(actor_id);
    format!(
        "You are DM finalizing player identities for this campaign.\n\
         Actor: {} (current label `{}`)\n\
         Proposed name: {}\n\
         Proposed pronouns: {}\n\
         Player 5: {} ({})\n\
         Return ONLY JSON:\n\
         {{\"final_name\":\"string\",\"final_pronouns\":\"string\",\"reason\":\"optional string\"}}\n\
         Keep it concise and ready for gameplay.",
        actor_id, current, proposal.name, proposal.pronouns, human.name, human.pronouns
    )
}

fn build_identity_proposal_repair_prompt(actor_id: &str, bad_output: &str) -> String {
    format!(
        "Your identity proposal for actor `{}` was invalid.\n\
         Return ONLY JSON:\n\
         {{\"name\":\"string\",\"pronouns\":\"string\"}}\n\
         Previous invalid output:\n{}",
        actor_id,
        truncate(bad_output, 800)
    )
}

fn build_identity_decision_repair_prompt(actor_id: &str, bad_output: &str) -> String {
    format!(
        "Your identity decision for actor `{}` was invalid.\n\
         Return ONLY JSON:\n\
         {{\"final_name\":\"string\",\"final_pronouns\":\"string\",\"reason\":\"optional string\"}}\n\
         Previous invalid output:\n{}",
        actor_id,
        truncate(bad_output, 800)
    )
}

fn game_loop(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    human: &HumanIdentity,
    show_debug: bool,
    recent_events: usize,
) -> Result<()> {
    let mut current_actor = DM_ACTOR.to_string();
    let mut stats = SchedulerStats::default();

    loop {
        if current_actor == HUMAN_ACTOR {
            if !run_human_turn(runner, campaign, human, show_debug, recent_events)? {
                println!("{}", "Session ended by player.".bright_yellow());
                break;
            }
            stats.note_actor_turn(HUMAN_ACTOR);
            current_actor = DM_ACTOR.to_string();
            continue;
        }

        let dm_scheduler_hint = if current_actor == DM_ACTOR {
            Some(build_dm_scheduler_hint(campaign, human, &stats))
        } else {
            None
        };

        match run_actor_turn_with_hint(
            runner,
            campaign,
            &current_actor,
            human,
            show_debug,
            recent_events,
            dm_scheduler_hint.as_deref(),
        ) {
            Ok(outcome) => {
                stats.note_actor_turn(&current_actor);
                if current_actor == DM_ACTOR {
                    campaign.bump_round()?;
                    let Some(next_actor) = outcome.next_actor_id else {
                        println!(
                            "{}",
                            "DM turn finished without next_actor_id; scheduler halted."
                                .red()
                                .bold()
                        );
                        if !prompt_yes_no("Retry DM turn? [Y/n]: ", true)? {
                            break;
                        }
                        continue;
                    };
                    stats.note_dm_pick(&next_actor);
                    println!(
                        "{} {}",
                        "DM selected next actor:".bright_black(),
                        styled_actor_label(campaign, &next_actor, human)
                    );
                    current_actor = next_actor;
                } else {
                    current_actor = DM_ACTOR.to_string();
                }
            }
            Err(err) => {
                if current_actor == DM_ACTOR {
                    println!("{} {err:#}", "DM turn failed:".red().bold());
                    if !prompt_yes_no("Retry DM turn? [Y/n]: ", true)? {
                        break;
                    }
                } else {
                    println!(
                        "{} turn failed: {err:#}",
                        styled_actor_label(campaign, &current_actor, human)
                            .red()
                            .bold()
                    );
                    if !prompt_yes_no("Continue and return to DM? [y/N]: ", false)? {
                        return Err(err);
                    }
                    current_actor = DM_ACTOR.to_string();
                }
            }
        }
    }

    Ok(())
}

fn build_dm_scheduler_hint(
    campaign: &CampaignRuntime,
    human: &HumanIdentity,
    stats: &SchedulerStats,
) -> String {
    let mut lines = vec![
        "- Turn selection is your call; this guidance is advisory only.".to_string(),
        "- Prefer less-used actors when one actor has dominated spotlight, unless the scene needs otherwise.".to_string(),
    ];

    let mut non_dm_counts: Vec<(String, u64)> = all_actor_ids()
        .into_iter()
        .filter(|id| *id != DM_ACTOR)
        .map(|id| (id.to_string(), stats.dm_pick_count(id)))
        .collect();
    non_dm_counts.sort_by(|a, b| a.1.cmp(&b.1));

    if let (Some((least_actor, least_count)), Some((most_actor, most_count))) =
        (non_dm_counts.first(), non_dm_counts.last())
        && most_count.saturating_sub(*least_count) >= 3
    {
        lines.push(format!(
            "- Spotlight gap detected: {} has {} picks, {} has {} picks.",
            actor_label(campaign, most_actor, human),
            most_count,
            actor_label(campaign, least_actor, human),
            least_count
        ));
    }

    if stats.consecutive_dm_self_picks >= 3 {
        lines.push(format!(
            "- DM self-pick streak is {}. Consider handing the spotlight to another actor if possible.",
            stats.consecutive_dm_self_picks
        ));
    }

    let picked_human = stats.dm_pick_count(HUMAN_ACTOR);
    lines.push(format!(
        "- Current DM pick counts this run: player5={}, p1={}, p2={}, p3={}, p4={}, dm_self={}.",
        picked_human,
        stats.dm_pick_count(PLAYER_AI_ACTORS[0]),
        stats.dm_pick_count(PLAYER_AI_ACTORS[1]),
        stats.dm_pick_count(PLAYER_AI_ACTORS[2]),
        stats.dm_pick_count(PLAYER_AI_ACTORS[3]),
        stats.dm_pick_count(DM_ACTOR),
    ));

    lines.join("\n")
}

fn run_actor_turn_with_hint(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    actor_id: &str,
    human: &HumanIdentity,
    show_debug: bool,
    recent_events: usize,
    dm_scheduler_hint: Option<&str>,
) -> Result<ActorTurnOutcome> {
    let mut prompt =
        build_actor_turn_prompt(campaign, actor_id, human, recent_events, dm_scheduler_hint)?;
    let mut next_thread = campaign.get_thread_id(actor_id);

    for attempt in 0..=TURN_OUTPUT_REPAIR_RETRIES {
        let phase = if attempt == 0 {
            "thinking"
        } else {
            "repairing format"
        };
        let subject = format!("{} ({})", actor_label(campaign, actor_id, human), phase);
        let result = run_with_spinner(&subject, || {
            runner.run_actor_turn(actor_id, &prompt, next_thread.as_deref())
        })?;

        if let Some(thread_id) = result.thread_id.clone() {
            campaign.set_thread_id(actor_id, thread_id.clone())?;
            next_thread = Some(thread_id);
        }
        campaign.set_last_message(actor_id, result.last_message.clone())?;

        if show_debug {
            print_debug_turn(actor_id, &result);
        }

        match parse_agent_turn_response(&result.last_message) {
            Ok(response) => {
                let next_actor_id = if actor_id == DM_ACTOR {
                    let raw = response.next_actor_id.clone().ok_or_else(|| {
                        anyhow!("DM output must include `next_actor_id` every turn")
                    })?;
                    let resolved = resolve_actor_id(&raw, campaign, human)
                        .ok_or_else(|| anyhow!("Invalid DM next actor `{}`", raw))?;
                    Some(resolved.to_string())
                } else {
                    None
                };

                if !response.public_message.trim().is_empty() {
                    campaign.add_public_message(actor_id, response.public_message.trim())?;
                    println!(
                        "{}: {}",
                        styled_actor_label(campaign, actor_id, human),
                        response.public_message.trim()
                    );
                }

                if let Some(note) = &response.note
                    && !note.trim().is_empty()
                {
                    campaign.append_note(actor_id, note.trim())?;
                }

                handle_actions(
                    runner,
                    campaign,
                    actor_id,
                    human,
                    &response.actions,
                    show_debug,
                    recent_events,
                )?;

                return Ok(ActorTurnOutcome { next_actor_id });
            }
            Err(err) => {
                if attempt >= TURN_OUTPUT_REPAIR_RETRIES {
                    if actor_id == DM_ACTOR {
                        return Err(anyhow!(
                            "DM output invalid after {} retries: {}",
                            TURN_OUTPUT_REPAIR_RETRIES,
                            err
                        ));
                    }
                    campaign.append_note(
                        DM_ACTOR,
                        &format!(
                            "{} produced invalid turn output after {} retries; output suppressed.",
                            actor_label(campaign, actor_id, human),
                            TURN_OUTPUT_REPAIR_RETRIES
                        ),
                    )?;
                    if show_debug {
                        println!(
                            "[debug:{}] invalid output suppressed: {}",
                            actor_id,
                            truncate(&err.to_string(), 200)
                        );
                    }
                    return Ok(ActorTurnOutcome {
                        next_actor_id: None,
                    });
                }

                prompt = build_repair_prompt(actor_id, actor_id == DM_ACTOR, &result.last_message);
            }
        }
    }

    Ok(ActorTurnOutcome {
        next_actor_id: None,
    })
}

fn handle_actions(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    actor_id: &str,
    human: &HumanIdentity,
    actions: &[AgentAction],
    show_debug: bool,
    recent_events: usize,
) -> Result<()> {
    for action in actions {
        match action {
            AgentAction::RequestMessagePlayer {
                target,
                targets,
                message,
                reason,
            } => {
                let mut requested_targets: Vec<String> = vec![];
                if let Some(single_target) = target {
                    if !single_target.trim().is_empty() {
                        requested_targets.push(single_target.trim().to_string());
                    }
                }
                for raw in targets {
                    if !raw.trim().is_empty() {
                        requested_targets.push(raw.trim().to_string());
                    }
                }

                if requested_targets.is_empty() {
                    campaign.append_note(
                        actor_id,
                        "Whisper request missing `target` or `targets`; request skipped.",
                    )?;
                    continue;
                }

                let mut invalid_targets: Vec<String> = vec![];
                let mut seen = BTreeSet::new();
                let mut resolved_targets: Vec<String> = vec![];
                let mut skipped_self_count: usize = 0;

                for raw_target in requested_targets {
                    let Some(resolved) = resolve_actor_id(&raw_target, campaign, human) else {
                        invalid_targets.push(raw_target);
                        continue;
                    };

                    if resolved == actor_id {
                        skipped_self_count = skipped_self_count.saturating_add(1);
                        continue;
                    }

                    if seen.insert(resolved.to_string()) {
                        resolved_targets.push(resolved.to_string());
                    }
                }

                if !invalid_targets.is_empty() {
                    campaign.append_note(
                        actor_id,
                        &format!(
                            "Invalid whisper targets skipped: {}. Valid targets: {}",
                            invalid_targets.join(", "),
                            valid_targets_csv(campaign, actor_id, human)
                        ),
                    )?;
                }

                if skipped_self_count > 0 {
                    campaign.append_note(
                        actor_id,
                        "Whisper target cannot include sender; self targets were skipped.",
                    )?;
                }

                if resolved_targets.is_empty() {
                    campaign.append_note(
                        actor_id,
                        "Whisper request had no valid targets after filtering; request skipped.",
                    )?;
                    continue;
                }

                let outcome = evaluate_whisper_request_batch(
                    runner,
                    campaign,
                    actor_id,
                    &resolved_targets,
                    message,
                    reason.as_deref(),
                    human,
                    show_debug,
                    recent_events,
                )?;
                finalize_whisper_outcome_batch(
                    campaign,
                    actor_id,
                    &resolved_targets,
                    message,
                    human,
                    outcome,
                )?;
            }
            AgentAction::NoteWrite { text } => {
                if !text.trim().is_empty() {
                    campaign.append_note(actor_id, text.trim())?;
                }
            }
        }
    }
    Ok(())
}

fn evaluate_whisper_request_batch(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    sender: &str,
    targets: &[String],
    message: &str,
    reason: Option<&str>,
    human: &HumanIdentity,
    show_debug: bool,
    recent_events: usize,
) -> Result<WhisperOutcome> {
    let dm_thread = campaign.get_thread_id(DM_ACTOR);
    let prompt =
        build_dm_whisper_prompt(campaign, sender, targets, message, reason, recent_events)?;
    let target_label = format_target_labels(campaign, targets, human);
    let result = run_with_spinner(
        &format!(
            "DM whisper gate ({} -> {})",
            actor_label(campaign, sender, human),
            target_label
        ),
        || runner.run_dm_whisper_approval(&prompt, dm_thread.as_deref()),
    )?;

    if let Some(thread_id) = result.thread_id.clone() {
        campaign.set_thread_id(DM_ACTOR, thread_id)?;
    }
    campaign.set_last_message(DM_ACTOR, result.last_message.clone())?;

    if show_debug {
        print_debug_turn("dm_whisper_gate", &result);
    }

    let decision = match parse_schema_json::<WhisperDecision>(&result.last_message) {
        Ok(parsed) => parsed,
        Err(_) => WhisperDecision {
            approve: false,
            reason: Some("DM whisper decision could not be parsed as JSON.".to_string()),
        },
    };

    Ok(WhisperOutcome {
        approved: decision.approve,
        reason: decision.reason,
    })
}

fn finalize_whisper_outcome_batch(
    campaign: &mut CampaignRuntime,
    sender: &str,
    targets: &[String],
    message: &str,
    human: &HumanIdentity,
    outcome: WhisperOutcome,
) -> Result<()> {
    let target_label = format_target_labels(campaign, targets, human);
    let includes_human = sender == HUMAN_ACTOR || targets.iter().any(|t| t == HUMAN_ACTOR);

    if outcome.approved {
        for target in targets {
            campaign.add_whisper(sender, target, message)?;
        }
        if includes_human {
            println!(
                "{} {} -> {}: {}",
                "[whisper approved]".green().bold(),
                styled_actor_label(campaign, sender, human),
                target_label,
                message
            );
        } else {
            println!(
                "{} {} -> {}",
                "[whisper approved]".green().bold(),
                styled_actor_label(campaign, sender, human),
                target_label
            );
        }
    } else {
        let reason = outcome
            .reason
            .unwrap_or_else(|| "No reason supplied.".to_string());
        campaign.append_note(
            sender,
            &format!(
                "DM denied whisper to {}. Reason: {}",
                format_target_plain(campaign, targets, human),
                reason
            ),
        )?;
        println!(
            "{} {} -> {} ({})",
            "[whisper denied]".red().bold(),
            styled_actor_label(campaign, sender, human),
            target_label,
            reason
        );
    }
    Ok(())
}

fn run_human_turn(
    runner: &CodexRunner,
    campaign: &mut CampaignRuntime,
    human: &HumanIdentity,
    show_debug: bool,
    recent_events: usize,
) -> Result<bool> {
    println!(
        "{}",
        format!("Your turn, {}. `/help` shows commands.", human.name)
            .bold()
            .cyan()
    );

    loop {
        let input = prompt_line(&format!("{}> ", human.prompt_tag))?;
        let trimmed = input.trim();

        if trimmed.is_empty() {
            println!(
                "{}",
                "Enter a message, or type `/pass` to skip.".bright_black()
            );
            continue;
        }

        if trimmed.eq_ignore_ascii_case("/pass") {
            println!("{}", "You pass this turn.".bright_yellow());
            return Ok(true);
        }

        if trimmed.eq_ignore_ascii_case("/quit") || trimmed.eq_ignore_ascii_case("/exit") {
            return Ok(false);
        }

        if trimmed.eq_ignore_ascii_case("/help") {
            print_human_help(campaign, human);
            continue;
        }

        if trimmed.eq_ignore_ascii_case("/history") {
            print_human_history(campaign, human, recent_events)?;
            continue;
        }

        if trimmed.starts_with("/w ") || trimmed.starts_with("/whisper ") {
            let (target_token, message) = parse_human_whisper_command(trimmed)?;
            let Some(target_id) = resolve_actor_id(&target_token, campaign, human) else {
                println!(
                    "Unknown whisper target `{}`. Valid targets: {}",
                    target_token,
                    valid_targets_csv(campaign, HUMAN_ACTOR, human)
                );
                continue;
            };
            if target_id == HUMAN_ACTOR {
                println!("Whisper target cannot be yourself.");
                continue;
            }

            let target_ids = vec![target_id.to_string()];
            let outcome = evaluate_whisper_request_batch(
                runner,
                campaign,
                HUMAN_ACTOR,
                &target_ids,
                &message,
                None,
                human,
                show_debug,
                recent_events,
            )?;
            finalize_whisper_outcome_batch(
                campaign,
                HUMAN_ACTOR,
                &target_ids,
                &message,
                human,
                outcome,
            )?;
            return Ok(true);
        }

        hide_previous_input_line();
        campaign.add_public_message(HUMAN_ACTOR, trimmed)?;
        println!(
            "{}: {}",
            styled_actor_label(campaign, HUMAN_ACTOR, human),
            trimmed
        );
        return Ok(true);
    }
}

fn parse_human_whisper_command(input: &str) -> Result<(String, String)> {
    let mut parts = input.splitn(3, ' ');
    let command = parts.next().unwrap_or_default();
    let target = parts.next().unwrap_or_default().trim();
    let message = parts.next().unwrap_or_default().trim();

    if !(command.eq_ignore_ascii_case("/w") || command.eq_ignore_ascii_case("/whisper")) {
        bail!("Whisper command must start with `/w` or `/whisper`.");
    }
    if target.is_empty() || message.is_empty() {
        bail!("Usage: /w targetplayername message");
    }
    Ok((target.to_string(), message.to_string()))
}

fn print_human_help(campaign: &CampaignRuntime, human: &HumanIdentity) {
    println!("{}", "Commands:".bold().bright_blue());
    println!("  /w targetplayername message  send a DM-approved whisper");
    println!("  /history                     show your visible recent events");
    println!("  /pass                        skip this turn");
    println!("  /quit                        end the session loop");
    println!("  (plain text)                 public in-character message");
    println!(
        "Current player identity: {} ({})",
        human.name.bold().bright_cyan(),
        human.pronouns
    );
    println!(
        "Whisper targets: {}",
        valid_targets_csv(campaign, HUMAN_ACTOR, human)
    );
}

fn print_human_history(
    campaign: &CampaignRuntime,
    human: &HumanIdentity,
    recent_events: usize,
) -> Result<()> {
    let events = campaign.visible_events_for_actor(HUMAN_ACTOR, recent_events)?;
    if events.is_empty() {
        println!("{}", "No visible events yet.".bright_black());
        return Ok(());
    }
    println!(
        "{}",
        format!("Recent events visible to {}:", human.name)
            .bold()
            .bright_blue()
    );
    for evt in events {
        println!(
            "  [{}] {}: {}",
            evt.timestamp,
            actor_label(campaign, &evt.speaker, human),
            evt.message
        );
    }
    Ok(())
}

fn build_actor_turn_prompt(
    campaign: &CampaignRuntime,
    actor_id: &str,
    human: &HumanIdentity,
    recent_events: usize,
    dm_scheduler_hint: Option<&str>,
) -> Result<String> {
    let visible_events = campaign.visible_events_for_actor(actor_id, recent_events)?;
    let notes = campaign.read_notes(actor_id)?;
    let sheet = campaign.read_character_sheet(actor_id)?;

    let note_start = notes.entries.len().saturating_sub(NOTE_WINDOW);
    let recent_notes = &notes.entries[note_start..];

    let role_guidance = if actor_id == DM_ACTOR {
        "Role guidance (DM):\n\
         - You are the Dungeon Master. Keep pacing tight and ask clarifying questions in-character.\n\
         - Ask each player what they want to play when uncertain about party direction.\n\
         - Adjudicate outcomes; do not reveal hidden info publicly unless earned.\n\
         - For private communication use `request_message_player` actions.\n\
         - After your turn, you MUST choose who acts next by setting `next_actor_id`.\n\
         - You may choose yourself (`dm_agent`) if narration needs it.\n"
    } else {
        "Role guidance (Player):\n\
         - Stay in character and propose concrete actions.\n\
         - Do not control other characters or retroactively rewrite scene outcomes.\n\
         - Use `request_message_player` when you want a private whisper.\n\
         - Use `note_write` for personal memory updates.\n"
    };

    let mut prompt = String::new();
    prompt.push_str("You are participating in an ongoing 6-player DnD game.\n");
    prompt.push_str(&format!("Your actor_id is `{}`.\n", actor_id));
    prompt.push_str(&format!(
        "Turn cycle index: {}.\n",
        campaign.state.round_index + 1
    ));
    prompt.push_str(&format!("Campaign id: {}.\n", campaign.campaign_id));
    prompt.push_str(&format!("{}\n", role_guidance));
    prompt.push_str("Actor roster:\n");
    for id in all_actor_ids() {
        let name = campaign.actor_display_name(id);
        let pronouns = campaign.actor_pronouns(id);
        prompt.push_str(&format!("- {} => {} ({})\n", id, name, pronouns));
    }
    if actor_id == DM_ACTOR
        && let Some(hint) = dm_scheduler_hint
    {
        prompt.push_str("\nScheduler guidance:\n");
        prompt.push_str(hint);
        prompt.push('\n');
    }
    prompt.push_str("Output rules:\n");
    prompt.push_str("- Return only one JSON object. No markdown.\n");
    prompt.push_str("- Required keys: `public_message` (string), `actions` (array).\n");
    if actor_id == DM_ACTOR {
        prompt.push_str("- DM additionally requires `next_actor_id` (string actor_id).\n");
    } else {
        prompt.push_str("- `next_actor_id` is optional and ignored for non-DM actors.\n");
    }
    prompt.push_str("- Optional key: `note` (string).\n");
    prompt.push_str("- Allowed action types: `request_message_player`, `note_write`.\n");
    prompt.push_str(
        "- Do not invent action types. Invalid action types will be rejected and retried.\n",
    );
    prompt.push_str("- `request_message_player` can set `target` (single) or `targets` (array) for the same message.\n");
    prompt.push_str("- Every whisper target must be one of: ");
    prompt.push_str(&valid_targets_csv(campaign, actor_id, human));
    prompt.push_str(".\n");
    prompt
        .push_str("- Use `targets` when sending identical whisper text to multiple recipients.\n");
    if actor_id == DM_ACTOR {
        prompt.push_str(
            "- `next_actor_id` must be one of: dm_agent, player_ai_1, player_ai_2, player_ai_3, player_ai_4, human_player.\n",
        );
    }
    prompt.push_str("- Keep `public_message` concise and in-character.\n\n");

    prompt.push_str("Character sheet JSON:\n");
    prompt.push_str(&serde_json::to_string_pretty(&sheet)?);
    prompt.push_str("\n\nRecent private notes JSON:\n");
    prompt.push_str(&serde_json::to_string_pretty(&recent_notes)?);
    prompt.push_str("\n\nRecent visible transcript events JSON:\n");
    prompt.push_str(&serde_json::to_string_pretty(&visible_events)?);
    prompt.push_str("\n\nNow produce the JSON response.");

    Ok(prompt)
}

fn build_dm_whisper_prompt(
    campaign: &CampaignRuntime,
    sender: &str,
    targets: &[String],
    message: &str,
    reason: Option<&str>,
    recent_events: usize,
) -> Result<String> {
    let dm_visible =
        campaign.visible_events_for_actor(DM_ACTOR, recent_events.min(WHISPER_CONTEXT_EVENTS))?;

    let mut prompt = String::new();
    prompt.push_str("You are DM whisper gatekeeper for a DnD game.\n");
    prompt.push_str("Decide if a private message should be approved.\n");
    prompt.push_str("Return only JSON with keys: `approve` (bool) and optional `reason`.\n");
    prompt.push_str("Default to approve unless request is abusive, breaks fairness, or spoils hidden adjudication.\n\n");
    prompt.push_str(&format!("sender: {}\n", sender));
    prompt.push_str("targets: ");
    prompt.push_str(&serde_json::to_string(targets)?);
    prompt.push('\n');
    prompt.push_str("This decision applies to the full target list.\n");
    prompt.push_str(&format!("message: {}\n", message));
    if let Some(r) = reason
        && !r.trim().is_empty()
    {
        prompt.push_str(&format!("sender_reason: {}\n", r.trim()));
    }
    prompt.push_str("\nRecent DM-visible events JSON:\n");
    prompt.push_str(&serde_json::to_string_pretty(&dm_visible)?);
    prompt.push_str("\n\nNow return the JSON decision.");

    Ok(prompt)
}

fn build_repair_prompt(actor_id: &str, requires_next_actor: bool, bad_output: &str) -> String {
    if requires_next_actor {
        format!(
            "Your previous turn output for actor `{}` was invalid for the required schema.\n\
             Return ONLY valid JSON with exactly this structure:\n\
             {{\n\
               \"public_message\": \"string\",\n\
               \"actions\": [\n\
                 {{\"type\":\"request_message_player\",\"target\":\"string\",\"targets\":[\"string\"],\"message\":\"string\",\"reason\":\"optional string\"}}\n\
                 or\n\
                 {{\"type\":\"note_write\",\"text\":\"string\"}}\n\
               ],\n\
               \"next_actor_id\": \"dm_agent|player_ai_1|player_ai_2|player_ai_3|player_ai_4|human_player\",\n\
               \"note\": \"optional string\"\n\
             }}\n\
             Do not include markdown fences.\n\
             Do not include unsupported action types.\n\
             Previous invalid output was:\n{}",
            actor_id,
            truncate(bad_output, 1200)
        )
    } else {
        format!(
            "Your previous turn output for actor `{}` was invalid for the required schema.\n\
             Return ONLY valid JSON with exactly this structure:\n\
             {{\n\
               \"public_message\": \"string\",\n\
               \"actions\": [\n\
                 {{\"type\":\"request_message_player\",\"target\":\"string\",\"targets\":[\"string\"],\"message\":\"string\",\"reason\":\"optional string\"}}\n\
                 or\n\
                 {{\"type\":\"note_write\",\"text\":\"string\"}}\n\
               ],\n\
               \"note\": \"optional string\"\n\
             }}\n\
             Do not include markdown fences.\n\
             Do not include unsupported action types.\n\
             Previous invalid output was:\n{}",
            actor_id,
            truncate(bad_output, 1200)
        )
    }
}

fn parse_agent_turn_response(raw: &str) -> Result<AgentTurnResponse> {
    parse_schema_json::<AgentTurnResponse>(raw)
}

fn parse_schema_json<T: DeserializeOwned>(raw: &str) -> Result<T> {
    let cleaned = strip_fences(raw);
    if let Ok(parsed) = serde_json::from_str::<T>(&cleaned) {
        return Ok(parsed);
    }

    let obj_candidate = extract_json_object(&cleaned)
        .ok_or_else(|| anyhow!("No JSON object detected in model output"))?;
    let parsed: T = serde_json::from_str(obj_candidate)
        .with_context(|| format!("Failed parsing JSON payload: {}", truncate(&cleaned, 400)))?;
    Ok(parsed)
}

fn strip_fences(raw: &str) -> String {
    let trimmed = raw.trim();
    if !trimmed.starts_with("```") {
        return trimmed.to_string();
    }

    let mut out = Vec::new();
    let mut lines = trimmed.lines();
    let _ = lines.next();
    for line in lines {
        if line.trim_start().starts_with("```") {
            break;
        }
        out.push(line);
    }
    out.join("\n").trim().to_string()
}

fn extract_json_object(input: &str) -> Option<&str> {
    let start = input.find('{')?;
    let end = input.rfind('}')?;
    if end <= start {
        return None;
    }
    Some(&input[start..=end])
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        return s.to_string();
    }
    let head: String = s.chars().take(max).collect();
    format!("{head}...")
}

fn print_debug_turn(actor_id: &str, result: &CodexTurnResult) {
    println!(
        "[debug:{}] errors={} reasoning_chunks={} raw_events={}",
        actor_id,
        result.errors.len(),
        result.reasoning_text.len(),
        result.raw_events.len()
    );
    if !result.errors.is_empty() {
        println!(
            "[debug:{}] error_text={}",
            actor_id,
            result.errors.join(" | ")
        );
    }
}

fn resolve_actor_id(
    input: &str,
    campaign: &CampaignRuntime,
    human: &HumanIdentity,
) -> Option<&'static str> {
    let key = normalize_alias(input);
    match key.as_str() {
        "dm" | "dungeonmaster" | "dm_agent" => return Some(DM_ACTOR),
        "player5" | "p5" | "human" | "human_player" => return Some(HUMAN_ACTOR),
        "player_ai_1" | "player1" | "p1" | "ai1" => return Some(PLAYER_AI_ACTORS[0]),
        "player_ai_2" | "player2" | "p2" | "ai2" => return Some(PLAYER_AI_ACTORS[1]),
        "player_ai_3" | "player3" | "p3" | "ai3" => return Some(PLAYER_AI_ACTORS[2]),
        "player_ai_4" | "player4" | "p4" | "ai4" => return Some(PLAYER_AI_ACTORS[3]),
        _ => {}
    }

    if human_aliases(campaign, human)
        .iter()
        .any(|alias| alias == &key)
    {
        return Some(HUMAN_ACTOR);
    }

    for actor_id in all_actor_ids() {
        if key == actor_id {
            return Some(actor_id);
        }
        let aliases = actor_identity_aliases(campaign, actor_id);
        if aliases.iter().any(|alias| alias == &key) {
            return Some(actor_id);
        }
    }

    None
}

fn valid_targets_csv(
    campaign: &CampaignRuntime,
    exclude_actor: &str,
    human: &HumanIdentity,
) -> String {
    let ordered = [
        DM_ACTOR,
        PLAYER_AI_ACTORS[0],
        PLAYER_AI_ACTORS[1],
        PLAYER_AI_ACTORS[2],
        PLAYER_AI_ACTORS[3],
        HUMAN_ACTOR,
    ];
    ordered
        .into_iter()
        .filter(|id| *id != exclude_actor)
        .map(|id| {
            format!(
                "{} ({})",
                public_actor_token(id),
                actor_label(campaign, id, human)
            )
        })
        .collect::<Vec<_>>()
        .join(", ")
}

fn actor_label(campaign: &CampaignRuntime, actor_id: &str, _human: &HumanIdentity) -> String {
    match actor_id {
        DM_ACTOR => "DM".to_string(),
        HUMAN_ACTOR => campaign.actor_display_name(HUMAN_ACTOR),
        id if PLAYER_AI_ACTORS.contains(&id) => campaign.actor_display_name(id),
        "system" => "System".to_string(),
        _ => campaign.actor_display_name(actor_id),
    }
}

fn styled_actor_label(campaign: &CampaignRuntime, actor_id: &str, human: &HumanIdentity) -> String {
    let label = actor_label(campaign, actor_id, human);
    match actor_id {
        DM_ACTOR => label.bright_magenta().bold().to_string(),
        HUMAN_ACTOR => label.bright_cyan().bold().to_string(),
        id if id == PLAYER_AI_ACTORS[0] => label.bright_red().bold().to_string(),
        id if id == PLAYER_AI_ACTORS[1] => label.bright_blue().bold().to_string(),
        id if id == PLAYER_AI_ACTORS[2] => label.bright_yellow().bold().to_string(),
        id if id == PLAYER_AI_ACTORS[3] => label.bright_green().bold().to_string(),
        "system" => label.bright_black().bold().to_string(),
        _ => label.bold().to_string(),
    }
}

fn format_target_labels(
    campaign: &CampaignRuntime,
    targets: &[String],
    human: &HumanIdentity,
) -> String {
    let labels: Vec<String> = targets
        .iter()
        .map(|target| styled_actor_label(campaign, target, human))
        .collect();
    format!("[{}]", labels.join(", "))
}

fn format_target_plain(
    campaign: &CampaignRuntime,
    targets: &[String],
    human: &HumanIdentity,
) -> String {
    let labels: Vec<String> = targets
        .iter()
        .map(|target| actor_label(campaign, target, human))
        .collect();
    format!("[{}]", labels.join(", "))
}

fn make_prompt_tag(name: &str) -> String {
    let first = name.split_whitespace().next().unwrap_or("player");
    let compact: String = first
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect::<String>();
    if compact.is_empty() {
        "Player".to_string()
    } else {
        let mut chars = compact.chars();
        let Some(first_char) = chars.next() else {
            return "Player".to_string();
        };
        format!("{}{}", first_char.to_uppercase(), chars.as_str())
    }
}

fn human_aliases(campaign: &CampaignRuntime, human: &HumanIdentity) -> Vec<String> {
    let base = campaign
        .actor_display_name(HUMAN_ACTOR)
        .trim()
        .to_ascii_lowercase();
    let nospace = base.replace(' ', "");
    let first = base.split_whitespace().next().unwrap_or("").to_string();
    vec![base, nospace, first, human.prompt_tag.to_ascii_lowercase()]
}

fn actor_identity_aliases(campaign: &CampaignRuntime, actor_id: &str) -> Vec<String> {
    let base = campaign.actor_display_name(actor_id).to_ascii_lowercase();
    let compact = base.replace(' ', "");
    let first = base.split_whitespace().next().unwrap_or("").to_string();
    vec![base, compact, first]
}

fn normalize_alias(input: &str) -> String {
    input.trim().to_ascii_lowercase()
}

fn public_actor_token(actor_id: &str) -> &'static str {
    match actor_id {
        DM_ACTOR => "dm",
        id if id == PLAYER_AI_ACTORS[0] => "player1",
        id if id == PLAYER_AI_ACTORS[1] => "player2",
        id if id == PLAYER_AI_ACTORS[2] => "player3",
        id if id == PLAYER_AI_ACTORS[3] => "player4",
        HUMAN_ACTOR => "player5",
        _ => "player",
    }
}

fn run_with_spinner<T, F>(subject: &str, action: F) -> Result<T>
where
    F: FnOnce() -> Result<T>,
{
    println!("{}", format!("--- {}...", subject).bright_black());
    let spinner = start_thinking_spinner(subject);
    let output = action();
    spinner.finish_and_clear();
    output
}

fn start_thinking_spinner(subject: &str) -> ProgressBar {
    let pb = ProgressBar::new_spinner();
    let style = ProgressStyle::with_template("{spinner:.cyan} {msg}")
        .unwrap_or_else(|_| ProgressStyle::default_spinner())
        .tick_strings(&["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]);
    pb.set_style(style);
    pb.enable_steady_tick(Duration::from_millis(90));
    pb.set_message(subject.to_string());
    pb
}

fn hide_previous_input_line() {
    if io::stdin().is_terminal() && io::stdout().is_terminal() {
        print!("\x1b[1A\x1b[2K\r");
        let _ = io::stdout().flush();
    }
}

fn prompt_yes_no(prompt: &str, default_yes: bool) -> Result<bool> {
    loop {
        let raw = prompt_line(prompt)?;
        let t = raw.trim().to_ascii_lowercase();
        if t.is_empty() {
            return Ok(default_yes);
        }
        if t == "y" || t == "yes" {
            return Ok(true);
        }
        if t == "n" || t == "no" {
            return Ok(false);
        }
        println!("Please answer `y` or `n`.");
    }
}

fn prompt_line(prompt: &str) -> Result<String> {
    print!("{prompt}");
    io::stdout().flush().context("failed to flush stdout")?;

    let mut buf = String::new();
    io::stdin()
        .read_line(&mut buf)
        .context("failed to read from stdin")?;
    Ok(buf.trim_end_matches(['\n', '\r']).to_string())
}
