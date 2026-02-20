#!/usr/bin/env python3

import re
import sys
import argparse
import subprocess

from pathlib import Path


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Verify final website post publish readiness and write a report.")
    parser.add_argument("--post-date", required=True, help="Post date in YYYY-MM-DD format.")
    parser.add_argument(
        "--report-path",
        default="/tmp/agents-artifacts/publish-check.txt",
        help="Path to write publish-check output.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root),
        help="Workspace root containing Website-Blog and .codex folders.",
    )
    return parser.parse_args()


def parse_frontmatter(markdown_text: str) -> dict:
    if not markdown_text.startswith("---\n"):
        return {}

    lines = markdown_text.splitlines()
    frontmatter = {}
    closing_found = False

    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            closing_found = True
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")

    if not closing_found:
        return {}
    return frontmatter


def run_check(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        return False, f"Failed to execute command: {' '.join(command)} ({exc})"

    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    combined = "\n".join(part for part in (output, error) if part)
    if completed.returncode == 0:
        return True, combined
    return False, combined or f"Command exited with code {completed.returncode}"


def main() -> int:
    args = parse_args()
    report_lines = []
    failures = 0

    if not DATE_PATTERN.match(args.post_date):
        print("ERROR: --post-date must be YYYY-MM-DD")
        return 2

    repo_root = Path(args.repo_root).resolve()
    post_path = repo_root / "Website-Blog" / "blog" / "posts" / f"{args.post_date}.md"
    similarity_path = Path("/tmp/agents-artifacts/auditor-similarity.txt")
    humanity_path = Path("/tmp/agents-artifacts/auditor-humanity.txt")
    report_path = Path(args.report_path)

    report_lines.append(f"post_date: {args.post_date}")
    report_lines.append(f"post_path: {post_path}")

    if post_path.is_file():
        report_lines.append("post_file_exists: PASS")
        frontmatter = parse_frontmatter(post_path.read_text(encoding="utf-8", errors="ignore"))
        if frontmatter:
            report_lines.append("frontmatter_parse: PASS")
            if frontmatter.get("author") == "Becca Kay":
                report_lines.append("frontmatter_author: PASS")
            else:
                report_lines.append("frontmatter_author: FAIL (author must be 'Becca Kay')")
                failures += 1

            cover_image = frontmatter.get("cover_image")
            if cover_image:
                report_lines.append("frontmatter_cover_image_present: PASS")
            else:
                report_lines.append("frontmatter_cover_image_present: FAIL")
                failures += 1
        else:
            report_lines.append("frontmatter_parse: FAIL")
            failures += 1
    else:
        report_lines.append("post_file_exists: FAIL")
        failures += 1
        frontmatter = {}

    meta_cmd = [
        "uv",
        "run",
        str(repo_root / ".codex" / "blog" / "scripts" / "verify_blog_meta.py"),
        str(post_path),
    ]
    cover_cmd = [
        "uv",
        "run",
        str(repo_root / ".codex" / "blog" / "scripts" / "verify_blog_cover.py"),
        str(post_path),
        "--post-date",
        args.post_date,
    ]

    meta_ok, meta_output = run_check(meta_cmd)
    cover_ok, cover_output = run_check(cover_cmd)

    report_lines.append(f"verify_blog_meta: {'PASS' if meta_ok else 'FAIL'}")
    if meta_output:
        report_lines.append(meta_output)
    if not meta_ok:
        failures += 1

    report_lines.append(f"verify_blog_cover: {'PASS' if cover_ok else 'FAIL'}")
    if cover_output:
        report_lines.append(cover_output)
    if not cover_ok:
        failures += 1

    if similarity_path.is_file():
        report_lines.append("auditor_similarity_artifact: PASS")
    else:
        report_lines.append(f"auditor_similarity_artifact: FAIL ({similarity_path} missing)")
        failures += 1

    if humanity_path.is_file():
        report_lines.append("auditor_humanity_artifact: PASS")
    else:
        report_lines.append(f"auditor_humanity_artifact: FAIL ({humanity_path} missing)")
        failures += 1

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    if failures:
        print(f"FAILED: publish check failed with {failures} issue(s). Report: {report_path}")
        return 1

    print(f"PASS: publish check succeeded. Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
