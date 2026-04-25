#!/usr/bin/env python3

import argparse
import re
import sys

from pathlib import Path


CHARACTER_ALIASES = {
    "echo": "echo",
    "leo": "leo",
    "leo midori": "leo",
    "luna": "luna",
    "luna midori": "luna",
    "riley": "riley",
    "w.e.a.v.e": "w-e-a-v-e",
    "w.e.a.v.e.": "w-e-a-v-e",
    "w-e-a-v-e": "w-e-a-v-e",
    "weave": "w-e-a-v-e",
    "w e a v e": "w-e-a-v-e",
    "lady light": "lady-light",
    "lady-light": "lady-light",
    "lady darkness": "lady-darkness",
    "lady-darkness": "lady-darkness",
}

CORE_REAL_MOMENTS_CAST = ["echo", "leo", "luna", "riley", "w-e-a-v-e"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Real Moments appearance reference bundle from canonical look bibles."
    )
    parser.add_argument(
        "characters",
        nargs="*",
        help="Character names or slugs to include (for example: luna riley 'lady darkness').",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all available Real Moments character look bibles.",
    )
    parser.add_argument(
        "--core-cast",
        action="store_true",
        help="Include the default core five Real Moments characters: echo, leo, luna, riley, w-e-a-v-e.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available character slugs and exit.",
    )
    parser.add_argument(
        "--real-moments-root",
        help="Override path to campaigns/real-moments.",
    )
    parser.add_argument(
        "--output",
        help="Write the markdown bundle to this file instead of stdout.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def candidate_roots(override_path: str | None) -> list[Path]:
    root = repo_root()
    candidates = []

    if override_path:
        candidates.append(Path(override_path).expanduser())

    candidates.extend(
        [
            Path("/home/midori-ai/dnd-notes/campaigns/real-moments"),
            root.parent / "dnd-notes" / "campaigns" / "real-moments",
            Path("/home/lunamidori/nfs/Midori-AI-Github/dnd-notes/campaigns/real-moments"),
        ]
    )

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(resolved)
    return unique_candidates


def resolve_real_moments_root(override_path: str | None) -> Path:
    for candidate in candidate_roots(override_path):
        if (candidate / "chars").is_dir():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidate_roots(override_path))
    raise FileNotFoundError(
        "Unable to resolve campaigns/real-moments. Checked:\n" + searched
    )


def available_character_looks(real_moments_root: Path) -> dict[str, Path]:
    chars_dir = real_moments_root / "chars"
    looks_by_slug: dict[str, Path] = {}
    for child in sorted(chars_dir.iterdir()):
        looks_path = child / "appearance" / "looks.md"
        if looks_path.is_file():
            looks_by_slug[child.name] = looks_path
    return looks_by_slug


def expand_character_args(values: list[str]) -> list[str]:
    expanded = []
    for value in values:
        for part in value.split(","):
            cleaned = part.strip()
            if cleaned:
                expanded.append(cleaned)
    return expanded


def normalize_character_name(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ")
    lowered = re.sub(r"\s+", " ", lowered)
    if lowered in CHARACTER_ALIASES:
        return CHARACTER_ALIASES[lowered]

    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return CHARACTER_ALIASES.get(slug, slug)


def heading_for(looks_text: str, fallback_slug: str) -> str:
    for line in looks_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback_slug.replace("-", " ").title()


def bundle_text(real_moments_root: Path, selected: list[tuple[str, Path]]) -> str:
    lines = [
        "# Real Moments Appearance Reference",
        "",
        f"- Resolved root: {real_moments_root}",
        "- Source files are canonical `chars/<slug>/appearance/looks.md` look bibles.",
        "- Use this bundle alongside the actual image. Do not identify a character from filename vibes alone.",
        "",
    ]

    for slug, looks_path in selected:
        looks_text = looks_path.read_text(encoding="utf-8", errors="ignore").rstrip()
        display_name = heading_for(looks_text, slug)
        body_lines = looks_text.splitlines()
        if body_lines and body_lines[0].startswith("# "):
            body_lines = body_lines[1:]

        lines.append(f"## {display_name}")
        lines.append("")
        lines.append(f"- Slug: `{slug}`")
        lines.append(f"- Source: `{looks_path}`")
        lines.append("")
        lines.extend(body_lines)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_output(content: str, output_path: str | None) -> None:
    if not output_path:
        sys.stdout.write(content)
        return

    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"WROTE: {path}")


def main() -> int:
    args = parse_args()

    try:
        real_moments_root = resolve_real_moments_root(args.real_moments_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    looks_by_slug = available_character_looks(real_moments_root)
    if not looks_by_slug:
        print(f"ERROR: no look bibles found under {real_moments_root / 'chars'}")
        return 2

    if args.list:
        for slug in looks_by_slug:
            print(slug)
        return 0

    if args.all:
        requested_slugs = list(looks_by_slug)
    else:
        raw_names = expand_character_args(args.characters)
        if args.core_cast or not raw_names:
            requested_slugs = [slug for slug in CORE_REAL_MOMENTS_CAST if slug in looks_by_slug]
            missing_core = [slug for slug in CORE_REAL_MOMENTS_CAST if slug not in looks_by_slug]
            if missing_core:
                print("ERROR: missing core Real Moments look bibles:")
                for slug in missing_core:
                    print(f"- {slug}")
                return 2
        else:
            requested_slugs = []
            for raw_name in raw_names:
                normalized = normalize_character_name(raw_name)
                if normalized not in looks_by_slug:
                    print(f"ERROR: unknown Real Moments character: {raw_name}")
                    print("Available characters:")
                    for slug in looks_by_slug:
                        print(f"- {slug}")
                    return 2
                if normalized not in requested_slugs:
                    requested_slugs.append(normalized)

    selected = [(slug, looks_by_slug[slug]) for slug in requested_slugs]
    content = bundle_text(real_moments_root, selected)
    write_output(content, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())