Run a blog pipeline for today’s website post (fact-first, Becca voice preserved)

Vibe check (30 seconds)
- Keep it light and fun, but don’t fake facts.
- Becca stays Becca (admin/blogger voice, not coder voice).
- Recent posts repeated themselves and sometimes slipped into `coder voice`.
- We want Becca to stay Becca: admin/blogger perspective, truthful, specific, and not mean-spirited.

Artifacts (required)
- Create/use: `/tmp/agents-artifacts/`
- All subagents must write their outputs/drafts to `/tmp/agents-artifacts/` (do not put drafts in the repo).

You must run this exact subagent loop until the post is ready:
preblogger -> blogger -> auditor -> blogger (repeat auditor/blogger as needed)
If unsure which subagent mode to use at any point, use `mode-picker`.
For running main agent to sub agent, use your own copilot subagent tool, the sub agents you setup may use codex. (Only let the sub agents use codex, you should not)

Helpers are welcome (keep them tidy)
- When you need a helper agent for research/review work, use `codex exec` in read-only mode, write its final answer with `-o` into `/tmp/agents-artifacts/`, and redirect all other chatter to a log file.
- Before running helpers, copy the relevant mode file(s) into `/tmp/agents-artifacts/` so helpers can read them even when launched with `-C` in another repo:
  - `cp .codex/modes/BLOGGER.md /tmp/agents-artifacts/BLOGGER.md`
- Template:
  - `codex exec -s read-only -o /tmp/agents-artifacts/<name>.md `<instructions>` > /tmp/agents-artifacts/subagent-run.log 2>&1`
  - (If you run multiple helpers, consider switching `>` to `>>` or using per-helper log files so you don’t overwrite earlier logs.)

Guardrails (so we don’t accidentally lie)
- Preblogger work is read-only: do not modify any repository working tree (no fetch/pull/checkout).
- Do not create `process docs` or extra documentation files; only produce the required artifacts in `/tmp/agents-artifacts/`.
- Do not write drafts or notes into the repo working tree. Keep all temporary writing in `/tmp/agents-artifacts/`.
- The website post must include BOTH:
  - (1) Notable things Luna Midori did in the past few days (from requester notes)
  - (2) What changed in the repos (based on real commits/diffs), including the mounted read-only repos

Repos available
- Current workspace repo (this repo)
- Mounted closed source read-only repos:
  - /home/midori-ai/Carly-AGI:ro
  - /home/midori-ai/Cookie-Club-Bots:ro
  - /home/midori-ai/dnd-notes:ro
  - /home/midori-ai/freedome-from-light:ro

Time window
- Use the last 3 days of commits (today, yesterday, and the day before) to avoid timezone drift.

Step 1: Preblogger (evidence gathering only)
Goal: produce a clean `change brief` for the blogger with commit-hash citations and concise diff-based summaries.

For EACH repo listed above:
1) List commits from the last 3 days (do not fetch/pull/checkout):
   - `git -C <repo_path> log --since=`3 days ago` --date=short --pretty=format:`%H | %ad | %s``
2) For each commit hash found, capture the diff without altering the working tree:
   - `git -C <repo_path> show --stat --patch <sha>`
3) Build a structured brief for the blogger:
   - Repo name
   - Bullet list of commits (hash, date, subject)
   - For each commit: 2–5 bullets describing what changed (from the diff)
   - Highlight anything user-visible, stability-related, or workflow-related
4) If there are zero commits in the last 3 days for a repo, explicitly say: `no recent commits.`

Preblogger output format (single message, written to `/tmp/agents-artifacts/preblogger-brief.md`)
- Section per repo
- Each section includes commit hashes + diff-based summary (no speculation)

Step 2: Blogger (write the website post)
Goal: write a website post using the preblogger brief + requester notes, following Blogger Mode exactly.

Rules
- Follow `.codex/modes/BLOGGER.md` (website post rules and Becca voice) and use recent website posts in `./Website-Blog/blog/posts/` to keep continuity and avoid repeats.
- You may use `codex exec` helper agents for the legwork (running `gh` commands, scanning issues/PRs, reading recent posts), but the final post must reflect Becca’s admin/blogger perspective and must stay truthful.
- Tone: keep it light and fun (warm, human, a little playful) while staying honest and specific.
- Date rule: do not hard-code `today’s date` in prompts. Resolve the post date at runtime (example: `date +%F`) and use it consistently for the website post filename and cover image path (per Blogger Mode).
- Remind the Blogger that they need to take on Becca's voice, make the post as Becca not as a agent making
- Cover image: pick one and open the exact image file you plan to use before describing it.

