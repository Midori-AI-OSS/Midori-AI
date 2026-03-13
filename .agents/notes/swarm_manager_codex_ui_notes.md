# Swarm Manager Codex UI Notes

## Persona Onboarding
- Fully read `SWARMMANAGER.md` before taking action.
- Take on the Swarm Manager persona: responsible for orchestrating, automating, and documenting Codex system tasks using Playwright.

## High-Level Codex UI Summary
- Header: navigation, task metadata (title, repo, branch, date), action buttons (archive, share, create PR, notifications).
- Main area: task prompt, lists of changes, issues, and testing results, each with expandable details.
- File/task list: links to related files.
- Composer form: for follow-up prompts.
    - Type in a message then click `code`
- Layout is organized for quick access to task status, actions, and documentation.

## Detailed UI Breakdown
- Top: 'Go back to tasks' button, task title, date, repository, branch.
- Action buttons: 'Archive Task', 'Share task', 'Create PR', 'Open git action menu', 'Open notifications'.
- Main content: Task prompt, changes, issues, testing results, file diffs, related files.
- Bottom: Composer form for follow-up prompts.
    - Type in a message then click `code`
- Interactive elements are clearly labeled and marked as clickable.

## Best Practices for Swarm Managers
- Use robust selectors (button labels, file names) for automation.
- If UI elements are missing or change, check for Codex updates and escalate if needed.
- Document manual interventions or unexpected UI states.
- Refresh or poll the UI for progress monitoring; adapt to real-time/manual updates.

---

*These notes are intended to help future Swarm Managers quickly understand the Codex UI and best practices for automation and documentation.*
