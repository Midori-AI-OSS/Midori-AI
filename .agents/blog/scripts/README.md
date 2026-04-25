# Blogger Scripts

This folder contains utility scripts for Blogger Mode contributors.

- `post_blog.sh`: Simulates posting a blog post by echoing a message. It does **not** delete the specified `.md` file (drafts are kept for human posting).
- `build_real_moments_appearance_reference.py`: Resolves the Real Moments repo path and bundles canonical character `appearance/looks.md` files for image checks. Defaults to the core five cast when no names are passed.
- `verify_blog_meta.py`: Fails when draft/final blog text contains blocked workflow/meta phrases.
- `verify_blog_cover.py`: Validates blog frontmatter cover image rules against the post date and available files.
- `verify_blog_publish.py`: Runs final publish checks and writes a status report to `/tmp/agents-artifacts/publish-check.txt`.

## Usage

```bash
./post_blog.sh <postfile.md>
uv run .agents/blog/scripts/build_real_moments_appearance_reference.py --core-cast --output /tmp/agents-artifacts/real-moments-appearance-reference.md
```

## Validation Usage

```bash
uv run .agents/blog/scripts/verify_blog_meta.py <postfile.md>
uv run .agents/blog/scripts/verify_blog_cover.py <postfile.md>
uv run .agents/blog/scripts/verify_blog_publish.py --post-date YYYY-MM-DD
```
