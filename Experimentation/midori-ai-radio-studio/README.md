# Midori AI Radio Studio

An experimental KDE-native desktop application for managing the music and prompt workflow behind **Midori AI Radio**.

The interface is written in QML with KDE Kirigami and the application logic is written in Rust through CXX-Qt. It follows the Plasma color scheme and uses KDE facilities such as KIO Trash when available.

## Current prototype features

- Browse the complete MP3 library by channel.
- Search title, filename, comment, theme, Q&A fields, and cached vibe summaries.
- Filter comments that contain old boilerplate markers.
- Edit title, artist, album, genre, public comment, and Midori AI Radio custom metadata fields.
- Preserve the existing MP3 streams and metadata while replacing edited tags with `ffmpeg`.
- Play tracks using `mpv`, VLC, `ffplay`, or the desktop opener.
- Move tracks to KDE Trash instead of permanently deleting them.
- Import multiple MP3 files into a channel without overwriting existing songs.
- See the newest MP3 files in Downloads and whether the same filename is already present.
- Block or unblock channels with the existing `.blocked` marker convention.
- Generate metadata drafts through the configured OpenCode model and fallback model.
- Record ratings and written feedback against each reusable prompt.
- Click **Update Prompts** to synthesize a revised prompt from recent feedback.
- Fall back to conservative local prompt guidance when OpenCode is unavailable.
- Version every prompt update and keep prompt history outside the repository.

## Build on Arch Linux / KDE Plasma

Install the development and runtime dependencies:

```bash
sudo pacman -S --needed base-devel rust cargo qt6-base qt6-declarative qt6-wayland kirigami qqc2-desktop-style ffmpeg mpv
```

Then run the dependency check and build:

```bash
bash build.sh doctor
bash build.sh build
```

Run directly:

```bash
bash build.sh run
```

Install it for the current user, including its desktop launcher:

```bash
bash build.sh install
```

Remove generated build output:

```bash
bash build.sh clean
```

## No build output in the monorepo

`build.sh` deliberately writes Cargo output to:

```text
${XDG_CACHE_HOME:-~/.cache}/midori-ai-radio-studio/target
```

The project also has a defensive `.gitignore` covering Cargo, CMake, media files, logs, temporary MP3 replacements, and runtime prompt state.

## Prompt feedback and self-updating prompts

Runtime files are intentionally stored outside the repository:

```text
~/.config/midori-ai-radio-studio/settings.json
~/.config/midori-ai-radio-studio/prompts.json
~/.local/share/midori-ai-radio-studio/feedback.jsonl
~/.local/share/midori-ai-radio-studio/prompt-history/
```

The normal loop is:

1. Select a song and generate a draft.
2. Rate the draft and write specific feedback.
3. Record the feedback.
4. Click **Update Prompts**.
5. The studio asks the configured OpenCode model to produce a complete replacement prompt using the recent feedback examples.
6. If OpenCode fails or is absent, the studio appends deduplicated operator guidance locally instead.
7. The prior prompt set is backed up before the new version is saved.

The application never edits its source code or the monorepo when prompts evolve.

## External tools

Required for normal metadata work:

- `ffprobe`
- `ffmpeg`

Optional but recommended:

- `opencode` for generated drafts and model-written prompt revisions
- `mpv` for playback
- `kioclient6` or `kioclient` for KDE Trash and folder opening

## Prototype limitations

- Long library scans and model calls currently run synchronously and can briefly pause the interface.
- Vibe analysis is displayed from existing MP3 cache tags; the first prototype does not yet rebuild the entire Essentia cache itself.
- Album-art editing is not implemented yet.
- Metadata writing has been designed defensively but should still be tested on copies of representative radio files before a large editing session.
