#!/usr/bin/env python3

import re
import sys
import argparse

from pathlib import Path


PLACEHOLDER_COVER = "/blog/placeholder.png"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_FILE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    default_posts_dir = repo_root / "Website-Blog" / "blog" / "posts"
    default_public_dir = repo_root / "Website-Blog" / "public" / "blog"

    parser = argparse.ArgumentParser(description="Validate blog cover_image frontmatter against date and files.")
    parser.add_argument("post_path", help="Path to markdown post file.")
    parser.add_argument(
        "--post-date",
        help="Post date in YYYY-MM-DD format. Required for non-date filenames like websitepost-draft.md.",
    )
    parser.add_argument("--posts-dir", default=str(default_posts_dir), help="Directory containing all website posts.")
    parser.add_argument(
        "--public-dir",
        default=str(default_public_dir),
        help="Directory containing public blog images (must include unassigned/).",
    )
    return parser.parse_args()


def parse_frontmatter(markdown_text: str) -> dict:
    if not markdown_text.startswith("---\n"):
        return {}

    lines = markdown_text.splitlines()
    frontmatter = {}
    closing_index = None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
        if ":" not in lines[index]:
            continue
        key, value = lines[index].split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")

    if closing_index is None:
        return {}
    return frontmatter


def resolve_post_date(post_path: Path, override_date: str | None) -> str | None:
    if override_date:
        if DATE_PATTERN.match(override_date):
            return override_date
        return None

    match = DATE_FILE_PATTERN.match(post_path.name)
    if match:
        return match.group(1)
    return None


def extract_cover_image(path: Path) -> str | None:
    if not path.is_file():
        return None
    frontmatter = parse_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
    cover_image = frontmatter.get("cover_image")
    if not cover_image:
        return None
    return cover_image.strip()


def main() -> int:
    args = parse_args()
    post_path = Path(args.post_path).resolve()
    posts_dir = Path(args.posts_dir).resolve()
    public_dir = Path(args.public_dir).resolve()
    errors = []

    if not post_path.is_file():
        print(f"ERROR: file not found: {post_path}")
        return 2

    post_date = resolve_post_date(post_path, args.post_date)
    if post_date is None:
        errors.append(
            "Unable to resolve post date. Use a YYYY-MM-DD filename or pass --post-date YYYY-MM-DD."
        )

    frontmatter = parse_frontmatter(post_path.read_text(encoding="utf-8", errors="ignore"))
    if not frontmatter:
        errors.append("Frontmatter is missing or malformed.")

    cover_image = frontmatter.get("cover_image", "").strip().strip("'\"")
    if not cover_image:
        errors.append("Frontmatter is missing cover_image.")

    if errors:
        print(f"FAILED: cover validation failed for {post_path}")
        for error in errors:
            print(f"- {error}")
        return 1

    if cover_image == PLACEHOLDER_COVER:
        print(f"PASS: {post_path} uses placeholder cover image.")
        return 0

    expected_prefix = f"/blog/{post_date}."
    if not cover_image.startswith(expected_prefix):
        print(f"FAILED: cover validation failed for {post_path}")
        print(f"- cover_image must be /blog/{post_date}.<ext> or {PLACEHOLDER_COVER}")
        print(f"- found: {cover_image}")
        return 1

    expected_file_name = cover_image.rsplit("/", 1)[-1]
    expected_cover_path = public_dir / expected_file_name
    if not expected_cover_path.is_file():
        print(f"FAILED: cover validation failed for {post_path}")
        print(f"- expected cover file is missing: {expected_cover_path}")
        return 1

    unassigned_copy = public_dir / "unassigned" / expected_file_name
    if unassigned_copy.exists():
        print(f"FAILED: cover validation failed for {post_path}")
        print(f"- cover file still exists in unassigned/: {unassigned_copy}")
        return 1

    duplicate_users = []
    if posts_dir.is_dir():
        for other_path in sorted(posts_dir.glob("*.md")):
            if other_path.resolve() == post_path:
                continue
            other_cover = extract_cover_image(other_path)
            if other_cover == cover_image:
                duplicate_users.append(other_path)

    if duplicate_users:
        print(f"FAILED: cover validation failed for {post_path}")
        print(f"- cover_image is reused by other post(s): {cover_image}")
        for duplicate_path in duplicate_users:
            print(f"  - {duplicate_path}")
        return 1

    print(f"PASS: cover image is valid for {post_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
