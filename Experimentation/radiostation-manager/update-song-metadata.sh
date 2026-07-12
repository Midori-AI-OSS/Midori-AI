#!/usr/bin/env bash
# This script has been replaced by the Luna Music Metadata Studio GUI.
# Run the GUI instead:
#   ./run.sh
echo "Luna Music Metadata Studio is now a GUI application."
echo "Run: ./run.sh"
exit 0

set -euo pipefail

MUSIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADS_DIR="${HOME}/Downloads"
DEFAULT_REFINE_FEEDBACK="Preserve details but improve readability"
DEFAULT_RAW_STATEMENT="Describe the song goals and key information clearly."
DEFAULT_QNA_WHY_MADE="Why did I make this song?"
DEFAULT_QNA_BACKSTORY="Is there a backstory behind this song?"
DEFAULT_QNA_RADIO_REASON="Why is this song on Midori AI Radio?"
DEFAULT_QNA_MUSIC_THEME="What is the music theme?"
DEFAULT_QNA_LISTENER_TAKEAWAY="What should listeners take away from this song?"
MAX_OPENCODE_ATTEMPTS=3
OPENCODE_MODEL="${OPENCODE_MODEL:-lm-studio/qwen/qwen3.6-27b}"
OPENCODE_VARIANT="${OPENCODE_VARIANT:-xhigh}"
OPENCODE_FALLBACK_MODEL="${OPENCODE_FALLBACK_MODEL:-deepseek/deepseek-v4-flash}"
OPENCODE_FALLBACK_VARIANT="${OPENCODE_FALLBACK_VARIANT:-max}"
RELATED_COMMENT_REFERENCE_LIMIT=30
RELATED_COMMENT_MAX_LENGTH=220
RELATED_VIBE_RETRIES=2
ESSENTIA_BACKEND="${ESSENTIA_BACKEND:-uv}"
ESSENTIA_UV_WORKDIR="${ESSENTIA_UV_WORKDIR:-/tmp/luna-essentia-uv}"
ESSENTIA_UV_CACHE_DIR="${ESSENTIA_UV_CACHE_DIR:-/tmp/luna-essentia-uv-cache}"
ESSENTIA_UV_PACKAGE_SPEC="${ESSENTIA_UV_PACKAGE_SPEC:-essentia}"
ESSENTIA_UV_READY=0
ESSENTIA_UV_PYTHON=""

LAST_POLISHED_STATEMENT=""
LAST_QNA_WHY_MADE=""
LAST_QNA_BACKSTORY=""
LAST_QNA_RADIO_REASON=""
LAST_QNA_MUSIC_THEME=""
LAST_QNA_LISTENER_TAKEAWAY=""
OPENCODE_CONTINUE_ALLOWED=0

MIDORI_TAG_WHY_MADE="midori_ai_why_made"
MIDORI_TAG_BACKSTORY="midori_ai_backstory"
MIDORI_TAG_RADIO_REASON="midori_ai_radio_reason"
MIDORI_TAG_MUSIC_THEME="midori_ai_music_theme"
MIDORI_TAG_LISTENER_TAKEAWAY="midori_ai_listener_takeaway"
MIDORI_TAG_VIBE_ANALYSIS="midori_ai_vibe_analysis"
MIDORI_TAG_VIBE_SUMMARY="midori_ai_vibe_summary"
MIDORI_TAG_VIBE_CACHED_AT_EPOCH="midori_ai_vibe_cached_at_epoch"
MIDORI_TAG_VIBE_CACHE_SCHEMA="midori_ai_vibe_cache_schema"
MIDORI_VIBE_CACHE_SCHEMA_VALUE="v1"
VIBE_CACHE_MAX_AGE_SECONDS=$((365 * 24 * 60 * 60))
SELECTED_DOWNLOAD_SONG=""
SELECTED_DOWNLOAD_SONGS=()
SELECTED_LIBRARY_SONG=""
SELECTED_CHANNEL=""
SELECTED_COMMENT_MODE=""
PARSE_IMPORT_ERROR=""
PARSED_DOWNLOAD_INDEXES=()
DOWNLOAD_MP3_TOTAL=0
DOWNLOAD_MP3_SKIPPED_IMPORTED=0
RECENT_NON_IMPORTED_DOWNLOADS=()
declare -A IMPORTED_MP3_BY_BASENAME=()
declare -A ESSENTIA_ANALYSIS_CACHE=()
declare -A SONG_VIBE_CACHE=()

VIBE_FAILURE_SENTINEL="__vibe_failure__"

RELATED_SONGS_USED=0
RELATED_SONGS_SKIPPED_NO_VIBES=0
RELATED_SONGS_SKIPPED_EMPTY_VIBES=0

COLOR_RESET=""
COLOR_ACCENT=""
COLOR_HEADER=""
COLOR_SUCCESS=""
COLOR_WARN=""
COLOR_ERROR=""
COLOR_DIM=""

init_colors() {
  if [[ -t 1 ]]; then
    COLOR_RESET=$'\033[0m'
    COLOR_ACCENT=$'\033[38;5;45m'
    COLOR_HEADER=$'\033[38;5;213m'
    COLOR_SUCCESS=$'\033[38;5;84m'
    COLOR_WARN=$'\033[38;5;220m'
    COLOR_ERROR=$'\033[38;5;203m'
    COLOR_DIM=$'\033[38;5;244m'
  fi
}

relative_path() {
  local file_path="$1"
  if [[ "$file_path" == "$MUSIC_ROOT/"* ]]; then
    printf '%s\n' "${file_path#"$MUSIC_ROOT/"}"
  else
    printf '%s\n' "$file_path"
  fi
}

print_splash() {
  if [[ -t 1 ]]; then
    clear
  fi

  cat <<EOF
${COLOR_HEADER}========================================${COLOR_RESET}
${COLOR_HEADER}  Luna Music Metadata Studio${COLOR_RESET}
${COLOR_HEADER}========================================${COLOR_RESET}
${COLOR_DIM}Root:${COLOR_RESET} ${MUSIC_ROOT}
${COLOR_DIM}Downloads:${COLOR_RESET} ${DOWNLOADS_DIR}
EOF
}

print_section() {
  local title="$1"
  printf '\n%s%s%s\n' "$COLOR_ACCENT" "== ${title} ==" "$COLOR_RESET"
}

show_toast_summary() {
  local used="$1"
  local skipped_no_vibes="$2"
  local skipped_empty_vibes="$3"
  local total_skipped=$((skipped_no_vibes + skipped_empty_vibes))
  local -a parts=()

  parts+=("Used ${used} related songs")

  if ((total_skipped > 0)); then
    local -a skip_reasons=()
    if ((skipped_no_vibes > 0)); then
      skip_reasons+=("${skipped_no_vibes} analysis failed")
    fi
    if ((skipped_empty_vibes > 0)); then
      skip_reasons+=("${skipped_empty_vibes} empty vibes")
    fi
    parts+=("${total_skipped} skipped: $(IFS=', '; printf '%s' "${skip_reasons[*]}")")
  fi

  printf '%s%s%s\n' "$COLOR_DIM" "$(IFS=' | '; printf '%s' "${parts[*]}")" "$COLOR_RESET"
}

prompt_with_default() {
  local prompt="$1"
  local default_value="${2:-}"
  local input

  if [[ -n "$default_value" ]]; then
    if ! read -r -p "$prompt [$default_value]: " input; then
      return 1
    fi
    printf '%s' "${input:-$default_value}"
    return 0
  fi

  if ! read -r -p "$prompt: " input; then
    return 1
  fi
  printf '%s' "$input"
}

ask_yes_no_default_yes() {
  local prompt="$1"
  local answer

  while true; do
    if ! read -r -p "$prompt [Y/n]: " answer; then
      return 1
    fi
    answer="${answer:-Y}"
    case "${answer,,}" in
      y|yes)
        return 0
        ;;
      n|no)
        return 1
        ;;
      *)
        printf '%sPlease enter y or n.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        ;;
    esac
  done
}

