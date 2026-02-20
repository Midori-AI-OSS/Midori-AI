Run a blog pipeline for today’s website post (fact-first, Becca voice preserved)

Vibe check (30 seconds)
- Keep it light and fun, but don’t fake facts.
- Becca stays Becca (admin/blogger voice, not coder voice).
- Recent posts repeated themselves and sometimes slipped into `coder voice`.
- We want Becca to stay Becca: admin/blogger perspective, truthful, specific, and not mean-spirited.

Roles (make “you” unambiguous)
- Coordinator (main agent): orchestrates the loop, launches subagents, verifies artifacts exist, and enforces guardrails.
- Subagents: do the actual work in their assigned mode and write the required artifacts.
- Helpers (optional): launched read-only via `codex exec` to summarize/review; outputs go to `/tmp/agents-artifacts/`.

Artifacts (required)
- Create/use: `/tmp/agents-artifacts/`
- All subagents must write their outputs/drafts to `/tmp/agents-artifacts/`.
- Optional staging: only stage into `.codex/blog/staging/` if the Coordinator explicitly requests it (default: `/tmp/agents-artifacts/` only).
- Never delete staged files during the pipeline. If cleanup is needed, use `CLEANUP` mode.

The loop (required)
- Coordinator must run this exact subagent loop until the post is ready:
  change-diff-gatherer -> change-pr-gatherer -> change-issue-gatherer -> change-context-gatherer -> blog-prompter -> blogger -> auditor -> blogger (repeat auditor/blogger as needed)
- If unsure which subagent mode to use at any point, use `mode-picker`.
- For main agent -> subagent: use your own copilot subagent tool. Subagents may use codex. (Only subagents use codex; Coordinator should not.)

Helpers are welcome (keep them tidy)
- When you need a helper for research/review work, use `codex exec` in read-only mode, write its final answer with `-o` into `/tmp/agents-artifacts/`, and redirect all other chatter to a log file.
- Before running helpers, copy the relevant mode file(s) into `/tmp/agents-artifacts/` so helpers can read them even when launched with `-C` in another repo:
  - `cp .codex/modes/blog/BLOGGER.md /tmp/agents-artifacts/BLOGGER.md`
- Template:
  - `codex exec -s read-only -o /tmp/agents-artifacts/<name>.md "<instructions>" > /tmp/agents-artifacts/subagent-run.log 2>&1`
  - (If you run multiple helpers, consider switching `>` to `>>` or using per-helper log files so you don’t overwrite earlier logs.)

Guardrails (so we don’t accidentally lie)
- Change gatherer work is read-only: do not modify any repository working tree (no fetch/pull/checkout).
- Do not create `process docs` or extra documentation files; only produce the required artifacts in `/tmp/agents-artifacts/`.
- Prefer `/tmp/agents-artifacts/` outputs. Only write to `.codex/blog/staging/` if the Coordinator explicitly requests it.
- Do not write drafts or notes elsewhere in the repo working tree. Keep all other temporary writing in `/tmp/agents-artifacts/`.
- Approved exception: `.codex/workflow-prompts/luna-activity.txt` is a persistent requester-context input file. Read it only as loose context and never publish/internalize it as process narration.
- Never include internal workflow narration in final website prose (`handoff notes`, `gatherer`, `coordinator`, `requester notes`, `as an agent`, or similar).
- Convert requester input into two explicit lists before blogging:
  - `must_include`
  - `must_not_mention`
- Treat `must_not_mention` violations as publish blockers.
- The website post must include BOTH:
  - (1) Notable things Luna Midori did in the past few days (from requester notes)
  - (2) What changed in the repos (based on real commits/diffs), including workspace submodules and mounted read-only repos

Repos available
- Current workspace repo (this repo)
- Workspace sub-repos (git submodules from `.gitmodules`)
  - Repo list helper (run at workspace root): `git config --file .gitmodules --get-regexp path | awk '{print $2}'`
