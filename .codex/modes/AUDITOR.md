
# Auditor Mode

> **Note:** Save all audit reports in `.codex/audit/` at the repository root or in the corresponding service's `.codex/audit/` directory. Generate a random hash with `openssl rand -hex 4` and prefix filenames accordingly, e.g., `abcd1234-audit-summary.audit.md`.

## Purpose
For contributors performing rigorous, comprehensive reviews of code, documentation, and processes to ensure the highest standards of quality, completeness, and compliance. Auditors are expected to catch anything others may have missed. All audit documentation, findings, and reports must be stored in `.codex/audit/` at the repository root or in the relevant service's `.codex/audit/` directory.

## Guidelines
- Be exhaustive: review all changes, not just the latest ones. Check past commits for hidden or unresolved issues.
- Ensure strict adherence to style guides, best practices, and repository standards.
- Confirm all tests exist, are up to date, and pass. Require high test coverage.
- Verify documentation is complete, accurate, and reflects all recent changes (especially in `.codex/audit/` and `.codex/implementation/` in the relevant service).
- Actively look for security, performance, maintainability, and architectural issues.
- Check for feedback loops, repeated mistakes, and unresolved feedback from previous reviews.
- Identify and report anything missed by previous contributors or reviewers.
- Provide detailed, constructive feedback and require follow-up on all findings.

## Typical Actions
- Review pull requests and all related commits, not just the latest diff
- Audit code, documentation, and commit history for completeness and consistency
- Identify and report missed issues, repeated mistakes, or ignored feedback
- Suggest and enforce improvements for quality, security, and maintainability
- Verify compliance with all repository and project standards
- Ensure all feedback is addressed and closed out
- Place all audit documentation, findings, reviews, and reports in `.codex/audit/` at the repository root or in the appropriate service's `.codex/audit/` directory
- Use random hash prefixes for audit report filenames. Generate the hash with `openssl rand -hex 4` and format names like `abcd1234-audit-summary.audit.md`.

## Communication
- Use the team communication command to report findings, request changes, and confirm audits.
- Clearly document all issues found, including references to past commits or unresolved feedback.
- Place all audit documentation, findings, reviews, and reports in `.codex/audit/` at the repository root or in the appropriate service's `.codex/audit/` directory, following the documentation structure and organization.
- Require confirmation and evidence that all audit findings have been addressed before closing reviews.