_render_loading_bar_frame() {
  local label="$1"
  local filled="$2"
  local width="$3"
  local thinking="${4:-}"
  local fill_segment
  local empty_segment
  local empty_count
  local cols
  local reserved
  local max_thinking

  if ((filled < 0)); then
    filled=0
  elif ((filled > width)); then
    filled=$width
  fi

  empty_count=$((width - filled))
  fill_segment="$(printf '%*s' "$filled" '')"
  fill_segment="${fill_segment// /=}"
  empty_segment="$(printf '%*s' "$empty_count" '')"
  empty_segment="${empty_segment// /-}"

  # Get terminal width for safe truncation
  cols=$(tput cols 2>/dev/null || echo 80)
  
  # Ensure we don't exceed terminal width to prevent wrapping (which causes "spam")
  # [bar] (width+2) + " " (1) + label (len)
  reserved=$((width + ${#label} + 4))
  
  if ((reserved > cols - 10)); then
    local max_label=$((cols - width - 15))
    if ((max_label > 5)); then
      label="${label:0:max_label}..."
    else
      label="..."
    fi
    reserved=$((width + ${#label} + 4))
  fi

  max_thinking=$((cols - reserved - 5))

  if [[ -n "$thinking" && $max_thinking -gt 10 ]]; then
    # Clean thinking text of any potential control characters
    thinking="${thinking//[$'\t\r\n']/ }"
    if ((${#thinking} > max_thinking)); then
      thinking="${thinking:0:max_thinking}..."
    fi
    printf '\r%s[%s%s]%s %s %s%s%s\033[K' "$COLOR_DIM" "$fill_segment" "$empty_segment" "$COLOR_RESET" "$label" "$COLOR_DIM" "$thinking" "$COLOR_RESET" >&2
  else
    printf '\r%s[%s%s]%s %s\033[K' "$COLOR_DIM" "$fill_segment" "$empty_segment" "$COLOR_RESET" "$label" >&2
  fi
}

run_with_loading_bar() {
  local label="$1"
  shift
  local -a command=("$@")
  local width=18
  local position=0
  local direction=1
  local thinking=""
  local pid
  local rc

  if ((${#command[@]} == 0)); then
    printf '%srun_with_loading_bar requires a command.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
    return 64
  fi

  if [[ ! -t 2 ]]; then
    printf '%s...\n' "$label" >&2
    "${command[@]}"
    return $?
  fi

  "${command[@]}" &
  pid=$!

  while kill -0 "$pid" >/dev/null 2>&1; do
    if [[ -n "${LOADING_BAR_MONITOR_FILE:-}" && -f "$LOADING_BAR_MONITOR_FILE" ]]; then
      # Fast parsing with sed to avoid overhead in tight loop
      # Extracts text from reasoning or text events, strips think tags and newlines
      thinking=$(tail -n 5 "$LOADING_BAR_MONITOR_FILE" 2>/dev/null | \
        grep -E '"type":"(reasoning|text)"' | tail -n 1 | \
        sed -n 's/.*"text":"\([^"]*\)".*/\1/p' | \
        sed 's/\\n/ /g; s/\\t/ /g; s/\\"/\"/g; s/<think>//g; s/<\/think>//g' | \
        tr -dc '[:print:]')
    fi

    _render_loading_bar_frame "$label" "$position" "$width" "$thinking"
    if ((position >= width)); then
      direction=-1
    elif ((position <= 0)); then
      direction=1
    fi
    ((position+=direction))
    sleep 0.07
  done

  if wait "$pid"; then
    rc=0
  else
    rc=$?
  fi

  printf '\r\033[2K' >&2
  return "$rc"
}

_build_library_research_instructions() {
  local song_file="$1"

  cat <<EOF
Read the target lyrics first:
  ffprobe -v error -show_entries format_tags=lyrics-eng -of default=noprint_wrappers=1:nokey=1 "$song_file"
If its title or lyrics name a person, character, or likely Real Moments event, search the other MP3s under the working directory for matching titles, then inspect matching lyrics-eng tags. Use a connection only when the library supports it; otherwise stay general. Never mention this research.
EOF
}

_build_song_statement_prompt() {
  local song_file="$1"
  local title="$2"
  local statement="$3"

  cat <<EOF
Write exactly one natural sentence describing this song.
$(_build_library_research_instructions "$song_file")
With lyrics, plainly explain the story, subject, or emotional movement. If it is instrumental, name a supported motif, source, or arrangement idea when possible; otherwise use a restrained atmosphere. Keep the comment about the song itself: do not add station, collection, productivity, listener-use, production-history, or AI-generation boilerplate. Use names exactly as the evidence supports (Luna Midori is a person; Midori AI is a group). Return only the sentence.

Song title: $title
Source note: $statement
EOF
}

_build_refinement_prompt() {
  local song_file="$1"
  local title="$2"
  local original_statement="$3"
  local current_draft="$4"
  local feedback="$5"

  cat <<EOF
Revise the draft into exactly one natural sentence that stays true to the song.
$(_build_library_research_instructions "$song_file")
Follow the feedback, keep supported details, and remove station, collection, productivity, listener-use, production-history, and AI-generation boilerplate. Return only the revised sentence.

Song title: $title
Source note: $original_statement
Current draft: $current_draft
Feedback: $feedback
EOF
}

normalize_single_line_text() {
  local text="$1"
  printf '%s' "$text" | tr '\r\n\t' '   ' | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//'
}

truncate_text() {
  local text="$1"
  local max_length="${2:-$RELATED_COMMENT_MAX_LENGTH}"

  if ((${#text} > max_length)); then
    printf '%s...' "${text:0:max_length}"
    return 0
  fi

  printf '%s' "$text"
}

extract_trailing_parenthetical_theme() {
  local title="$1"
  local extracted=""

  if [[ "$title" =~ \(([^()]*)\)[[:space:]]*$ ]]; then
    extracted="${BASH_REMATCH[1]}"
    extracted="$(normalize_single_line_text "$extracted")"
    if [[ -n "$extracted" ]]; then
      printf '%s\n' "$extracted"
      return 0
    fi
  fi

  return 1
}

get_song_metadata_tag() {
  local song_file="$1"
  local wanted_key="$2"
  local wanted_lower
  local line
  local pair
  local key
  local value
  local last_value=""
  local found=0

  wanted_lower="${wanted_key,,}"

  while IFS= read -r line; do
    [[ "$line" == TAG:* ]] || continue
    pair="${line#TAG:}"
    key="${pair%%=*}"
    value="${pair#*=}"
    if [[ "${key,,}" == "$wanted_lower" ]]; then
      last_value="$value"
      found=1
    fi
  done < <(ffprobe -v error -show_entries format_tags -of default=noprint_wrappers=1 "$song_file" 2>/dev/null || true)

  if ((found)); then
    printf '%s\n' "$last_value"
    return 0
  fi

  return 1
}

_build_qna_cleanup_prompt() {
  local song_file="$1"
  local title="$2"
  local field_key="$3"
  local answer="$4"
  local question_label

  case "$field_key" in
    "$MIDORI_TAG_WHY_MADE")
      question_label="Why I made this song"
      ;;
    "$MIDORI_TAG_BACKSTORY")
      question_label="Backstory"
      ;;
    "$MIDORI_TAG_RADIO_REASON")
      question_label="Why this song is on Midori AI Radio"
      ;;
    "$MIDORI_TAG_MUSIC_THEME")
      question_label="Music theme"
      ;;
    "$MIDORI_TAG_LISTENER_TAKEAWAY")
      question_label="Listener takeaway"
      ;;
    *)
      question_label="$field_key"
      ;;
  esac

  cat <<EOF
Polish this answer into one or two natural sentences. Preserve its meaning and do not add unsupported facts.
$(_build_library_research_instructions "$song_file")
Use names exactly as the evidence supports. Return only the answer.

Song title: $title
Question: $question_label
Answer: $answer
EOF
}

_build_qna_guess_prompt() {
  local song_file="$1"
  local title="$2"
  local field_key="$3"
  local current_comment="$4"
  local theme_hint="$5"
  local question_label

  case "$field_key" in
    "$MIDORI_TAG_WHY_MADE")
      question_label="Why I made this song"
      ;;
    "$MIDORI_TAG_BACKSTORY")
      question_label="Backstory"
      ;;
    "$MIDORI_TAG_RADIO_REASON")
      question_label="Why this song is on Midori AI Radio"
      ;;
    "$MIDORI_TAG_MUSIC_THEME")
      question_label="Music theme"
      ;;
    "$MIDORI_TAG_LISTENER_TAKEAWAY")
      question_label="Listener takeaway"
      ;;
    *)
      question_label="$field_key"
      ;;
  esac

  cat <<EOF
Answer this missing metadata field in one or two natural sentences.
$(_build_library_research_instructions "$song_file")
Prefer confirmed lyrics and related library tracks. If evidence is thin, make a cautious inference rather than inventing details. Return only the answer.

Song title: $title
Missing field: $question_label
Current comment: ${current_comment:-none}
Theme hint from title: ${theme_hint:-none}
EOF
}

resolve_qna_field_value() {
  local song_file="$1"
  local title="$2"
  local field_key="$3"
  local raw_input="$4"
  local current_comment="$5"
  local theme_hint="$6"
  local normalized_input
  local prompt
  local resolved
  local manual_answer
  local loading_label

  normalized_input="$(normalize_single_line_text "$raw_input")"
  if [[ -n "$normalized_input" ]]; then
    prompt="$(_build_qna_cleanup_prompt "$song_file" "$title" "$field_key" "$normalized_input")"
    loading_label="Polishing ${field_key}"
    if resolved="$(_run_prompt_with_retry "$prompt" "$loading_label" "0")"; then
      resolved="$(normalize_single_line_text "$resolved")"
      if [[ -n "$resolved" ]]; then
        printf '%s\n' "$resolved"
        return 0
      fi
    fi
    printf '%s\n' "$normalized_input"
    return 0
  fi

  prompt="$(_build_qna_guess_prompt "$song_file" "$title" "$field_key" "$current_comment" "$theme_hint")"
  loading_label="Guessing ${field_key}"
  if resolved="$(_run_prompt_with_retry "$prompt" "$loading_label" "0")"; then
    resolved="$(normalize_single_line_text "$resolved")"
    if [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi

  printf '%sCould not infer %s from the available song and library evidence.%s\n' "$COLOR_WARN" "$field_key" "$COLOR_RESET" >&2
  if ! manual_answer="$(prompt_with_default "Enter a cautious answer or cancel" "")"; then
    return 1
  fi
  manual_answer="$(normalize_single_line_text "$manual_answer")"
  if [[ -z "$manual_answer" ]]; then
    return 1
  fi
  printf '%s\n' "$manual_answer"
}

build_qna_seed_statement() {
  local why_made="$1"
  local backstory="$2"
  local radio_reason="$3"
  local music_theme="$4"
  local listener_takeaway="$5"

  cat <<EOF
Why I made this song: $why_made
Backstory: $backstory
Why this song is on Midori AI Radio: $radio_reason
Music theme: $music_theme
Listener takeaway: $listener_takeaway
EOF
}

collect_song_qna_inputs() {
  local song_file="$1"
  local song_title="$2"
  local current_comment="$3"
  local theme_hint=""
  local why_default=""
  local backstory_default=""
  local radio_default=""
  local theme_default=""
  local takeaway_default=""
  local why_input=""
  local backstory_input=""
  local radio_input=""
  local theme_input=""
  local takeaway_input=""

  theme_hint="$(extract_trailing_parenthetical_theme "$song_title" || true)"

  why_default="$(normalize_single_line_text "$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_WHY_MADE" || true)")"
  backstory_default="$(normalize_single_line_text "$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_BACKSTORY" || true)")"
  radio_default="$(normalize_single_line_text "$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_RADIO_REASON" || true)")"
  theme_default="$(normalize_single_line_text "$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_MUSIC_THEME" || true)")"
  takeaway_default="$(normalize_single_line_text "$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_LISTENER_TAKEAWAY" || true)")"

  if [[ -z "$theme_default" && -n "$theme_hint" ]]; then
    theme_default="$theme_hint"
  fi

  print_section "Song Q&A Inputs"
  if ! why_input="$(prompt_with_default "$DEFAULT_QNA_WHY_MADE" "$why_default")"; then
    return 130
  fi
  if ! backstory_input="$(prompt_with_default "$DEFAULT_QNA_BACKSTORY" "$backstory_default")"; then
    return 130
  fi
  if ! radio_input="$(prompt_with_default "$DEFAULT_QNA_RADIO_REASON" "$radio_default")"; then
    return 130
  fi
  if ! theme_input="$(prompt_with_default "$DEFAULT_QNA_MUSIC_THEME" "$theme_default")"; then
    return 130
  fi
  if ! takeaway_input="$(prompt_with_default "$DEFAULT_QNA_LISTENER_TAKEAWAY" "$takeaway_default")"; then
    return 130
  fi

  LAST_QNA_WHY_MADE="$(resolve_qna_field_value "$song_file" "$song_title" "$MIDORI_TAG_WHY_MADE" "$why_input" "$current_comment" "$theme_hint")"
  LAST_QNA_BACKSTORY="$(resolve_qna_field_value "$song_file" "$song_title" "$MIDORI_TAG_BACKSTORY" "$backstory_input" "$current_comment" "$theme_hint")"
  LAST_QNA_RADIO_REASON="$(resolve_qna_field_value "$song_file" "$song_title" "$MIDORI_TAG_RADIO_REASON" "$radio_input" "$current_comment" "$theme_hint")"
  LAST_QNA_MUSIC_THEME="$(resolve_qna_field_value "$song_file" "$song_title" "$MIDORI_TAG_MUSIC_THEME" "$theme_input" "$current_comment" "$theme_hint")"
  LAST_QNA_LISTENER_TAKEAWAY="$(resolve_qna_field_value "$song_file" "$song_title" "$MIDORI_TAG_LISTENER_TAKEAWAY" "$takeaway_input" "$current_comment" "$theme_hint")"

  LAST_QNA_WHY_MADE="$(normalize_single_line_text "$LAST_QNA_WHY_MADE")"
  LAST_QNA_BACKSTORY="$(normalize_single_line_text "$LAST_QNA_BACKSTORY")"
  LAST_QNA_RADIO_REASON="$(normalize_single_line_text "$LAST_QNA_RADIO_REASON")"
  LAST_QNA_MUSIC_THEME="$(normalize_single_line_text "$LAST_QNA_MUSIC_THEME")"
  LAST_QNA_LISTENER_TAKEAWAY="$(normalize_single_line_text "$LAST_QNA_LISTENER_TAKEAWAY")"

  return 0
}

tokenize_for_similarity() {
  local text="$1"
  printf '%s\n' "$text" \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]/ /g' \
    | tr ' ' '\n' \
    | awk 'length($0) >= 3' \
    | sort -u
}

token_overlap_score() {
  local left_text="$1"
  local right_text="$2"
  local token
  local -A left_tokens=()
  local score=0

  while IFS= read -r token; do
    [[ -n "$token" ]] || continue
    left_tokens["$token"]=1
  done < <(tokenize_for_similarity "$left_text")

  while IFS= read -r token; do
    [[ -n "$token" ]] || continue
    if [[ -n "${left_tokens[$token]+x}" ]]; then
      ((score+=1))
    fi
  done < <(tokenize_for_similarity "$right_text")

  printf '%s\n' "$score"
}

get_file_mtime_epoch() {
  local file_path="$1"
  local mtime

  if mtime="$(stat -c '%Y' "$file_path" 2>/dev/null)"; then
    printf '%s\n' "$mtime"
    return 0
  fi

  if mtime="$(stat -f '%m' "$file_path" 2>/dev/null)"; then
    printf '%s\n' "$mtime"
    return 0
  fi

  printf '0\n'
}

build_analysis_cache_key() {
  local song_file="$1"
  local song_mtime
  song_mtime="$(get_file_mtime_epoch "$song_file")"
  printf '%s|%s|%s|%s\n' "$song_file" "$song_mtime" "$ESSENTIA_BACKEND" "$ESSENTIA_UV_PACKAGE_SPEC"
}

is_numeric_value() {
  local value="$1"
  [[ "$value" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

is_non_negative_integer() {
  local value="$1"
  [[ "$value" =~ ^[0-9]+$ ]]
}

get_current_epoch() {
  local now_epoch

  if now_epoch="$(date +%s 2>/dev/null)" && is_non_negative_integer "$now_epoch"; then
    printf '%s\n' "$now_epoch"
    return 0
  fi

  printf '0\n'
}

is_vibe_cache_timestamp_fresh() {
  local cached_at_epoch="$1"
  local now_epoch
  local age_seconds

  if ! is_non_negative_integer "$cached_at_epoch"; then
    return 1
  fi
  if ((cached_at_epoch <= 0)); then
    return 1
  fi

  now_epoch="$(get_current_epoch)"
  if ! is_non_negative_integer "$now_epoch"; then
    return 1
  fi
  if ((now_epoch <= 0)); then
    return 1
  fi

  if ((cached_at_epoch > now_epoch)); then
    return 1
  fi

  age_seconds=$((now_epoch - cached_at_epoch))
  if ((age_seconds > VIBE_CACHE_MAX_AGE_SECONDS)); then
    return 1
  fi

  return 0
}

is_vibe_cache_schema_current() {
  local cache_schema="$1"
  cache_schema="$(normalize_single_line_text "$cache_schema")"
  [[ "$cache_schema" == "$MIDORI_VIBE_CACHE_SCHEMA_VALUE" ]]
}

get_cached_vibe_tag_value() {
  local song_file="$1"
  local tag_name="$2"
  local raw_value

  raw_value="$(get_song_metadata_tag "$song_file" "$tag_name" || true)"
  raw_value="$(normalize_single_line_text "$raw_value")"
  printf '%s\n' "$raw_value"
}

is_valid_cached_analysis_context() {
  local analysis_context="$1"
  local tempo_field
  local tempo_value

  analysis_context="$(normalize_single_line_text "$analysis_context")"
  if [[ -z "$analysis_context" ]]; then
    return 1
  fi

  tempo_field="$(extract_analysis_metric "$analysis_context" "tempo")"
  tempo_value="${tempo_field%% BPM*}"
  if ! is_numeric_value "$tempo_value"; then
    return 1
  fi

  if ! build_song_vibe_summary "$analysis_context" >/dev/null 2>&1; then
    return 1
  fi

  return 0
}

cache_song_analysis_and_vibe_in_memory() {
  local song_file="$1"
  local analysis_context="$2"
  local vibe_summary="$3"
  local cache_key

  analysis_context="$(normalize_single_line_text "$analysis_context")"
  vibe_summary="$(normalize_single_line_text "$vibe_summary")"
  cache_key="$(build_analysis_cache_key "$song_file")"

  if [[ -n "$analysis_context" ]]; then
    ESSENTIA_ANALYSIS_CACHE["$cache_key"]="$analysis_context"
  fi

  if [[ -n "$vibe_summary" ]]; then
    SONG_VIBE_CACHE["$cache_key"]="$vibe_summary"
  else
    unset "SONG_VIBE_CACHE[$cache_key]"
  fi
}

cache_song_vibe_failure_in_memory() {
  local song_file="$1"
  local cache_key
  cache_key="$(build_analysis_cache_key "$song_file")"
  SONG_VIBE_CACHE["$cache_key"]="$VIBE_FAILURE_SENTINEL"
}

persist_song_vibe_cache_best_effort() {
  local song_file="$1"
  local analysis_context="$2"
  local vibe_summary="$3"
  local cached_at_epoch="${4:-}"
  local existing_analysis
  local existing_summary
  local existing_cached_at
  local existing_schema

  analysis_context="$(normalize_single_line_text "$analysis_context")"
  vibe_summary="$(normalize_single_line_text "$vibe_summary")"

  if ! is_valid_cached_analysis_context "$analysis_context"; then
    return 1
  fi
  if [[ -z "$vibe_summary" ]]; then
    return 1
  fi

  if ! is_non_negative_integer "$cached_at_epoch" || ((cached_at_epoch <= 0)); then
    cached_at_epoch="$(get_current_epoch)"
  fi
  if ! is_non_negative_integer "$cached_at_epoch" || ((cached_at_epoch <= 0)); then
    return 1
  fi

  existing_analysis="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_ANALYSIS")"
  existing_summary="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_SUMMARY")"
  existing_cached_at="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHED_AT_EPOCH")"
  existing_schema="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHE_SCHEMA")"

  if [[ "$existing_analysis" == "$analysis_context" ]] \
    && [[ "$existing_summary" == "$vibe_summary" ]] \
    && [[ "$existing_cached_at" == "$cached_at_epoch" ]] \
    && [[ "$existing_schema" == "$MIDORI_VIBE_CACHE_SCHEMA_VALUE" ]]; then
    cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
    return 0
  fi

  if ! write_vibe_cache_tags_in_place "$song_file" "$analysis_context" "$vibe_summary" "$cached_at_epoch" "$MIDORI_VIBE_CACHE_SCHEMA_VALUE"; then
    return 1
  fi

  cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
  return 0
}