- Mounted closed source read-only repos:
  - /home/midori-ai/Carly-AGI:ro
  - /home/midori-ai/Cookie-Club-Bots:ro
  - /home/midori-ai/dnd-notes:ro
  - /home/midori-ai/freedome-from-light:ro

Repo scope for gatherers (required)
- Build a repo path list that includes: workspace root + every submodule path + the mounted read-only repos.

Time window
- Use the last 3 days of commits (today, yesterday, and the day before) to avoid timezone drift.

Step 1: Change-Diff-Gatherer (evidence gathering only)
Goal: produce a clean `change brief` for the blogger with concise diff-based summaries (no raw diffs; no commit IDs in the brief).

Coordinator responsibilities
- Launch the `change-diff-gatherer` subagent with the repos list + time window + output requirements (default: write to `/tmp/agents-artifacts/` only).
- Verify the brief exists at the required path when the subagent is done.

Subagent responsibilities (for EACH repo listed above)
1) Record the current branch:
   - `git -C <repo_path> rev-parse --abbrev-ref HEAD`
2) Collect commit hashes to process (do not fetch/pull/checkout):
   - `git -C <repo_path> log --since="3 days ago" -n 50 --pretty=format:"%H"`
3) For each commit hash found, capture metadata + diff without altering the working tree:
   - `git -C <repo_path> show -s --date=short --format="%ad | %s" <sha>`
   - `git -C <repo_path> show --stat --patch <sha>`
4) Build a structured brief for the blogger:
   - Repo name
   - Branch name
   - Bullet list of updates (date, subject; no commit IDs)
   - For each update: 2–5 bullets describing what changed (from the diff; no commit IDs)
   - Highlight anything user-visible, stability-related, or workflow-related
5) If there are zero commits in the last 3 days for a repo, do not bring up that repo in the brief.

Change-Diff-Gatherer output format (single message, written to `/tmp/agents-artifacts/change-diff-gatherer-brief.md`)
- Section per repo
- Each section includes diff-based summary (no speculation; no raw diffs; no commit IDs)

Output
- Optional: stage to `.codex/blog/staging/change-diff-gatherer-brief.md` only if the Coordinator explicitly requests it.

Step 2: Change-PR-Gatherer (evidence gathering only)
Goal: produce a clean PR brief for the blogger (themes only; no PR numbers/titles/URLs).

Coordinator responsibilities
- Launch the `change-pr-gatherer` subagent and verify the brief exists at the required path.

Subagent note
- Run `gh` commands from inside each repo directory (do not use `gh -R <repo_path>`; `-R/--repo` expects `OWNER/REPO`).

Output
- Write to `/tmp/agents-artifacts/change-pr-gatherer-brief.md`
- Optional: stage to `.codex/blog/staging/change-pr-gatherer-brief.md` only if the Coordinator explicitly requests it.

Step 3: Change-Issue-Gatherer (evidence gathering only)
Goal: produce a clean issues brief for the blogger (themes only; no issue numbers/titles/URLs).

Coordinator responsibilities
- Launch the `change-issue-gatherer` subagent and verify the brief exists at the required path.

Subagent note
- Run `gh` commands from inside each repo directory (do not use `gh -R <repo_path>`; `-R/--repo` expects `OWNER/REPO`).

Output
- Write to `/tmp/agents-artifacts/change-issue-gatherer-brief.md`
- Optional: stage to `.codex/blog/staging/change-issue-gatherer-brief.md` only if the Coordinator explicitly requests it.

Step 4: Change-Context-Gatherer (evidence gathering only)
Goal: produce a small context brief for the blogger (workflow/focus signals; no speculation).

Coordinator responsibilities
- Launch the `change-context-gatherer` subagent and verify the brief exists at the required path.

Output
- Write to `/tmp/agents-artifacts/change-context-gatherer-brief.md`
- Optional: stage to `.codex/blog/staging/change-context-gatherer-brief.md` only if the Coordinator explicitly requests it.

