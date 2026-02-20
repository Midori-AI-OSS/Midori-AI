#!/usr/bin/env python3

import re
import sys
import argparse

from pathlib import Path


BLOCKED_PATTERNS = (
    (re.compile(r"\bhandoff notes?\b", re.IGNORECASE), "mentions internal handoff artifacts"),
    (re.compile(r"\bper the handoff\b", re.IGNORECASE), "mentions internal handoff artifacts"),
    (re.compile(r"\bfrom the handoff\b", re.IGNORECASE), "mentions internal handoff artifacts"),
    (re.compile(r"\bgatherers?\b", re.IGNORECASE), "mentions internal gatherer workflow"),
    (re.compile(r"\bcoordinator\b", re.IGNORECASE), "mentions internal coordinator workflow"),
    (re.compile(r"\brequester notes?\b", re.IGNORECASE), "mentions internal requester workflow"),
    (re.compile(r"\bas an agent\b", re.IGNORECASE), "contains agent-facing narration"),
    (re.compile(r"\bthis agent\b", re.IGNORECASE), "contains agent-facing narration"),
    (re.compile(r"\bno comments from luna today\b", re.IGNORECASE), "contains blocked Luna note"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail when a blog draft includes blocked meta/process phrases.")
    parser.add_argument("post_path", help="Path to the markdown post file to validate.")
    return parser.parse_args()


def line_number_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def line_text_for_line(text: str, line_number: int) -> str:
    lines = text.splitlines()
    if line_number <= 0 or line_number > len(lines):
        return ""
    return lines[line_number - 1].strip()


def main() -> int:
    args = parse_args()
    post_path = Path(args.post_path)
    if not post_path.is_file():
        print(f"ERROR: file not found: {post_path}")
        return 2

    text = post_path.read_text(encoding="utf-8", errors="ignore")
    violations = []

    for pattern, reason in BLOCKED_PATTERNS:
        for match in pattern.finditer(text):
            line_number = line_number_for_offset(text, match.start())
            line_text = line_text_for_line(text, line_number)
            violations.append((line_number, reason, match.group(0), line_text))

    if violations:
        print(f"FAILED: blocked meta/process language found in {post_path}")
        for line_number, reason, phrase, line_text in sorted(violations, key=lambda item: item[0]):
            print(f"{post_path}:{line_number}: {reason}: '{phrase}'")
            if line_text:
                print(f"  line: {line_text}")
        return 1

    print(f"PASS: no blocked meta/process language found in {post_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