get_cached_essentia_analysis() {
  local song_file="$1"
  local force="${2:-0}"
  local cache_key
  local analysis_context
  local vibe_summary
  local cache_schema
  local cached_at_epoch

  cache_key="$(build_analysis_cache_key "$song_file")"

  if [[ "$force" != "1" ]]; then
    if [[ -n "${ESSENTIA_ANALYSIS_CACHE[$cache_key]+x}" ]]; then
      analysis_context="${ESSENTIA_ANALYSIS_CACHE[$cache_key]}"
      printf '%s\n' "$analysis_context"
      return 0
    fi

    cache_schema="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHE_SCHEMA")"
    cached_at_epoch="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHED_AT_EPOCH")"
    analysis_context="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_ANALYSIS")"

    if is_vibe_cache_schema_current "$cache_schema" \
      && is_vibe_cache_timestamp_fresh "$cached_at_epoch" \
      && is_valid_cached_analysis_context "$analysis_context"; then
      vibe_summary="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_SUMMARY")"
      if [[ -z "$vibe_summary" ]]; then
        if vibe_summary="$(build_song_vibe_summary "$analysis_context" 2>/dev/null)"; then
          vibe_summary="$(normalize_single_line_text "$vibe_summary")"
          if ! persist_song_vibe_cache_best_effort "$song_file" "$analysis_context" "$vibe_summary" "$cached_at_epoch"; then
            cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
          fi
        fi
      else
        cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
      fi

      printf '%s\n' "$analysis_context"
      return 0
    fi
  else
    unset "ESSENTIA_ANALYSIS_CACHE[$cache_key]"
    unset "SONG_VIBE_CACHE[$cache_key]"
  fi

  if [[ "$ESSENTIA_BACKEND" != "uv" ]]; then
    return 1
  fi

  if ! analysis_context="$(analyze_song_with_essentia "$song_file")"; then
    return 1
  fi

  analysis_context="$(normalize_single_line_text "$analysis_context")"
  if ! is_valid_cached_analysis_context "$analysis_context"; then
    return 1
  fi

  if ! vibe_summary="$(build_song_vibe_summary "$analysis_context")"; then
    return 1
  fi
  vibe_summary="$(normalize_single_line_text "$vibe_summary")"
  cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
  if ! persist_song_vibe_cache_best_effort "$song_file" "$analysis_context" "$vibe_summary"; then
    printf '%sCould not persist vibe cache tags for:%s %s\n' "$COLOR_WARN" "$COLOR_RESET" "$song_file" >&2
  fi

  printf '%s\n' "$analysis_context"
}

extract_analysis_metric() {
  local analysis_context="$1"
  local key="$2"

  awk -v key="$key" -F'; ' '
    {
      for (i=1; i<=NF; i++) {
        if ($i ~ ("^" key "=")) {
          sub("^" key "=", "", $i)
          print $i
          exit
        }
      }
    }
  ' <<< "$analysis_context"
}

build_song_vibe_summary() {
  local analysis_context="$1"
  local tempo_field
  local tempo_value
  local tempo_vibe
  local rms_value
  local dynamics_vibe
  local centroid_value
  local tone_vibe
  local key_value
  local joined
  local -a vibe_parts=()

  tempo_field="$(extract_analysis_metric "$analysis_context" "tempo")"
  tempo_value="${tempo_field%% BPM*}"
  if is_numeric_value "$tempo_value"; then
    tempo_vibe="$(awk -v t="$tempo_value" 'BEGIN { if (t < 80) print "slow tempo"; else if (t < 110) print "steady tempo"; else if (t < 145) print "driving tempo"; else print "fast tempo"; }')"
    vibe_parts+=("$tempo_vibe")
  fi

  rms_value="$(extract_analysis_metric "$analysis_context" "rms_mean")"
  if is_numeric_value "$rms_value"; then
    dynamics_vibe="$(awk -v r="$rms_value" 'BEGIN { if (r < 0.035) print "soft dynamics"; else if (r < 0.080) print "balanced dynamics"; else print "strong dynamics"; }')"
    vibe_parts+=("$dynamics_vibe")
  fi

  centroid_value="$(extract_analysis_metric "$analysis_context" "centroid_mean_hz")"
  if is_numeric_value "$centroid_value"; then
    tone_vibe="$(awk -v c="$centroid_value" 'BEGIN { if (c < 1700) print "warm tone"; else if (c < 3200) print "neutral tone"; else print "bright tone"; }')"
    vibe_parts+=("$tone_vibe")
  fi

  key_value="$(extract_analysis_metric "$analysis_context" "key")"
  key_value="$(normalize_single_line_text "$key_value")"
  if [[ -n "$key_value" ]]; then
    vibe_parts+=("key ${key_value}")
  fi

  if ((${#vibe_parts[@]} == 0)); then
    return 1
  fi

  joined="$(IFS=', '; printf '%s' "${vibe_parts[*]}")"
  printf '%s\n' "$joined"
}

get_cached_song_vibe() {
  local song_file="$1"
  local retry_count="${2:-0}"
  local cache_key
  local vibe_summary
  local analysis_context
  local cache_schema
  local cached_at_epoch
  local attempt=1
  local max_attempts=1

  if [[ ! "$retry_count" =~ ^[0-9]+$ ]]; then
    retry_count=0
  fi
  max_attempts=$((retry_count + 1))

  cache_key="$(build_analysis_cache_key "$song_file")"
  if [[ -n "${SONG_VIBE_CACHE[$cache_key]+x}" ]]; then
    vibe_summary="${SONG_VIBE_CACHE[$cache_key]}"
    if [[ "$vibe_summary" != "$VIBE_FAILURE_SENTINEL" ]]; then
      printf '%s\n' "$vibe_summary"
      return 0
    fi

    if ((retry_count <= 0)); then
      return 1
    fi

    unset "SONG_VIBE_CACHE[$cache_key]"
    unset "ESSENTIA_ANALYSIS_CACHE[$cache_key]"
  fi

  cache_schema="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHE_SCHEMA")"
  cached_at_epoch="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_CACHED_AT_EPOCH")"
  if is_vibe_cache_schema_current "$cache_schema" && is_vibe_cache_timestamp_fresh "$cached_at_epoch"; then
    vibe_summary="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_SUMMARY")"
    analysis_context="$(get_cached_vibe_tag_value "$song_file" "$MIDORI_TAG_VIBE_ANALYSIS")"

    if [[ -n "$vibe_summary" ]]; then
      cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
      printf '%s\n' "$vibe_summary"
      return 0
    fi

    if is_valid_cached_analysis_context "$analysis_context"; then
      if vibe_summary="$(build_song_vibe_summary "$analysis_context" 2>/dev/null)"; then
        vibe_summary="$(normalize_single_line_text "$vibe_summary")"
        cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
        if ! persist_song_vibe_cache_best_effort "$song_file" "$analysis_context" "$vibe_summary" "$cached_at_epoch"; then
          :
        fi
        printf '%s\n' "$vibe_summary"
        return 0
      fi
    fi
  fi

  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    if ! analysis_context="$(get_cached_essentia_analysis "$song_file")"; then
      continue
    fi

    if ! vibe_summary="$(build_song_vibe_summary "$analysis_context")"; then
      continue
    fi

    cache_song_analysis_and_vibe_in_memory "$song_file" "$analysis_context" "$vibe_summary"
    printf '%s\n' "$vibe_summary"
    return 0
  done

  cache_song_vibe_failure_in_memory "$song_file"
  return 1
}