Step 5: Blog-Prompter (handoff builder)
Goal: combine all briefs into a single, Blogger-ready handoff file.

Coordinator responsibilities
- Launch the `blog-prompter` subagent.
- Verify the handoff exists at the required path.

Subagent responsibilities
- Combine all briefs into one Blogger-ready handoff.
- Write the handoff file.

Output
- Write to `/tmp/agents-artifacts/blogger-handoff.md`
- Optional: stage to `.codex/blog/staging/blogger-handoff.md` only if the Coordinator explicitly requests it.

Step 6: Blogger (write the website post)
Goal: write a website post using `blogger-handoff.md` + requester notes, following Blogger Mode exactly.

Coordinator responsibilities
- Launch the `blogger` subagent and ensure it uses the handoff file (not `git`/`gh`).
- Ensure the blogger is reminded to write as Becca (not as an agent explaining its process).

Rules (for the blogger subagent)
- Follow `.codex/modes/blog/BLOGGER.md` (website post rules and Becca voice) and use recent website posts in `./Website-Blog/blog/posts/` to keep continuity and avoid repeats.
- Blogger does not run `git` or `gh`. Use the handoff: `/tmp/agents-artifacts/blogger-handoff.md` (or `.codex/blog/staging/blogger-handoff.md`).
- Read requester context from `.codex/workflow-prompts/luna-activity.txt` as loose context:
  - Use non-empty lines above `--- archive ---` as current-cycle context.
  - If the file is missing, continue with handoff evidence + the hard rules below.
- Tone: keep it light and fun (warm, human, a little playful) while staying honest and specific.
- Date rule: do not hard-code `today’s date`. Resolve the post date at runtime (example: `date +%F`) and use it consistently for the website post filename and cover image path (per Blogger Mode).
- Cover image: pick one and open the exact image file you plan to use before describing it.
- Cover image behavior: prefer claiming by moving/renaming from `./Website-Blog/public/blog/unassigned/`; placeholder is allowed when there is no fitting image.
- Resolve and export post date once before validation commands:
  - `POST_DATE="$(date +%F)"`
- Run required checks before handing off to auditor:
  - `uv run .codex/blog/scripts/verify_blog_meta.py /tmp/agents-artifacts/websitepost-draft.md`
  - `uv run .codex/blog/scripts/verify_blog_cover.py /tmp/agents-artifacts/websitepost-draft.md --post-date "$POST_DATE"`

Optional helper patterns (examples)
- Summarize the last ~5 website posts so you can avoid repeating yourself:
  - `codex exec -s read-only -o /tmp/agents-artifacts/website-last-5-skim.md "Read the last ~5 files in Website-Blog/blog/posts/ and list: (1) 2–5 topics that were already explained recently, (2) 0–5 good callback candidates with their dates. Keep it concise." > /tmp/agents-artifacts/subagent-run.log 2>&1`

Output
- Write the draft to `/tmp/agents-artifacts/websitepost-draft.md`
- Website-only (do not write Discord/Facebook/LinkedIn posts unless explicitly requested later).

Step 7: Auditor (proofread + fact-check only)
Goal: ensure statements are true, the post is readable, and Becca’s established voice is preserved.

Coordinator responsibilities
- Launch the `auditor` subagent and confirm it produced the required similarity report.
- Launch the `auditor` subagent and confirm it produced the required humanity report.

Rules (for the auditor subagent)
- Similarity check (required)
  - Before giving rewrite suggestions, compare the draft against the last ~5 website posts for accidental repetition.
  - Write results to: `/tmp/agents-artifacts/auditor-similarity.txt`
  - Command (example):

