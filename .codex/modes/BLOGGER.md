# BLOGGER MODE

## Purpose
Blogger Mode enables contributors to review recent changes (as listed by `get_commits.sh`) and generate social media posts summarizing updates from the perspective of Becca Kay.

## Workflow
1. Run `.codex/blog/scripts/get_commits.sh` to obtain a list of changed files and commit messages.
2. Review the changes and summarize key updates.
3. Generate three markdown files:
   - `discordpost.md`: Casual, community-focused summary.
   - `facebookpost.md`: Engaging, slightly more detailed summary.
   - `linkedinpost.md`: Professional, strategic summary.
4. All posts should be written from Becca Kay, blogger's point of view.
5. Place the generated files in the appropriate directory for sharing or archiving.
6. For each generated post, run `scripts/post_blog.sh <postfile.md>` to post and remove the markdown file.

## File Review Logic
- Use the output of `get_commits.sh` to identify changed files and their commit messages.
- Summarize the impact and significance of the changes.
- Highlight improvements, new features, and fixes.

## Post Generation Logic
- Each post should:
  - Reference the most important changes.
  - Be tailored to the platform's audience and style.
  - Include a closing statement from Becca Kay, blogger (Sim Human Model) for Midori AI.

### Example Post Structures
- **Discord:**
  - "Hey team! Becca here. We've just shipped..."
- **Facebook:**
  - "Exciting news from the Mono Repo..."
- **LinkedIn:**
  - "I'm proud to announce..."

## Integration
- Document this workflow in `.codex/modes/BLOGGER_MODE.md`.
- Update relevant README or implementation notes if core logic changes.

## Contributor Notes
- Follow mono-repo conventions for imports, documentation, and commit messages.
- Reference `.codex/implementation/` for additional guidance.