find_related_song_comments() {
  local target_song="$1"
  local target_title="$2"
  local limit="${3:-$RELATED_COMMENT_REFERENCE_LIMIT}"
  local target_base
  local target_basis
  local -a library_songs=()
  local -a eligible_rows=()
  local -a scored_rows=()
  local -a candidate_pool=()
  local -A selected_paths=()
  local candidate_song
  local candidate_base
  local candidate_title
  local candidate_comment
  local candidate_comment_clean
  local candidate_basis
  local score
  local candidate_mtime
  local row_mtime
  local row_score
  local row_title
  local row_path
  local row_comment
  local row_vibes
  local row_theme
  local row
  local emitted=0
  local skip_no_vibes=0
  local skip_empty_vibes=0

  target_base="$(basename "$target_song")"
  target_base="${target_base%.[mM][pP]3}"
  target_basis="$(normalize_single_line_text "${target_title} ${target_base}")"

  RELATED_SONGS_USED=0
  RELATED_SONGS_SKIPPED_NO_VIBES=0
  RELATED_SONGS_SKIPPED_EMPTY_VIBES=0

  mapfile -t library_songs < <(find "$MUSIC_ROOT" -type f -iname '*.mp3' 2>/dev/null | sort)

  for candidate_song in "${library_songs[@]}"; do
    if [[ "$candidate_song" == "$target_song" ]]; then
      continue
    fi

    candidate_comment="$(get_song_comment "$candidate_song")"
    candidate_comment_clean="$(normalize_single_line_text "$candidate_comment")"
    if [[ -z "$candidate_comment_clean" ]]; then
      continue
    fi
    if is_outdated_comment "$candidate_comment_clean"; then
      continue
    fi

    candidate_title="$(get_song_title "$candidate_song")"
    candidate_title="$(normalize_single_line_text "$candidate_title")"
    candidate_base="$(basename "$candidate_song")"
    candidate_base="${candidate_base%.[mM][pP]3}"
    candidate_basis="$(normalize_single_line_text "${candidate_title} ${candidate_base}")"
    score="$(token_overlap_score "$target_basis" "$candidate_basis")"
    candidate_mtime="$(get_file_mtime_epoch "$candidate_song")"

    candidate_comment_clean="$(truncate_text "$candidate_comment_clean" "$RELATED_COMMENT_MAX_LENGTH")"
    eligible_rows+=("${candidate_mtime}"$'\t'"${score}"$'\t'"${candidate_title}"$'\t'"${candidate_song}"$'\t'"${candidate_comment_clean}")
    if ((score > 0)); then
      scored_rows+=("${candidate_mtime}"$'\t'"${score}"$'\t'"${candidate_title}"$'\t'"${candidate_song}"$'\t'"${candidate_comment_clean}")
    fi
  done

  if ((${#eligible_rows[@]} == 0)); then
    return 0
  fi

  if ((${#scored_rows[@]} > 0)); then
    while IFS=$'\t' read -r row_mtime row_score row_title row_path row_comment; do
      [[ -n "$row_path" ]] || continue
      if [[ -n "${selected_paths[$row_path]+x}" ]]; then
        continue
      fi
      candidate_pool+=("${row_title}"$'\t'"${row_path}"$'\t'"${row_comment}")
      selected_paths["$row_path"]=1
    done < <(printf '%s\n' "${scored_rows[@]}" | sort -t $'\t' -k2,2nr -k3,3f -k1,1nr)
  fi

  while IFS=$'\t' read -r row_mtime row_score row_title row_path row_comment; do
    [[ -n "$row_path" ]] || continue
    if [[ -n "${selected_paths[$row_path]+x}" ]]; then
      continue
    fi
    candidate_pool+=("${row_title}"$'\t'"${row_path}"$'\t'"${row_comment}")
    selected_paths["$row_path"]=1
  done < <(printf '%s\n' "${eligible_rows[@]}" | sort -t $'\t' -k1,1nr -k3,3f)

  for row in "${candidate_pool[@]}"; do
    IFS=$'\t' read -r row_title row_path row_comment <<< "$row"
    if [[ -z "$row_title" ]]; then
      row_title="$(basename "$row_path")"
    fi

    row_vibes=""
    if [[ "$ESSENTIA_BACKEND" == "uv" ]]; then
      if row_vibes="$(run_with_loading_bar "Vibes: $row_title" get_cached_song_vibe "$row_path" "$RELATED_VIBE_RETRIES")"; then
        row_vibes="$(normalize_single_line_text "$row_vibes")"
      fi
    else
      if row_vibes="$(get_cached_song_vibe "$row_path" 0 2>/dev/null)"; then
        row_vibes="$(normalize_single_line_text "$row_vibes")"
      fi
    fi

    if [[ -z "$row_vibes" ]]; then
      if ! get_cached_song_vibe "$row_path" 0 >/dev/null 2>&1; then
        ((skip_no_vibes+=1))
      else
        ((skip_empty_vibes+=1))
      fi
      row_vibes="unknown vibes"
    fi

    row_theme="$(normalize_single_line_text "$(get_song_metadata_tag "$row_path" "$MIDORI_TAG_MUSIC_THEME" || true)")"
    if [[ -z "$row_theme" ]]; then
      row_theme="unknown theme"
    fi

    printf '%s : %s : Theme=%s : %s\n' "$row_title" "$row_vibes" "$row_theme" "$row_comment"
    ((emitted+=1))
    if ((emitted >= limit)); then
      break
    fi
  done

  printf '__COUNTS__:%d:%d:%d\n' "$emitted" "$skip_no_vibes" "$skip_empty_vibes"
}

_run_song_statement_opencode() {
  local prompt="$1"
  local output_file="$2"
  local stderr_file="$3"
  local continue_mode="${4:-0}"
  local model="${5:-$OPENCODE_MODEL}"
  local variant="${6:-$OPENCODE_VARIANT}"
  local -a cmd=(opencode run --dir "$MUSIC_ROOT" --variant "$variant" -m "$model")

  if [[ "$continue_mode" == "1" ]]; then
    cmd+=(-c)
  fi

  # Enable thinking and JSON format for real-time reasoning extraction
  cmd+=(--thinking --format json)

  cmd+=("$prompt")
  "${cmd[@]}" > "$output_file" 2> "$stderr_file"
}

_run_prompt_with_retry() {
  local prompt="$1"
  local loading_label="${2:-OpenCode}"
  local continue_mode="${3:-0}"
  local output_file
  local stderr_file
  local attempt
  local current_model
  local current_variant

  output_file="$(mktemp /tmp/fix-song-statement.XXXXXX)"
  stderr_file="$(mktemp /tmp/fix-song-statement.stderr.XXXXXX)"

  for ((attempt=1; attempt<=MAX_OPENCODE_ATTEMPTS; attempt++)); do
    : > "$stderr_file"
    : > "$output_file"
    current_model="$OPENCODE_MODEL"
    current_variant="$OPENCODE_VARIANT"
    if ((attempt == MAX_OPENCODE_ATTEMPTS)) && [[ -n "$OPENCODE_FALLBACK_MODEL" ]]; then
      current_model="$OPENCODE_FALLBACK_MODEL"
      current_variant="$OPENCODE_FALLBACK_VARIANT"
    fi
    if LOADING_BAR_MONITOR_FILE="$output_file" run_with_loading_bar "$loading_label" _run_song_statement_opencode "$prompt" "$output_file" "$stderr_file" "$continue_mode" "$current_model" "$current_variant"; then
      # Extract final text from JSON events
      uv run python -c "
import sys, json, re
def extract_final():
    full_text = ''
    try:
        with open(sys.argv[1], 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'text':
                        text = data.get('part', {}).get('text', '')
                        if text: full_text = text # opencode often sends the full accumulated text in the last event
                except: continue
    except: pass
    # Strip think tags from final output if present
    full_text = re.sub(r'<think>.*?</think>', '', full_text, flags=re.DOTALL).strip()
    print(full_text)

extract_final()
" "$output_file"
      rm -f "$output_file" "$stderr_file"
      return 0
    fi
  done

  if [[ -s "$stderr_file" ]]; then
    printf '%sOpenCode execution details:%s\n' "$COLOR_WARN" "$COLOR_RESET" >&2
    cat "$stderr_file" >&2
  fi

  rm -f "$output_file" "$stderr_file"
  return 1
}

is_valid_comment_sentence() {
  local draft
  local lower

  draft="$(normalize_single_line_text "$1")"
  [[ -n "$draft" ]] || return 1
  [[ ! "$draft" =~ [.!?][[:space:]]+[^[:space:]] ]] || return 1

  lower="${draft,,}"
  [[ "$lower" != song\ title:* ]] || return 1
  [[ "$lower" != comment:* ]] || return 1
  [[ "$lower" != *"let me "* ]] || return 1
  [[ "$lower" != *"i checked"* ]] || return 1
  return 0
}

run_comment_prompt() {
  local prompt="$1"
  local loading_label="${2:-OpenCode}"
  local continue_mode="${3:-0}"
  local draft
  local correction

  if ! draft="$(_run_prompt_with_retry "$prompt" "$loading_label" "$continue_mode")"; then
    return 1
  fi
  draft="$(normalize_single_line_text "$draft")"
  if is_valid_comment_sentence "$draft"; then
    printf '%s\n' "$draft"
    return 0
  fi

  correction="Rewrite the following as exactly one natural sentence about the song. Return only that sentence, with no label or process text: $draft"
  if ! draft="$(_run_prompt_with_retry "$correction" "${loading_label} correction" "$continue_mode")"; then
    return 1
  fi
  draft="$(normalize_single_line_text "$draft")"
  if ! is_valid_comment_sentence "$draft"; then
    return 1
  fi
  printf '%s\n' "$draft"
}

fix_song_statement() {
  if [[ "$#" -lt 3 || "$#" -gt 4 ]]; then
    echo "Usage: fix_song_statement <song_file> <title> <statement> [loading_label]" >&2
    return 64
  fi

  local song_file="$1"
  local title="$2"
  local statement="$3"
  local loading_label="${4:-OpenCode}"
  local prompt

  prompt="$(_build_song_statement_prompt "$song_file" "$title" "$statement")"
  run_comment_prompt "$prompt" "$loading_label"
}

vibe_test_model() {
  local model="${1:-$OPENCODE_MODEL}"
  local exit_code

  printf '%sTesting model: %s%s\n' "$COLOR_DIM" "$model" "$COLOR_RESET"
  printf '\n'

  opencode run --dir "$MUSIC_ROOT" --variant "$OPENCODE_VARIANT" -m "$model" "Pick any MP3 file in this directory, check its title, and tell me what song it is"
  exit_code=$?

  printf '\n'
  if ((exit_code == 0)); then
    printf '%s[OK]%s Model %s responded successfully (exit code 0)\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$model"
    return 0
  fi

  printf '%s[FAIL]%s Model %s failed (exit code %d)\n' "$COLOR_ERROR" "$COLOR_RESET" "$model" "$exit_code"
  return 1
}

get_song_title() {
  local song_file="$1"
  local title

  title="$(ffprobe -v error -show_entries format_tags=title -of default=noprint_wrappers=1:nokey=1 "$song_file" 2>/dev/null || true)"
  if [[ -n "$title" ]]; then
    printf '%s\n' "$title"
    return 0
  fi

  printf '%s\n' "${song_file##*/}" | sed 's/\.[mM][pP]3$//'
}

get_song_comment() {
  local song_file="$1"
  ffprobe -v error -show_entries format_tags=comment -of default=noprint_wrappers=1:nokey=1 "$song_file" 2>/dev/null || true
}

ensure_uv_essentia_env() {
  local uv_venv_dir="${ESSENTIA_UV_WORKDIR}/.venv"
  local uv_venv_python="${uv_venv_dir}/bin/python"
  local package_spec_file="${ESSENTIA_UV_WORKDIR}/.essentia-package-spec"
  local current_package_spec=""

  if ((ESSENTIA_UV_READY == 1)) && [[ -x "$ESSENTIA_UV_PYTHON" ]]; then
    return 0
  fi

  if [[ "$ESSENTIA_UV_PACKAGE_SPEC" == *"git+"* ]] || [[ "$ESSENTIA_UV_PACKAGE_SPEC" == *"-git"* ]]; then
    printf '%sESSENTIA_UV_PACKAGE_SPEC must use a non-git package spec, got:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$ESSENTIA_UV_PACKAGE_SPEC" >&2
    return 64
  fi

  if ! mkdir -p "$ESSENTIA_UV_WORKDIR" "$ESSENTIA_UV_CACHE_DIR"; then
    printf '%sFailed to prepare uv temp directories under /tmp.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
    return 1
  fi

  if [[ ! -x "$uv_venv_python" ]]; then
    if ! UV_CACHE_DIR="$ESSENTIA_UV_CACHE_DIR" uv venv "$uv_venv_dir" > /dev/null 2>&1; then
      printf '%sFailed to create uv temp Python environment.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
      return 1
    fi
  fi

  if [[ -f "$package_spec_file" ]]; then
    current_package_spec="$(<"$package_spec_file")"
  fi

  if [[ "$current_package_spec" != "$ESSENTIA_UV_PACKAGE_SPEC" ]]; then
    if ! UV_CACHE_DIR="$ESSENTIA_UV_CACHE_DIR" uv pip install --python "$uv_venv_python" "$ESSENTIA_UV_PACKAGE_SPEC" > /dev/null 2>&1; then
      printf '%sFailed to install Essentia via uv package spec:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$ESSENTIA_UV_PACKAGE_SPEC" >&2
      return 1
    fi
    if ! printf '%s' "$ESSENTIA_UV_PACKAGE_SPEC" > "$package_spec_file"; then
      printf '%sFailed to cache Essentia package spec marker.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
      return 1
    fi
  fi

  ESSENTIA_UV_PYTHON="$uv_venv_python"
  ESSENTIA_UV_READY=1
  return 0
}

analyze_song_with_essentia() {
  local song_file="$1"
  local analysis_context
  local analysis_stderr

  if [[ "$ESSENTIA_BACKEND" == "off" ]]; then
    return 0
  fi

  if [[ "$ESSENTIA_BACKEND" != "uv" ]]; then
    printf '%sUnsupported ESSENTIA_BACKEND value:%s %s (use uv or off)\n' "$COLOR_ERROR" "$COLOR_RESET" "$ESSENTIA_BACKEND" >&2
    return 64
  fi

  if ! ensure_uv_essentia_env; then
    return 1
  fi

  analysis_stderr="$(mktemp /tmp/essentia-uv-analysis.stderr.XXXXXX)"

  if ! analysis_context="$("$ESSENTIA_UV_PYTHON" - "$song_file" 2>"$analysis_stderr" <<'PY'
import sys

song_file = sys.argv[1]

def mean(values):
    if not values:
        return None
    return sum(values) / float(len(values))

def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None

try:
    import essentia.standard as es
except Exception as exc:
    print(f"Failed to import essentia: {exc}", file=sys.stderr)
    sys.exit(1)

sample_rate = 44100
try:
    audio = es.MonoLoader(filename=song_file, sampleRate=sample_rate)()
except Exception as exc:
    print(f"Failed to load audio with Essentia: {exc}", file=sys.stderr)
    sys.exit(1)

if len(audio) == 0:
    print("Essentia loaded an empty audio buffer.", file=sys.stderr)
    sys.exit(1)

duration = len(audio) / float(sample_rate)

try:
    bpm, ticks, confidence, _, _ = es.RhythmExtractor2013(method='multifeature')(audio)
except Exception as exc:
    print(f"Failed to extract tempo with Essentia: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    key, scale, strength = es.KeyExtractor()(audio)
except Exception as exc:
    print(f"Failed to extract key with Essentia: {exc}", file=sys.stderr)
    sys.exit(1)

onset_rate = (len(ticks) / duration) if duration > 0 else None
loudness = None
energy = None

try:
    loudness = safe_float(es.Loudness()(audio))
except Exception:
    loudness = None

try:
    energy = safe_float(es.Energy()(audio))
except Exception:
    energy = None

frame_size = 2048
hop_size = 512
windowing = es.Windowing(type='hann')
spectrum = es.Spectrum(size=frame_size)
rms_algo = es.RMS()
zcr_algo = es.ZeroCrossingRate()

centroid_algo = None
rolloff_algo = None
flatness_algo = None
mfcc_algo = None
spectral_contrast_algo = None

try:
    centroid_algo = es.Centroid(range=sample_rate / 2.0)
except Exception:
    centroid_algo = None

try:
    rolloff_algo = es.RollOff(sampleRate=sample_rate)
except Exception:
    rolloff_algo = None

try:
    flatness_algo = es.FlatnessDB()
except Exception:
    flatness_algo = None

try:
    mfcc_algo = es.MFCC(numberCoefficients=13)
except Exception:
    mfcc_algo = None

try:
    spectral_contrast_algo = es.SpectralContrast(frameSize=frame_size, sampleRate=sample_rate)
except Exception:
    spectral_contrast_algo = None

rms_values = []
zcr_values = []
centroid_values = []
rolloff_values = []
flatness_values = []
spectral_contrast_values = []
mfcc_vectors = []

for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
    if len(frame) == 0:
        continue

    rms_value = safe_float(rms_algo(frame))
    if rms_value is not None:
        rms_values.append(rms_value)

    zcr_value = safe_float(zcr_algo(frame))
    if zcr_value is not None:
        zcr_values.append(zcr_value)

    spec = None
    try:
        spec = spectrum(windowing(frame))
    except Exception:
        spec = None

    if spec is None:
        continue

    if centroid_algo is not None:
        centroid_value = safe_float(centroid_algo(spec))
        if centroid_value is not None:
            centroid_values.append(centroid_value)

    if rolloff_algo is not None:
        rolloff_value = safe_float(rolloff_algo(spec))
        if rolloff_value is not None:
            rolloff_values.append(rolloff_value)

    if flatness_algo is not None:
        flatness_value = safe_float(flatness_algo(spec))
        if flatness_value is not None:
            flatness_values.append(flatness_value)

    if spectral_contrast_algo is not None:
        try:
            contrast, _ = spectral_contrast_algo(spec)
            contrast_values = [safe_float(v) for v in contrast]
            contrast_values = [v for v in contrast_values if v is not None]
            if contrast_values:
                spectral_contrast_values.append(mean(contrast_values))
        except Exception:
            spectral_contrast_algo = None

    if mfcc_algo is not None:
        try:
            _, mfcc_values = mfcc_algo(spec)
            mfcc_values = [safe_float(v) for v in mfcc_values[:4]]
            mfcc_values = [v for v in mfcc_values if v is not None]
            if mfcc_values:
                mfcc_vectors.append(mfcc_values)
        except Exception:
            mfcc_algo = None

parts = [f"tempo={float(bpm):.2f} BPM"]

if key:
    key_text = str(key)
    if scale:
        key_text = f"{key_text} {scale}"
    key_text = f"{key_text} (strength {float(strength):.2f})"
    parts.append(f"key={key_text}")

parts.append(f"rhythm_confidence={float(confidence):.3f}")
parts.append(f"duration={duration:.2f}s")

if onset_rate is not None:
    parts.append(f"onset_rate={onset_rate:.2f}/s")

if loudness is not None:
    parts.append(f"loudness={loudness:.3f}")

if energy is not None:
    parts.append(f"energy={energy:.3f}")

rms_mean = mean(rms_values)
if rms_mean is not None:
    parts.append(f"rms_mean={rms_mean:.4f}")

if rms_values:
    parts.append(f"rms_peak={max(rms_values):.4f}")

zcr_mean = mean(zcr_values)
if zcr_mean is not None:
    parts.append(f"zcr_mean={zcr_mean:.4f}")

centroid_mean = mean(centroid_values)
if centroid_mean is not None:
    parts.append(f"centroid_mean_hz={centroid_mean:.2f}")

rolloff_mean = mean(rolloff_values)
if rolloff_mean is not None:
    parts.append(f"rolloff_mean={rolloff_mean:.3f}")

flatness_mean = mean(flatness_values)
if flatness_mean is not None:
    parts.append(f"flatness_db_mean={flatness_mean:.3f}")

spectral_contrast_mean = mean(spectral_contrast_values)
if spectral_contrast_mean is not None:
    parts.append(f"spectral_contrast_mean={spectral_contrast_mean:.3f}")

if mfcc_vectors:
    max_len = max(len(vec) for vec in mfcc_vectors)
    mfcc_means = []
    for idx in range(max_len):
        coeff_values = [vec[idx] for vec in mfcc_vectors if idx < len(vec)]
        coeff_mean = mean(coeff_values)
        if coeff_mean is not None:
            mfcc_means.append(coeff_mean)
    if mfcc_means:
        mfcc_summary = ",".join(f"{value:.2f}" for value in mfcc_means[:4])
        parts.append(f"mfcc_mean_1_4=[{mfcc_summary}]")

print("; ".join(parts))
PY
)"; then
    if [[ -s "$analysis_stderr" ]]; then
      cat "$analysis_stderr" >&2
    fi
    rm -f "$analysis_stderr"
    printf '%suv/Python Essentia analysis failed for:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$song_file" >&2
    return 1
  fi

  rm -f "$analysis_stderr"
  analysis_context="$(normalize_single_line_text "$analysis_context")"
  if [[ -z "$analysis_context" ]]; then
    printf '%sEssentia analysis returned empty context for:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$song_file" >&2
    return 1
  fi

  printf '%s\n' "$analysis_context"
}

build_unique_destination() {
  local target_path="$1"
  local dir_name
  local base_name
  local stem
  local extension
  local idx=1
  local candidate

  if [[ ! -e "$target_path" ]]; then
    printf '%s\n' "$target_path"
    return 0
  fi

  dir_name="$(dirname "$target_path")"
  base_name="$(basename "$target_path")"

  if [[ "$base_name" == *.* ]]; then
    extension=".${base_name##*.}"
    stem="${base_name%.*}"
  else
    extension=""
    stem="$base_name"
  fi

  while true; do
    candidate="${dir_name}/${stem} (${idx})${extension}"
    if [[ ! -e "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    ((++idx))
  done
}

set_file_mtime_epoch() {
  local file_path="$1"
  local epoch="$2"
  local formatted_time=""

  if ! is_non_negative_integer "$epoch"; then
    return 1
  fi
  if ((epoch <= 0)); then
    return 1
  fi

  if touch -d "@$epoch" "$file_path" 2>/dev/null; then
    return 0
  fi

  if formatted_time="$(TZ=UTC date -d "@$epoch" '+%Y%m%d%H%M.%S' 2>/dev/null)"; then
    if touch -t "$formatted_time" "$file_path" 2>/dev/null; then
      return 0
    fi
  fi

  if formatted_time="$(TZ=UTC date -r "$epoch" '+%Y%m%d%H%M.%S' 2>/dev/null)"; then
    if touch -t "$formatted_time" "$file_path" 2>/dev/null; then
      return 0
    fi
  fi

  return 1
}

write_vibe_cache_tags_in_place() {
  if [[ "$#" -ne 5 ]]; then
    echo "Usage: write_vibe_cache_tags_in_place <song_file> <analysis_context> <vibe_summary> <cached_at_epoch> <cache_schema>" >&2
    return 64
  fi

  local song_file="$1"
  local analysis_context="$2"
  local vibe_summary="$3"
  local cached_at_epoch="$4"
  local cache_schema="$5"
  local song_dir
  local temp_file
  local original_mtime

  analysis_context="$(normalize_single_line_text "$analysis_context")"
  vibe_summary="$(normalize_single_line_text "$vibe_summary")"
  cache_schema="$(normalize_single_line_text "$cache_schema")"
  if [[ -z "$analysis_context" || -z "$vibe_summary" || -z "$cache_schema" ]]; then
    return 64
  fi
  if ! is_non_negative_integer "$cached_at_epoch"; then
    return 64
  fi
  if ((cached_at_epoch <= 0)); then
    return 64
  fi

  original_mtime="$(get_file_mtime_epoch "$song_file")"
  song_dir="$(dirname "$song_file")"
  if ! temp_file="$(mktemp "${song_dir}/.vibe-cache-update-XXXXXX.mp3")"; then
    return 1
  fi

  if ! ffmpeg -hide_banner -loglevel error -y \
    -i "$song_file" \
    -map 0 \
    -c copy \
    -metadata "${MIDORI_TAG_VIBE_ANALYSIS}=$analysis_context" \
    -metadata "${MIDORI_TAG_VIBE_SUMMARY}=$vibe_summary" \
    -metadata "${MIDORI_TAG_VIBE_CACHED_AT_EPOCH}=$cached_at_epoch" \
    -metadata "${MIDORI_TAG_VIBE_CACHE_SCHEMA}=$cache_schema" \
    "$temp_file"; then
    rm -f "$temp_file"
    return 1
  fi

  if ! mv -f "$temp_file" "$song_file"; then
    rm -f "$temp_file"
    return 1
  fi

  if is_non_negative_integer "$original_mtime" && ((original_mtime > 0)); then
    if ! set_file_mtime_epoch "$song_file" "$original_mtime"; then
      printf '%sVibe cache mtime restore failed for:%s %s\n' "$COLOR_WARN" "$COLOR_RESET" "$song_file" >&2
      return 1
    fi
  fi

  return 0
}

write_song_metadata_in_place() {
  if [[ "$#" -ne 7 ]]; then
    echo "Usage: write_song_metadata_in_place <song_file> <comment> <why_made> <backstory> <radio_reason> <music_theme> <listener_takeaway>" >&2
    return 64
  fi

  local song_file="$1"
  local new_comment="$2"
  local why_made="$3"
  local backstory="$4"
  local radio_reason="$5"
  local music_theme="$6"
  local listener_takeaway="$7"
  local song_dir
  local temp_file

  song_dir="$(dirname "$song_file")"
  if ! temp_file="$(mktemp "${song_dir}/.metadata-update-XXXXXX.mp3")"; then
    return 1
  fi

  if ffmpeg -hide_banner -loglevel error -y \
    -i "$song_file" \
    -map 0 \
    -c copy \
    -metadata comment="$new_comment" \
    -metadata "${MIDORI_TAG_WHY_MADE}=$why_made" \
    -metadata "${MIDORI_TAG_BACKSTORY}=$backstory" \
    -metadata "${MIDORI_TAG_RADIO_REASON}=$radio_reason" \
    -metadata "${MIDORI_TAG_MUSIC_THEME}=$music_theme" \
    -metadata "${MIDORI_TAG_LISTENER_TAKEAWAY}=$listener_takeaway" \
    "$temp_file"; then
    if ! mv -f "$temp_file" "$song_file"; then
      rm -f "$temp_file"
      return 1
    fi
    return 0
  fi

  rm -f "$temp_file"
  return 1
}

trash_file() {
  local file_path="$1"
  local display_name

  display_name="$(relative_path "$file_path")"

  if command -v kioclient >/dev/null 2>&1; then
    if kioclient move "$file_path" trash:/ >/dev/null 2>&1; then
      printf '%sTrashed:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$display_name"
      return 0
    fi
  fi

  if command -v kioclient5 >/dev/null 2>&1; then
    if kioclient5 move "$file_path" trash:/ >/dev/null 2>&1; then
      printf '%sTrashed:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$display_name"
      return 0
    fi
  fi

  if command -v gio >/dev/null 2>&1; then
    if gio trash "$file_path" >/dev/null 2>&1; then
      printf '%sTrashed:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$display_name"
      return 0
    fi
  fi

  printf '%sNo trash tool available (kioclient, kioclient5, gio).%s\n' "$COLOR_ERROR" "$COLOR_RESET"
  return 1
}

collect_channel_dirs() {
  local -a channels=()
  mapfile -t channels < <(find "$MUSIC_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
  printf '%s\n' "${channels[@]}"
}

list_blocked_channels() {
  local -a blocked=()
  local dir

  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    if [[ -f "${MUSIC_ROOT}/${dir}/.blocked" ]]; then
      blocked+=("$dir")
    fi
  done < <(collect_channel_dirs)

  if ((${#blocked[@]} == 0)); then
    printf '%sNo blocked channels.%s\n' "$COLOR_DIM" "$COLOR_RESET"
    return 1
  fi

  printf '%sBlocked channels:%s\n' "$COLOR_DIM" "$COLOR_RESET"
  local i
  for i in "${!blocked[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${blocked[$i]}"
  done
  return 0
}

block_channel_flow() {
  local -a channels=()
  local channel
  local input
  local i

  mapfile -t channels < <(collect_channel_dirs)
  if ((${#channels[@]} == 0)); then
    printf '%sNo channels found.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi

  print_section "Block Channel"
  for i in "${!channels[@]}"; do
    if [[ -f "${MUSIC_ROOT}/${channels[$i]}/.blocked" ]]; then
      printf '  %d) %s %s(blocked)%s\n' "$((i + 1))" "${channels[$i]}" "$COLOR_WARN" "$COLOR_RESET"
    else
      printf '  %d) %s\n' "$((i + 1))" "${channels[$i]}"
    fi
  done
  printf '  b) Back\n'

  while true; do
    if ! input="$(prompt_with_default "Pick channel to block" "")"; then
      return 1
    fi
    input="${input,,}"

    if [[ "$input" == "b" ]]; then
      return 1
    fi

    if [[ "$input" =~ ^[0-9]+$ ]] && ((input >= 1 && input <= ${#channels[@]})); then
      channel="${channels[$((input - 1))]}"
      if [[ -f "${MUSIC_ROOT}/${channel}/.blocked" ]]; then
        printf '%s%s is already blocked.%s\n' "$COLOR_WARN" "$channel" "$COLOR_RESET"
        continue
      fi
      touch "${MUSIC_ROOT}/${channel}/.blocked"
      printf '%sBlocked channel:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$channel"
      return 0
    fi

    printf '%sPick a valid number or b to go back.%s\n' "$COLOR_WARN" "$COLOR_RESET"
  done
}

unblock_channel_flow() {
  local -a blocked=()
  local dir
  local channel
  local input
  local i

  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    if [[ -f "${MUSIC_ROOT}/${dir}/.blocked" ]]; then
      blocked+=("$dir")
    fi
  done < <(collect_channel_dirs)

  if ((${#blocked[@]} == 0)); then
    printf '%sNo blocked channels to unblock.%s\n' "$COLOR_DIM" "$COLOR_RESET"
    return 1
  fi

  print_section "Unblock Channel"
  for i in "${!blocked[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${blocked[$i]}"
  done
  printf '  b) Back\n'

  while true; do
    if ! input="$(prompt_with_default "Pick channel to unblock" "")"; then
      return 1
    fi
    input="${input,,}"

    if [[ "$input" == "b" ]]; then
      return 1
    fi

    if [[ "$input" =~ ^[0-9]+$ ]] && ((input >= 1 && input <= ${#blocked[@]})); then
      channel="${blocked[$((input - 1))]}"
      rm -f "${MUSIC_ROOT}/${channel}/.blocked"
      printf '%sUnblocked channel:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$channel"
      return 0
    fi

    printf '%sPick a valid number or b to go back.%s\n' "$COLOR_WARN" "$COLOR_RESET"
  done
}

play_song_detached() {
  local song_file="$1"
  local display_name

  if ! command -v haruna >/dev/null 2>&1; then
    printf '%sHaruna is not installed on this system.%s\n' "$COLOR_ERROR" "$COLOR_RESET"
    return 1
  fi

  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    printf '%sNo GUI display detected, so Haruna playback is unavailable here.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi

  setsid haruna "$song_file" > /dev/null 2>&1 &
  display_name="$(relative_path "$song_file")"
  printf '%sPlaying in Haruna (detached):%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$display_name"
  return 0
}

parse_download_selection() {
  local raw_input="$1"
  local max_index="$2"
  local normalized
  local -a tokens=()
  local token
  local start
  local end
  local idx
  local -A seen=()

  PARSE_IMPORT_ERROR=""
  PARSED_DOWNLOAD_INDEXES=()

  normalized="${raw_input//[[:space:]]/}"
  if [[ -z "$normalized" ]]; then
    normalized="1"
  fi

  IFS=',' read -r -a tokens <<< "$normalized"
  if ((${#tokens[@]} == 0)); then
    PARSE_IMPORT_ERROR="Please enter a number, range, or list."
    return 1
  fi

  for token in "${tokens[@]}"; do
    if [[ -z "$token" ]]; then
      PARSE_IMPORT_ERROR="List format is invalid. Example: 1,3-5"
      return 1
    fi

    if [[ "$token" =~ ^[0-9]+$ ]]; then
      start="$token"
      end="$token"
    elif [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      start="${BASH_REMATCH[1]}"
      end="${BASH_REMATCH[2]}"
      if ((start > end)); then
        PARSE_IMPORT_ERROR="Range $token is descending. Use ascending like 1-8."
        return 1
      fi
    else
      PARSE_IMPORT_ERROR="Token '$token' is invalid. Use forms like 1, 2-4, 1,3-5."
      return 1
    fi

    if ((start < 1 || end > max_index)); then
      PARSE_IMPORT_ERROR="Selection '$token' is out of range. Use 1-${max_index}."
      return 1
    fi

    for ((idx=start; idx<=end; idx++)); do
      if [[ -z "${seen[$idx]+x}" ]]; then
        PARSED_DOWNLOAD_INDEXES+=("$idx")
        seen[$idx]=1
      fi
    done
  done

  if ((${#PARSED_DOWNLOAD_INDEXES[@]} == 0)); then
    PARSE_IMPORT_ERROR="Selection did not include any songs."
    return 1
  fi

  return 0
}

build_imported_basename_index() {
  local library_song
  local base_lower

  IMPORTED_MP3_BY_BASENAME=()

  while IFS= read -r -d '' library_song; do
    base_lower="$(basename "$library_song")"
    base_lower="${base_lower,,}"
    IMPORTED_MP3_BY_BASENAME["$base_lower"]=1
  done < <(find "$MUSIC_ROOT" -type f -iname '*.mp3' -print0 2>/dev/null || true)
}

list_recent_non_imported_downloads() {
  local limit="${1:-10}"
  local -a all_downloads=()
  local -a non_imported=()
  local download_song
  local base_lower

  DOWNLOAD_MP3_TOTAL=0
  DOWNLOAD_MP3_SKIPPED_IMPORTED=0
  RECENT_NON_IMPORTED_DOWNLOADS=()

  build_imported_basename_index

  mapfile -t all_downloads < <(
    find "$DOWNLOADS_DIR" -maxdepth 1 -type f -iname '*.mp3' -printf '%T@ %p\n' 2>/dev/null \
      | sort -nr \
      | cut -d' ' -f2-
  )

  DOWNLOAD_MP3_TOTAL=${#all_downloads[@]}

  for download_song in "${all_downloads[@]}"; do
    base_lower="$(basename "$download_song")"
    base_lower="${base_lower,,}"
    if [[ -n "${IMPORTED_MP3_BY_BASENAME[$base_lower]+x}" ]]; then
      ((DOWNLOAD_MP3_SKIPPED_IMPORTED+=1))
      continue
    fi

    non_imported+=("$download_song")
    if ((${#non_imported[@]} >= limit)); then
      break
    fi
  done

  if ((${#non_imported[@]} > 0)); then
    RECENT_NON_IMPORTED_DOWNLOADS=("${non_imported[@]}")
  fi

  return 0
}

recommend_channel_for_song() {
  local song_file="$1"
  shift
  local -a channels=("$@")
  local song_name_lower
  local channel_lower
  local key
  local target
  local rule
  local tokenized
  local token
  local -A channel_by_lower=()
  local -a rules=(
    "lofi:lofi"
    "chill:chill"
    "indie:indie"
    "vibe:vibes"
    "vibes:vibes"
    "waiting:vibes"
    "lunar:lunar-mix"
    "moon:lunar-mix"
    "space:lunar-mix"
    "8bit:bits-tech"
    "gba:bits-tech"
    "tech:bits-tech"
    "bit:bits-tech"
  )

  song_name_lower="$(basename "$song_file")"
  song_name_lower="${song_name_lower,,}"

  for channel in "${channels[@]}"; do
    channel_by_lower["${channel,,}"]="$channel"
  done

  for rule in "${rules[@]}"; do
    key="${rule%%:*}"
    target="${rule##*:}"
    if [[ "$song_name_lower" == *"$key"* ]] && [[ -n "${channel_by_lower[$target]+x}" ]]; then
      printf '%s\n' "${channel_by_lower[$target]}"
      return 0
    fi
  done

  for channel in "${channels[@]}"; do
    channel_lower="${channel,,}"
    if [[ "$song_name_lower" == *"$channel_lower"* ]]; then
      printf '%s\n' "$channel"
      return 0
    fi

    tokenized="${channel_lower//[^a-z0-9]/ }"
    for token in $tokenized; do
      if ((${#token} >= 3)) && [[ "$song_name_lower" == *"$token"* ]]; then
        printf '%s\n' "$channel"
        return 0
      fi
    done
  done

  return 1
}

select_download_song_top10() {
  local -a songs=()
  local -a selected_indexes=()
  local input
  local idx
  local i

  list_recent_non_imported_downloads 10
  songs=("${RECENT_NON_IMPORTED_DOWNLOADS[@]}")

  if ((${#songs[@]} == 0)); then
    if ((DOWNLOAD_MP3_TOTAL == 0)); then
      printf '%sNo MP3 files found in %s.%s\n' "$COLOR_WARN" "$DOWNLOADS_DIR" "$COLOR_RESET"
    else
      printf '%sNo importable MP3 files found in %s (all appear already imported).%s\n' "$COLOR_WARN" "$DOWNLOADS_DIR" "$COLOR_RESET"
    fi
    return 1
  fi

  print_section "Import Song(s) - Newest 10 MP3s"
  for i in "${!songs[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "$(basename "${songs[$i]}")"
  done
  printf '  b) Back\n'

  while true; do
    if ! input="$(prompt_with_default "Pick song index/range/list (1, 1-8, 1,3-5)" "1")"; then
      return 1
    fi
    input="${input//[[:space:]]/}"
    input="${input,,}"

    if [[ "$input" == "b" ]]; then
      return 1
    fi

    if parse_download_selection "$input" "${#songs[@]}"; then
      selected_indexes=("${PARSED_DOWNLOAD_INDEXES[@]}")
      SELECTED_DOWNLOAD_SONGS=()
      SELECTED_DOWNLOAD_SONG=""

      for idx in "${selected_indexes[@]}"; do
        SELECTED_DOWNLOAD_SONGS+=("${songs[$((idx - 1))]}")
      done

      if ((${#SELECTED_DOWNLOAD_SONGS[@]} > 0)); then
        SELECTED_DOWNLOAD_SONG="${SELECTED_DOWNLOAD_SONGS[0]}"
      fi
      return 0
    fi

    if [[ -n "$PARSE_IMPORT_ERROR" ]]; then
      printf '%s%s%s\n' "$COLOR_WARN" "$PARSE_IMPORT_ERROR" "$COLOR_RESET"
    else
      printf '%sPick a valid selection or b to go back.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    fi
  done
}

select_channel() {
  local -a channels=()
  local recommended_channel="${1:-}"
  local recommended_index=""
  local input
  local i

  mapfile -t channels < <(find "$MUSIC_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

  if ((${#channels[@]} == 0)); then
    printf '%sNo Channels folders found in %s.%s\n' "$COLOR_ERROR" "$MUSIC_ROOT" "$COLOR_RESET"
    return 1
  fi

  print_section "Channels"
  for i in "${!channels[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${channels[$i]}"
    if [[ -n "$recommended_channel" ]] && [[ "${channels[$i],,}" == "${recommended_channel,,}" ]]; then
      recommended_index="$((i + 1))"
    fi
  done
  printf '  b) Back\n'

  if [[ -n "$recommended_index" ]]; then
    printf '%sRecommended channel:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${channels[$((recommended_index - 1))]}"
  else
    printf '%sNo recommendation available for this filename. Choose a channel.%s\n' "$COLOR_DIM" "$COLOR_RESET"
  fi

  while true; do
    if [[ -n "$recommended_index" ]]; then
      if ! input="$(prompt_with_default "Pick a channel" "$recommended_index")"; then
        return 1
      fi
    else
      if ! input="$(prompt_with_default "Pick a channel (no default)" "")"; then
        return 1
      fi
    fi
    input="${input//[[:space:]]/}"
    input="${input,,}"

    if [[ "$input" == "b" ]]; then
      return 1
    fi

    if [[ -z "$input" ]] && [[ -z "$recommended_index" ]]; then
      printf '%sNo default is set here, please enter a channel number.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      continue
    fi

    if [[ "$input" =~ ^[0-9]+$ ]] && ((input >= 1 && input <= ${#channels[@]})); then
      SELECTED_CHANNEL="${channels[$((input - 1))]}"
      return 0
    fi

    printf '%sPick a valid number or b to go back.%s\n' "$COLOR_WARN" "$COLOR_RESET"
  done
}

select_library_song() {
  local -a songs=()
  local input
  local i

  mapfile -t songs < <(find "$MUSIC_ROOT" -type f -iname '*.mp3' | sort)

  if ((${#songs[@]} == 0)); then
    printf '%sNo MP3 files found in this music library.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi

  print_section "Update Comments - Library Songs"
  for i in "${!songs[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "$(relative_path "${songs[$i]}")"
  done
  printf '  b) Back\n'

  while true; do
    input="$(prompt_with_default "Pick a song" "1")"
    input="${input,,}"

    if [[ "$input" == "b" ]]; then
      return 1
    fi

    if [[ "$input" =~ ^[0-9]+$ ]] && ((input >= 1 && input <= ${#songs[@]})); then
      SELECTED_LIBRARY_SONG="${songs[$((input - 1))]}"
      return 0
    fi

    printf '%sPick a valid number or b to go back.%s\n' "$COLOR_WARN" "$COLOR_RESET"
  done
}

SEARCH_RESULT_SONGS=()
SEARCH_KEYWORD=""
SEARCH_INCLUDE_BLOCKED=0

search_songs_by_keyword() {
  local keyword
  local include_blocked=0
  local -a fields=()
  local -a all_songs=()
  local -a matched_paths=()
  local -a matched_display=()
  local -a selected_indexes=()
  local field_input input
  local song_file display_name title comment field_values
  local i idx
  local total_matched=0
  local -a search_tokens=()
  local search_token
  local all_matched

  SEARCH_RESULT_SONGS=()

  print_section "Search Songs by Keyword"
  if ! keyword="$(prompt_with_default "Keyword (case-insensitive)" "")"; then
    return 1
  fi
  keyword="$(normalize_single_line_text "$keyword")"
  if [[ -z "$keyword" ]]; then
    printf '%sKeyword cannot be empty.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi
  keyword="${keyword,,}"
  SEARCH_KEYWORD="$keyword"

  printf '\n%sSearch in which fields?%s\n' "$COLOR_DIM" "$COLOR_RESET"
  printf '  1) Title\n'
  printf '  2) Comment\n'
  printf '  3) Filename\n'
  printf '  4) Music Theme\n'
  printf '  5) Why Made\n'
  printf '  6) Backstory\n'
  printf '  7) Radio Reason\n'
  printf '  8) Listener Takeaway\n'
  printf '  9) Vibe Summary\n'
  printf '  A) All fields\n'

  if ! field_input="$(prompt_with_default "Fields (comma or A)" "A")"; then
    return 1
  fi
  field_input="${field_input,,}"
  field_input="${field_input//[[:space:]]/}"

  if [[ "$field_input" == "a" ]]; then
    fields=(title comment filename theme why_made backstory radio_reason listener_takeaway vibe_summary)
  else
    IFS=',' read -r -a selected_nums <<< "$field_input"
    for num in "${selected_nums[@]}"; do
      case "$num" in
        1) fields+=(title) ;;
        2) fields+=(comment) ;;
        3) fields+=(filename) ;;
        4) fields+=(theme) ;;
        5) fields+=(why_made) ;;
        6) fields+=(backstory) ;;
        7) fields+=(radio_reason) ;;
        8) fields+=(listener_takeaway) ;;
        9) fields+=(vibe_summary) ;;
      esac
    done
  fi

  if ((${#fields[@]} == 0)); then
    printf '%sNo valid fields selected.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi

  if list_blocked_channels >/dev/null 2>&1; then
    if ask_yes_no_default_yes "Include blocked channels in search?"; then
      include_blocked=1
    fi
  fi
  SEARCH_INCLUDE_BLOCKED="$include_blocked"

  if ((include_blocked)); then
    mapfile -t all_songs < <(find "$MUSIC_ROOT" -type f -iname '*.mp3' 2>/dev/null | sort)
  else
    mapfile -t all_songs < <(find "$MUSIC_ROOT" \
      \( -type d -exec test -e '{}/.blocked' ';' -prune \) -o \
      \( -type f -iname '*.mp3' -print \) \
      2>/dev/null | sort)
  fi

  if ((${#all_songs[@]} == 0)); then
    printf '%sNo MP3 files found in the music library.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 1
  fi

  printf '%sSearching %d songs for "%s"...%s\n' "$COLOR_DIM" "${#all_songs[@]}" "$keyword" "$COLOR_RESET"

  for song_file in "${all_songs[@]}"; do
    field_values=""

    for field_type in "${fields[@]}"; do
      case "$field_type" in
        title)
          field_values+=" $(get_song_title "$song_file")"
          ;;
        comment)
          field_values+=" $(get_song_comment "$song_file")"
          ;;
        filename)
          field_values+=" $(basename "$song_file")"
          ;;
        theme)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_MUSIC_THEME" || true)"
          ;;
        why_made)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_WHY_MADE" || true)"
          ;;
        backstory)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_BACKSTORY" || true)"
          ;;
        radio_reason)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_RADIO_REASON" || true)"
          ;;
        listener_takeaway)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_LISTENER_TAKEAWAY" || true)"
          ;;
        vibe_summary)
          field_values+=" $(get_song_metadata_tag "$song_file" "$MIDORI_TAG_VIBE_SUMMARY" || true)"
          ;;
      esac
    done

    field_values="${field_values,,}"
    read -r -a search_tokens <<< "$keyword"
    all_matched=1
    for search_token in "${search_tokens[@]}"; do
      if [[ "$field_values" != *"$search_token"* ]]; then
        all_matched=0
        break
      fi
    done
    if ((all_matched)); then
      display_name="$(relative_path "$song_file")"
      matched_paths+=("$song_file")
      matched_display+=("$display_name")
      ((++total_matched))
    fi
  done

  if ((total_matched == 0)); then
    printf '%sNo matches found for "%s".%s\n' "$COLOR_WARN" "$keyword" "$COLOR_RESET"
    return 1
  fi

  local page=0
  local per_page=20
  local total_pages=$(( (total_matched + per_page - 1) / per_page ))
  local start_idx end_idx

  while true; do
    start_idx=$((page * per_page))
    end_idx=$((start_idx + per_page))
    if ((end_idx > total_matched)); then
      end_idx=$total_matched
    fi

    print_section "Search Results: \"$keyword\" ($total_matched matches)"
    if ((total_pages > 1)); then
      printf '%sPage %d of %d%s\n' "$COLOR_DIM" "$((page + 1))" "$total_pages" "$COLOR_RESET"
    fi

    for ((i=start_idx; i<end_idx; i++)); do
      printf '  %d) %s\n' "$((i + 1))" "${matched_display[$i]}"
    done

    printf '  n) Next page\n'
    printf '  p) Previous page\n'
    printf '  b) Back\n'

    if ! input="$(prompt_with_default "Pick song number or navigate" "")"; then
      return 1
    fi
    input="${input,,}"
    input="${input//[[:space:]]/}"

    if [[ "$input" == "b" ]]; then
      return 1
    elif [[ "$input" == "n" ]]; then
      if ((page + 1 < total_pages)); then
        ((++page))
      else
        printf '%sAlready on last page.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      fi
      continue
    elif [[ "$input" == "p" ]]; then
      if ((page > 0)); then
        ((--page))
      else
        printf '%sAlready on first page.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      fi
      continue
    fi

    if parse_download_selection "$input" "$total_matched"; then
      selected_indexes=("${PARSED_DOWNLOAD_INDEXES[@]}")
      SEARCH_RESULT_SONGS=()
      for idx in "${selected_indexes[@]}"; do
        SEARCH_RESULT_SONGS+=("${matched_paths[$((idx - 1))]}")
      done
      return 0
    fi

    if [[ -n "$PARSE_IMPORT_ERROR" ]]; then
      printf '%s%s%s\n' "$COLOR_WARN" "$PARSE_IMPORT_ERROR" "$COLOR_RESET"
    else
      printf '%sPick a valid number, n, p, or b.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    fi
  done
}

view_song_details() {
  local song_file="$1"
  local song_title current_comment why_made backstory radio_reason music_theme listener_takeaway vibe_summary

  song_title="$(get_song_title "$song_file")"
  current_comment="$(get_song_comment "$song_file")"
  why_made="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_WHY_MADE" || true)"
  backstory="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_BACKSTORY" || true)"
  radio_reason="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_RADIO_REASON" || true)"
  music_theme="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_MUSIC_THEME" || true)"
  listener_takeaway="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_LISTENER_TAKEAWAY" || true)"
  vibe_summary="$(get_song_metadata_tag "$song_file" "$MIDORI_TAG_VIBE_SUMMARY" || true)"

  print_section "Song Details"
  printf '%sFile:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$(relative_path "$song_file")"
  printf '%sTitle:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${song_title:-none}"
  printf '%sComment:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${current_comment:-none}"
  printf '%sTheme:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${music_theme:-none}"
  printf '%sWhy Made:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${why_made:-none}"
  printf '%sBackstory:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${backstory:-none}"
  printf '%sRadio Reason:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${radio_reason:-none}"
  printf '%sListener Takeaway:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${listener_takeaway:-none}"
  printf '%sVibe Summary:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "${vibe_summary:-none}"
}

is_outdated_comment() {
  local comment="$1"
  local comment_lower

  comment_lower="$(normalize_single_line_text "$comment")"
  comment_lower="${comment_lower,,}"

  if [[ -z "$comment_lower" ]]; then
    return 1
  fi

  if [[ "$comment_lower" == *"made with suno"* ]] || \
     [[ "$comment_lower" == *"produced with suno"* ]] || \
     [[ "$comment_lower" == *"from midori ai radio"* ]]; then
    return 0
  fi

  return 1
}

list_stale_songs_oldest_first() {
  local song_file
  local song_comment
  local found_outdated=0

  while IFS=$'\t' read -r _ song_file; do
    if [[ -z "$song_file" ]]; then
      continue
    fi

    song_comment="$(get_song_comment "$song_file")"
    if is_outdated_comment "$song_comment"; then
      printf '%s\n' "$song_file"
      found_outdated=1
    fi
  done < <(find "$MUSIC_ROOT" \
    \( -type d -exec test -e '{}/.blocked' ';' -prune \) -o \
    \( -type f -iname '*.mp3' -printf '%T@\t%p\n' \) \
    2>/dev/null | sort -n || true)

  if ((found_outdated == 1)); then
    return 0
  fi

  while IFS=$'\t' read -r _ song_file; do
    if [[ -z "$song_file" ]]; then
      continue
    fi
    printf '%s\n' "$song_file"
  done < <(find "$MUSIC_ROOT" \
    \( -type d -exec test -e '{}/.blocked' ';' -prune \) -o \
    \( -type f -iname '*.mp3' -printf '%T@\t%p\n' \) \
    2>/dev/null | sort -n || true)
}

select_comment_update_mode() {
  local input
  SELECTED_COMMENT_MODE=""

  while true; do
    print_section "Comment Strategy"
    printf '%sChoose how to continue:%s\n' "$COLOR_DIM" "$COLOR_RESET"
    printf '  1) Use\n'
    printf '  2) Feedback\n'
    printf '  3) Replace\n'
    printf '  4) Cancel\n'

    if ! input="$(prompt_with_default "Choose strategy" "1")"; then
      return 130
    fi
    input="${input,,}"

    case "$input" in
      1|a|accept|use|as-is|asis|recommended|recommend)
        SELECTED_COMMENT_MODE="as_is"
        return 0
        ;;
      2|f|feedback)
        SELECTED_COMMENT_MODE="feedback"
        return 0
        ;;
      3|r|replace|manual)
        SELECTED_COMMENT_MODE="replace"
        return 0
        ;;
      4|c|cancel|back|b)
        return 130
        ;;
      *)
        printf '%sChoose 1, 2, 3, or 4.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        ;;
    esac
  done
}

review_statement_with_feedback_loop() {
  local song_file="$1"
  local title="$2"
  local raw_statement="$3"
  local initial_draft="${4:-}"
  local pre_refine_first="${5:-0}"
  local action
  local feedback
  local prompt
  local draft
  local continue_mode=0
  local -a history=()
  local idx

  LAST_POLISHED_STATEMENT=""

  if [[ -n "$initial_draft" ]]; then
    draft="$initial_draft"
    OPENCODE_CONTINUE_ALLOWED=1
  else
    if ! draft="$(fix_song_statement "$song_file" "$title" "$raw_statement")"; then
      printf '%sThere was an error while running opencode.%s\n' "$COLOR_ERROR" "$COLOR_RESET"
      return 1
    fi
    OPENCODE_CONTINUE_ALLOWED=1
  fi

  if [[ "$pre_refine_first" == "1" ]]; then
    history+=("$draft")
    if ! feedback="$(prompt_with_default "Feedback" "$DEFAULT_REFINE_FEEDBACK")"; then
      return 130
    fi
    prompt="$(_build_refinement_prompt "$song_file" "$title" "$raw_statement" "$draft" "$feedback")"
    if [[ "$OPENCODE_CONTINUE_ALLOWED" == "1" ]]; then
      continue_mode=1
    else
      continue_mode=0
    fi

    while true; do
      if draft="$(run_comment_prompt "$prompt" "OpenCode Refine" "$continue_mode")"; then
        OPENCODE_CONTINUE_ALLOWED=1
        break
      fi

      printf '%sOpenCode failed to refine this round.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      if ask_yes_no_default_yes "Retry this refine round?"; then
        continue
      fi
      return 1
    done
  fi

  while true; do
    print_section "Draft Review"
    printf '%s%s%s\n' "$COLOR_DIM" "Current draft:" "$COLOR_RESET"
    printf '%s\n' "$draft"
    printf '\n'
    printf '  1) Accept\n'
    printf '  2) Refine\n'
    printf '  3) Undo\n'
    printf '  4) Cancel\n'

    if ! action="$(prompt_with_default "Choose action" "1")"; then
      return 130
    fi
    action="${action,,}"

    case "$action" in
      1|a|accept)
        LAST_POLISHED_STATEMENT="$draft"
        return 0
        ;;
      2|r|refine)
        history+=("$draft")
        if ! feedback="$(prompt_with_default "Feedback" "$DEFAULT_REFINE_FEEDBACK")"; then
          return 130
        fi
        prompt="$(_build_refinement_prompt "$song_file" "$title" "$raw_statement" "$draft" "$feedback")"
        if [[ "$OPENCODE_CONTINUE_ALLOWED" == "1" ]]; then
          continue_mode=1
        else
          continue_mode=0
        fi

        while true; do
          if draft="$(run_comment_prompt "$prompt" "OpenCode Refine" "$continue_mode")"; then
            OPENCODE_CONTINUE_ALLOWED=1
            break
          fi

          printf '%sOpenCode failed to refine this round.%s\n' "$COLOR_WARN" "$COLOR_RESET"
          if ask_yes_no_default_yes "Retry this refine round?"; then
            continue
          fi
          return 1
        done
        ;;
      3|u|undo)
        if ((${#history[@]} == 0)); then
          printf '%sNo previous draft available yet.%s\n' "$COLOR_WARN" "$COLOR_RESET"
          continue
        fi
        idx=$(( ${#history[@]} - 1 ))
        draft="${history[$idx]}"
        unset "history[$idx]"
        printf '%sReverted to previous draft.%s\n' "$COLOR_SUCCESS" "$COLOR_RESET"
        ;;
      4|c|cancel)
        return 130
        ;;
      *)
        printf '%sChoose 1, 2, 3, or 4.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        ;;
    esac
  done
}

update_comment_for_song() {
  local song_file="$1"
  local song_title
  local current_comment
  local raw_statement
  local qna_seed_statement=""
  local seed_statement_default=""
  local recommendation_seed
  local recommendation_draft=""
  local selected_mode="replace"
  local mode_status=0
  local review_status=0
  local display_name

  OPENCODE_CONTINUE_ALLOWED=0
  display_name="$(relative_path "$song_file")"
  song_title="$(get_song_title "$song_file")"
  current_comment="$(get_song_comment "$song_file")"

  print_section "Song Details"
  printf '%sSong:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$display_name"
  printf '%sTitle:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$song_title"
  if [[ -n "$current_comment" ]]; then
    printf '%sCurrent Comment:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$current_comment"
  else
    printf '%sCurrent Comment:%s (empty)\n' "$COLOR_DIM" "$COLOR_RESET"
  fi

  if collect_song_qna_inputs "$song_file" "$song_title" "$current_comment"; then
    :
  else
    review_status=$?
    if [[ "$review_status" -eq 130 ]]; then
      printf '%sComment update canceled.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      return 130
    fi
    return 1
  fi

  qna_seed_statement="$(build_qna_seed_statement "$LAST_QNA_WHY_MADE" "$LAST_QNA_BACKSTORY" "$LAST_QNA_RADIO_REASON" "$LAST_QNA_MUSIC_THEME" "$LAST_QNA_LISTENER_TAKEAWAY")"
  recommendation_seed="$qna_seed_statement"
  if [[ -z "$(normalize_single_line_text "$recommendation_seed")" ]]; then
    recommendation_seed="$DEFAULT_RAW_STATEMENT"
  fi
  seed_statement_default="$(normalize_single_line_text "$recommendation_seed")"

  if recommendation_draft="$(fix_song_statement "$song_file" "$song_title" "$recommendation_seed" "Crafting Recommended Comment")"; then
    OPENCODE_CONTINUE_ALLOWED=1
    print_section "Recommended Comment"
    printf '%s%s%s\n' "$COLOR_DIM" "Draft suggestion:" "$COLOR_RESET"
    printf '%s\n' "$recommendation_draft"
    printf '\n'
  else
    printf '%sCould not create a recommendation. Falling back to Replace flow.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    recommendation_draft=""
  fi

  if [[ -n "$recommendation_draft" ]]; then
    if select_comment_update_mode; then
      selected_mode="$SELECTED_COMMENT_MODE"
    else
      mode_status=$?
      if [[ "$mode_status" -eq 130 ]]; then
        printf '%sComment update canceled.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        return 130
      fi
      return 1
    fi
  else
    selected_mode="replace"
  fi

  if [[ "$selected_mode" == "as_is" ]]; then
    LAST_POLISHED_STATEMENT="$recommendation_draft"
  elif [[ "$selected_mode" == "feedback" ]]; then
    if review_statement_with_feedback_loop "$song_file" "$song_title" "$recommendation_seed" "$recommendation_draft" "1"; then
      :
    else
      review_status=$?
      if [[ "$review_status" -eq 130 ]]; then
        printf '%sComment update canceled.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        return 130
      fi
      return 1
    fi
  else
    if ! raw_statement="$(prompt_with_default "Seed statement" "$seed_statement_default")"; then
      printf '%sComment update canceled.%s\n' "$COLOR_WARN" "$COLOR_RESET"
      return 130
    fi

    if review_statement_with_feedback_loop "$song_file" "$song_title" "$raw_statement"; then
      :
    else
      review_status=$?
      if [[ "$review_status" -eq 130 ]]; then
        printf '%sComment update canceled.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        return 130
      fi
      return 1
    fi
  fi

  if write_song_metadata_in_place \
    "$song_file" \
    "$LAST_POLISHED_STATEMENT" \
    "$LAST_QNA_WHY_MADE" \
    "$LAST_QNA_BACKSTORY" \
    "$LAST_QNA_RADIO_REASON" \
    "$LAST_QNA_MUSIC_THEME" \
    "$LAST_QNA_LISTENER_TAKEAWAY"; then
    printf '%sUpdated comment metadata:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$display_name"
    return 0
  fi

  printf '%sFailed to write metadata for:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$display_name"
  return 1
}

update_stale_comments_flow() {
  local -a stale_songs=()
  local song_file
  local action
  local display_name
  local current_comment
  local update_status
  local found_outdated=0

  mapfile -t stale_songs < <(list_stale_songs_oldest_first)

  for song_file in "${stale_songs[@]}"; do
    current_comment="$(get_song_comment "$song_file")"
    if is_outdated_comment "$current_comment"; then
      found_outdated=1
      break
    fi
  done

  if ((${#stale_songs[@]} == 0)); then
    printf '%sNo MP3 files found in the music library.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 0
  fi

  if ((found_outdated == 0)); then
    printf '%sNo outdated markers found. Showing oldest songs for review.%s\n' "$COLOR_DIM" "$COLOR_RESET"
  fi

  while true; do
    for song_file in "${stale_songs[@]}"; do
      current_comment="$(get_song_comment "$song_file")"

      while true; do
        print_section "Update Stale Comments"
        display_name="$(relative_path "$song_file")"
        printf '%sSelected:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$display_name"
        if [[ -n "$current_comment" ]]; then
          printf '%sCurrent Comment:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$current_comment"
        else
          printf '%sCurrent Comment:%s (empty)\n' "$COLOR_DIM" "$COLOR_RESET"
        fi
        printf '  1) Play\n'
        printf '  2) Fix\n'
        printf '  3) Skip\n'
        printf '  4) Back\n'

        action="$(prompt_with_default "Choose action (p also plays)" "2")"
        action="${action,,}"

        case "$action" in
          p|1|play)
            play_song_detached "$song_file" || true
            ;;
          2|f|fix|update)
            if update_comment_for_song "$song_file"; then
              if ask_yes_no_default_yes "More Updates?"; then
                break
              fi
              return 0
            fi

            update_status=$?
            if [[ "$update_status" -eq 130 ]]; then
              if ask_yes_no_default_yes "More Updates?"; then
                break
              fi
              return 0
            fi

            printf '%sCould not update that song.%s\n' "$COLOR_WARN" "$COLOR_RESET"
            ;;
          3|s|skip)
            break
            ;;
          4|b|back)
            return 0
            ;;
          *)
            printf '%sChoose 1, 2, 3, or 4 (or press p).%s\n' "$COLOR_WARN" "$COLOR_RESET"
            ;;
        esac
      done
    done

    mapfile -t stale_songs < <(list_stale_songs_oldest_first)
    if ((${#stale_songs[@]} == 0)); then
      printf '%sNo more songs to review. Great work!%s\n' "$COLOR_SUCCESS" "$COLOR_RESET"
      return 0
    fi

    if ! ask_yes_no_default_yes "Queue pass complete. Review remaining songs?"; then
      return 0
    fi
  done
}

import_songs_flow() {
  local -a selected_songs=()
  local -a channels=()
  local source_song
  local channel
  local recommended_channel=""
  local destination
  local destination_display
  local update_status

  while true; do
    if ! select_download_song_top10; then
      return 0
    fi
    selected_songs=("${SELECTED_DOWNLOAD_SONGS[@]}")
    mapfile -t channels < <(find "$MUSIC_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

    for source_song in "${selected_songs[@]}"; do
      print_section "Import Queue Item"
      printf '%sSelected download:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$(basename "$source_song")"
      recommended_channel=""
      if ((${#channels[@]} > 0)); then
        recommended_channel="$(recommend_channel_for_song "$source_song" "${channels[@]}" || true)"
      fi

      if ! select_channel "$recommended_channel"; then
        return 0
      fi
      channel="$SELECTED_CHANNEL"

      destination="$(build_unique_destination "${MUSIC_ROOT}/${channel}/$(basename "$source_song")")"
      cp -- "$source_song" "$destination"
      destination_display="$(relative_path "$destination")"
      printf '%sImported:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$destination_display"

      if update_comment_for_song "$destination"; then
        :
      else
        update_status=$?
        if [[ "$update_status" -ne 130 ]]; then
          printf '%sComment update failed for imported song.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        fi
      fi
    done

    if ! ask_yes_no_default_yes "More Updates?"; then
      return 0
    fi
  done
}

update_comments_flow() {
  local song_file
  local action
  local update_status

  while true; do
    if ! select_library_song; then
      return 0
    fi
    song_file="$SELECTED_LIBRARY_SONG"

    while true; do
      print_section "Song Actions"
      printf '%sSelected:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$(relative_path "$song_file")"
      printf '  1) Play\n'
      printf '  2) Update Comment\n'
      printf '  3) Back\n'

      action="$(prompt_with_default "Choose action (p also plays)" "2")"
      action="${action,,}"

      case "$action" in
        p|1|play)
          play_song_detached "$song_file" || true
          ;;
        2|u|update|comment)
          if update_comment_for_song "$song_file"; then
            if ask_yes_no_default_yes "More Updates?"; then
              break
            fi
            return 0
          fi
          update_status=$?
          if [[ "$update_status" -eq 130 ]]; then
            if ask_yes_no_default_yes "More Updates?"; then
              break
            fi
            return 0
          fi
          printf '%sCould not update that song.%s\n' "$COLOR_WARN" "$COLOR_RESET"
          ;;
        3|b|back)
          break
          ;;
        *)
          printf '%sChoose 1, 2, or 3 (or press p).%s\n' "$COLOR_WARN" "$COLOR_RESET"
          ;;
      esac
    done
  done
}

search_and_manage_flow() {
  local song_file
  local action
  local update_status

  while true; do
    if ! search_songs_by_keyword; then
      return 0
    fi

    if ((${#SEARCH_RESULT_SONGS[@]} == 0)); then
      return 0
    fi

    for song_file in "${SEARCH_RESULT_SONGS[@]}"; do
      while true; do
        print_section "Search Result Actions"
        printf '%sSelected:%s %s\n' "$COLOR_DIM" "$COLOR_RESET" "$(relative_path "$song_file")"
        printf '  1) Play\n'
        printf '  2) Update Comment\n'
        printf '  3) View Details\n'
        printf '  4) Trash\n'
        printf '  5) Skip\n'
        printf '  6) Back to search\n'

        action="$(prompt_with_default "Choose action" "2")"
        action="${action,,}"

        case "$action" in
          p|1|play)
            play_song_detached "$song_file" || true
            ;;
          2|u|update|comment)
            if update_comment_for_song "$song_file"; then
              break
            fi
            update_status=$?
            if [[ "$update_status" -eq 130 ]]; then
              break
            fi
            printf '%sCould not update that song.%s\n' "$COLOR_WARN" "$COLOR_RESET"
            ;;
          3|v|view|details)
            view_song_details "$song_file"
            ;;
          4|t|trash|delete|remove)
            if ask_yes_no_default_yes "Trash this song?"; then
              if trash_file "$song_file"; then
                printf '%sSong trashed. Skipping to next result.%s\n' "$COLOR_SUCCESS" "$COLOR_RESET"
                break
              fi
            fi
            ;;
          5|s|skip|next)
            break
            ;;
          6|b|back)
            return 0
            ;;
          *)
            printf '%sChoose 1-6 (or press p).%s\n' "$COLOR_WARN" "$COLOR_RESET"
            ;;
        esac
      done
    done

    if ! ask_yes_no_default_yes "New search?"; then
      return 0
    fi
  done
}

cache_all_vibes_flow() {
  local -a songs=()
  local include_blocked=0
  local total count success failed skipped
  local song_file display_name
  local rc

  if list_blocked_channels >/dev/null 2>&1; then
    if ask_yes_no_default_yes "Include blocked channels?"; then
      include_blocked=1
    fi
  fi

  if ((include_blocked)); then
    mapfile -t songs < <(find "$MUSIC_ROOT" -type f -iname '*.mp3' 2>/dev/null | sort)
  else
    mapfile -t songs < <(find "$MUSIC_ROOT" \
      \( -type d -exec test -e '{}/.blocked' ';' -prune \) -o \
      \( -type f -iname '*.mp3' -print \) \
      2>/dev/null | sort)
  fi

  total=${#songs[@]}
  if ((total == 0)); then
    printf '%sNo MP3 files found.%s\n' "$COLOR_WARN" "$COLOR_RESET"
    return 0
  fi

  local max_workers=$(( $(nproc) / 2 ))
  (( max_workers < 1 )) && max_workers=1

  print_section "Cache All Vibes"
  printf '%sThis will force re-analyze %d songs with Essentia.%s\n' "$COLOR_WARN" "$total" "$COLOR_RESET"
  printf '%sEstimated time: ~%d minutes with %d workers (~30s per song serial).%s\n' "$COLOR_DIM" "$(( (total * 30 + max_workers * 59) / (max_workers * 60) ))" "$max_workers" "$COLOR_RESET"

  if ! ask_yes_no_default_yes "Proceed?"; then
    return 0
  fi
  local active=0
  local progress_dir lock_fd counter_file results_file
  progress_dir="$(mktemp -d /tmp/vibe-cache-parallel-XXXXXX)"
  lock_fd="$progress_dir/lock"
  counter_file="$progress_dir/counter"
  echo 0 > "$counter_file"
  results_file="$progress_dir/results"
  : > "$results_file"

  printf '%sUsing %d parallel workers.%s\n' "$COLOR_DIM" "$max_workers" "$COLOR_RESET"

  for song_file in "${songs[@]}"; do
    while (( active >= max_workers )); do
      wait -n 2>/dev/null || true
      (( --active )) || true
    done

    (
      set +e
      local dname n
      dname="$(relative_path "$song_file")"

      exec 200>"$lock_fd"
      flock 200
      read -r n < "$counter_file"
      (( ++n ))
      echo "$n" > "$counter_file"
      printf '\n%s[%d/%d]%s %s\n' "$COLOR_ACCENT" "$n" "$total" "$COLOR_RESET" "$dname"
      exec 200>&-

      if get_cached_essentia_analysis "$song_file" "1" >/dev/null 2>&1; then
        printf '%s  Cached:%s %s\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$dname"
        echo "ok" >> "$results_file"
      else
        printf '%s  Failed:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$dname"
        echo "fail" >> "$results_file"
      fi
    ) &
    (( ++active ))
  done

  wait || true

  local success=0 failed=0
  if [[ -f "$results_file" ]]; then
    success=$(grep -cx 'ok' "$results_file" 2>/dev/null || echo 0)
    failed=$(grep -cx 'fail' "$results_file" 2>/dev/null || echo 0)
  fi
  rm -rf "$progress_dir"

  print_section "Cache All Summary"
  printf '%sTotal:%s %d\n' "$COLOR_DIM" "$COLOR_RESET" "$total"
  printf '%sCached:%s %d\n' "$COLOR_SUCCESS" "$COLOR_RESET" "$success"
  if ((failed > 0)); then
    printf '%sFailed:%s %d\n' "$COLOR_ERROR" "$COLOR_RESET" "$failed"
  fi
}

manage_channels_flow() {
  local action

  while true; do
    print_section "Manage Channels"
    list_blocked_channels || true
    printf '\n'
    printf '  1) Block a channel\n'
    printf '  2) Unblock a channel\n'
    printf '  3) Back\n'

    action="$(prompt_with_default "Choose action" "1")"
    action="${action,,}"

    case "$action" in
      1|b|block)
        block_channel_flow
        ;;
      2|u|unblock)
        unblock_channel_flow
        ;;
      3|q|quit|back)
        return 0
        ;;
      *)
        printf '%sChoose 1, 2, or 3.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        ;;
    esac
  done
}

main_menu() {
  local choice

  while true; do
    print_splash
    print_section "Main Menu"
    printf '  1) Import Song(s)\n'
    printf '  2) Update Comments\n'
    printf '  3) Update Stale Comments\n'
    printf '  4) Search & Manage Songs\n'
    printf '  5) Cache All Vibes\n'
    printf '  6) Block/Unblock Channels\n'
    printf '  7) Exit\n'

    choice="$(prompt_with_default "Select option" "1")"
    choice="${choice,,}"

    case "$choice" in
      1|i|import)
        import_songs_flow
        ;;
      2|u|update)
        update_comments_flow
        ;;
      3|s|stale|fix|outdated)
        update_stale_comments_flow
        ;;
      4|f|find|search|manage)
        search_and_manage_flow
        ;;
      5|c|cache|vibes)
        cache_all_vibes_flow
        ;;
      6|b|block|channels)
        manage_channels_flow
        ;;
      7|e|exit|q|quit)
        printf '%sDone. See you next session.%s\n' "$COLOR_SUCCESS" "$COLOR_RESET"
        return 0
        ;;
      *)
        printf '%sChoose 1, 2, 3, 4, 5, 6, or 7.%s\n' "$COLOR_WARN" "$COLOR_RESET"
        ;;
    esac
  done
}

main() {
  ESSENTIA_BACKEND="${ESSENTIA_BACKEND,,}"

  if ! command -v opencode >/dev/null 2>&1; then
    printf '%sThe opencode CLI is required but was not found in PATH.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
    return 127
  fi

  if ! command -v ffmpeg >/dev/null 2>&1; then
    printf '%sffmpeg is required but was not found in PATH.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
    return 127
  fi

  if [[ "$ESSENTIA_BACKEND" != "off" && "$ESSENTIA_BACKEND" != "uv" ]]; then
    printf '%sESSENTIA_BACKEND must be "uv" or "off", got:%s %s\n' "$COLOR_ERROR" "$COLOR_RESET" "$ESSENTIA_BACKEND" >&2
    return 64
  fi

  if [[ "$ESSENTIA_BACKEND" == "uv" ]]; then
    if ! command -v uv >/dev/null 2>&1; then
      printf '%suv is required for ESSENTIA_BACKEND=uv but was not found in PATH.%s\n' "$COLOR_ERROR" "$COLOR_RESET" >&2
      return 127
    fi
  fi

  init_colors

  if [[ "${1:-}" == "--debug" || "${1:-}" == "-x" ]]; then
    shift
    set -x
    printf '%sDebug mode enabled (set -x).%s\n' "$COLOR_WARN" "$COLOR_RESET" >&2
  fi

  if [[ "${1:-}" == "--test-model" || "${1:-}" == "-t" ]]; then
    shift
    local test_model="$OPENCODE_MODEL"
    if [[ "$#" -gt 0 && "${1:-}" != -* ]]; then
      test_model="$1"
      shift
    fi
    vibe_test_model "$test_model"
    return $?
  fi

  main_menu
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