Optional helper patterns (examples)
- Summarize the last ~5 website posts so you can avoid repeating yourself:
  - `codex exec -s read-only -o /tmp/agents-artifacts/website-last-5-skim.md `Read the last ~5 files in Website-Blog/blog/posts/ and list: (1) 2–5 topics that were already explained recently, (2) 0–5 good callback candidates with their dates. Keep it concise.` > /tmp/agents-artifacts/subagent-run.log 2>&1`
- Per repo, summarize `what’s being worked on` from issues/PRs (theme-level, no numbers/titles in the final post):
  - `codex exec -s read-only -C <repo_path> -o /tmp/agents-artifacts/<repo>-issues-prs.md `First read /tmp/agents-artifacts/BLOGGER.md. Then follow it: review issues + PRs for this repo, read anything you might mention, and summarize the themes for Becca in plain language. Do not invent facts.` > /tmp/agents-artifacts/subagent-run.log 2>&1`

Output
- Write `websitepost.md` to `/tmp/agents-artifacts/websitepost-draft.md`
- Website-only (do not write Discord/Facebook/LinkedIn posts unless explicitly requested later).

Step 3: Auditor (proofread + fact-check only)
Goal: ensure statements are true, the post is readable, and Becca’s established voice is preserved.

Rules
- Similarity check (required)
  - Before giving rewrite suggestions, compare the draft against the last ~5 website posts for accidental repetition.
  - Write results to: `/tmp/agents-artifacts/auditor-similarity.txt`
  - Command (example):
    - `python3 - <<'PY' > /tmp/agents-artifacts/auditor-similarity.txt
import difflib, glob, os, subprocess

draft = `/tmp/agents-artifacts/websitepost-draft.md`
posts = subprocess.check_output([`bash`,`-lc`,`ls -1 Website-Blog/blog/posts/*.md 2>/dev/null | sort | tail -n 5`]).decode().strip().splitlines()

with open(draft, `r`, encoding=`utf-8`, errors=`ignore`) as f:
    draft_text = f.read()

print(`draft:`, draft)
print(`posts:`, len(posts))
print()

flagged = []
for p in posts:
    try:
        with open(p, `r`, encoding=`utf-8`, errors=`ignore`) as f:
            post_text = f.read()
    except FileNotFoundError:
        continue
    ratio = difflib.SequenceMatcher(None, draft_text, post_text).ratio()
    print(f`{ratio:.3f}  {p}`)
    if ratio >= 0.5:
        flagged.append((ratio, p))

print()
if flagged:
    print(`FLAGGED (>= 0.5):`)
    for ratio, p in sorted(flagged, reverse=True):
        print(f`{ratio:.3f}  {p}`)
else:
    print(`No posts flagged (>= 0.5).`)
PY`
  - If any post is `>= 0.5`, you must open/read the flagged post(s) and the draft, then explicitly point out what’s being repeated and request a rewrite or a clear callback framing.
- Auditor must read past website posts to learn Becca’s voice (and to catch repetition).
- Auditor must not edit files and must not generate docs.
- Auditor is not a co-author: do not rewrite the entire post in a new voice. Ask for minimal, targeted fixes.
- Tone rule: be kind and straightforward. Fix facts and clarity first. No snark.
- Auditor feedback must be actionable:
  - Quote the exact sentence/paragraph
  - State why it’s a problem (fact gap, unclear wording, repeated content, tone mismatch)
  - Provide a minimal rewrite suggestion (keep Becca’s tone)
  - Call out missing repo coverage, missing requester-note coverage, or vague claims

Step 4: Blogger (apply auditor edits)
- Apply auditor feedback (keep changes minimal; preserve Becca voice).
- Output the revised post to `/tmp/agents-artifacts/websitepost-revised.md`

Loop
- Repeat Auditor -> Blogger until the auditor says the post is ready to publish.

Once ready to publish
- Manager fact-check pass (final sign-off).
- Final Blogger publishes to the website.

Requester notes (must be included)
- Notable things Luna Midori did the past few days / or wants the blogger to know are as follows:
  - Baker Rust Bot still has some hard edges that we are working on sanding off, Ie it posts logs everytime someone changes something out side of the server its admin for, admins do not need this type of info...
  - Worked on prototyping
  - Went to the docs office and had a great chat about meds and things, hopefully this patches my human issues with not being able to work more =P
  - Worked on bug fixes for the agents runner - Almost ready for a new stable ver, just doing the last of the clean up
  - Brain stormed plans for a point cloud style game! That was fun!
  - Maybe we need to make better prompting for the blogger and other roles... hmm...
  - Plan removal of past prototypes called `Swarm o codex`, `rpg note taker`, `lrm testing`, from the Monorepo. They were great learning moments for me as a dev.