```bash
python3 - <<'PY' > /tmp/agents-artifacts/auditor-similarity.txt
import difflib
import subprocess

draft_path = "/tmp/agents-artifacts/websitepost-draft.md"
posts = subprocess.check_output(
    ["bash", "-lc", "ls -1 Website-Blog/blog/posts/*.md 2>/dev/null | sort | tail -n 5"]
).decode().strip().splitlines()

with open(draft_path, "r", encoding="utf-8", errors="ignore") as f:
    draft_text = f.read()

print("draft:", draft_path)
print("posts:", len(posts))
print()

flagged = []
for path in posts:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            post_text = f.read()
    except FileNotFoundError:
        continue
    ratio = difflib.SequenceMatcher(None, draft_text, post_text).ratio()
    print(f"{ratio:.3f}  {path}")
    if ratio >= 0.5:
        flagged.append((ratio, path))

print()
if flagged:
    print("FLAGGED (>= 0.5):")
    for ratio, path in sorted(flagged, reverse=True):
        print(f"{ratio:.3f}  {path}")
else:
    print("No posts flagged (>= 0.5).")
PY
```
  - If any post is `>= 0.5`, auditor must open/read the flagged post(s) and the draft, then explicitly point out what’s being repeated and request a rewrite or a clear callback framing.
- Humanity check (required)
  - Write results to: `/tmp/agents-artifacts/auditor-humanity.txt`
  - Confirm the draft reads like a human blog post and not an agent/process report.
  - Explicitly fail if the draft includes workflow/meta narration (`handoff notes`, `gatherer`, `as an agent`, etc.).
- Auditor must read past website posts to learn Becca’s voice (and to catch repetition).
- Auditor must not edit files and must not generate docs.
- Auditor is not a co-author: do not rewrite the entire post in a new voice. Ask for minimal, targeted fixes.
- Tone rule: be kind and straightforward. Fix facts and clarity first. No snark.
- Auditor feedback must be actionable:
  - Quote the exact sentence/paragraph
  - State why it’s a problem (fact gap, unclear wording, repeated content, tone mismatch)
  - Provide a minimal rewrite suggestion (keep Becca’s tone)
  - Call out missing repo coverage, missing requester-note coverage, or vague claims

Step 8: Blogger (apply auditor edits)
- Blogger applies auditor feedback (keep changes minimal; preserve Becca voice).
- Output the revised post to `/tmp/agents-artifacts/websitepost-revised.md`
- Re-run required checks on the revised file:
  - `uv run .codex/blog/scripts/verify_blog_meta.py /tmp/agents-artifacts/websitepost-revised.md`
  - `uv run .codex/blog/scripts/verify_blog_cover.py /tmp/agents-artifacts/websitepost-revised.md --post-date "$POST_DATE"`

Loop
- Repeat Auditor -> Blogger until the auditor says the post is ready to publish.

Once ready to publish
- Manager fact-check pass (final sign-off).
- Final Blogger publishes to the website.
- Coordinator must run a publish completion check and write:
  - `uv run .codex/blog/scripts/verify_blog_publish.py --post-date "$POST_DATE"`
  - Report path: `/tmp/agents-artifacts/publish-check.txt`
- `publish-check` only passes when all are true:
  - Final post file exists at `./Website-Blog/blog/posts/YYYY-MM-DD.md`
  - Frontmatter includes `author: Becca Kay` and a valid `cover_image`
  - `verify_blog_meta.py` passes
  - `verify_blog_cover.py` passes
  - `auditor-similarity.txt` exists
  - `auditor-humanity.txt` exists
- If publish-check fails, the pipeline is incomplete (do not mark done).

Historical sweep rule (required)
- For historical edits, use one fresh subagent per post. A subagent may not edit multiple post files in one run.

Requester notes (must be included)
- Notable things Luna Midori did the past few days / or wants the blogger to know are as follows:
  (NOTE: Do not reflavor these things as things Becca did, these are things Luna has done)
  - `must_include`
    - Source: `.codex/workflow-prompts/luna-activity.txt`
    - Read as loose context only (use lines above `--- archive ---`).
    - Do not quote raw lines verbatim in final prose.
  - `must_not_mention`
    - "No Comments from Luna today. She is just hard at work on projects!"
