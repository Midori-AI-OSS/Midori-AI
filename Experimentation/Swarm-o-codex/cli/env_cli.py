from __future__ import annotations

import os
import argparse
from typing import List, Optional, Tuple
from shared import environments


def _render_page(names: List[str], page: int, page_size: int) -> None:
    start = page * page_size
    end = start + page_size
    slice = names[start:end]
    print("\nEnvironments (showing {}-{} of {}):".format(start + 1, min(end, len(names)), len(names)))
    for i, n in enumerate(slice, start=1):
        env = environments.get_environment(n)
        short = env.repo if env else ""
        print(f"{i}) {n} -> {short}")
    print("\nCommands: up, down, add, remove, update.")
    print("Press Enter to open your local work folder, or 1-5 to select a listed environment")


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return "q"

def parse_env_task_args(argv: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Lightweight parser for --env and --task flags.

    This is intentionally minimal to allow embedding in other CLIs.
    Returns a tuple (env_name, task_text). Unrecognized args are ignored.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env", dest="env", nargs="?", const="local", default=None)
    parser.add_argument("--task", dest="task", default=None)
    try:
        ns, _ = parser.parse_known_args(argv)
        return ns.env, ns.task
    except Exception:
        # On any parsing issue, gracefully fall back to interactive mode
        return None, None


def get_local_work_init_prompt() -> str:
    """Return the initialization prompt for setting up a new local work folder."""
    return """Finalize the local work folder setup based on the pre-cloned Codex template.

Important:
- In most cases, the Codex template was already pre-cloned into this folder from https://github.com/Midori-AI-OSS/codex_template_repo.
- If files are already present, skip cloning and proceed with cleanup and customization.
- If this folder is empty (pre-clone failed), perform the clone steps first as described below.

Please complete the following steps:
1. If the folder is empty: clone https://github.com/Midori-AI-OSS/codex_template_repo into a temporary location, then copy contents into the current working directory.
2. Ensure any .git directory is removed from this folder so it is detached from the template's history.
3. Remove template-only metadata (e.g., .github workflows or template-specific badges/sections) as appropriate.
4. Update README.md to state this is your local work folder based on the Codex template, including brief usage notes if helpful.
5. Verify the structure is clean and ready (build scripts, configs, and starter files are present and runnable).

Goal: this folder should be a clean, ready-to-use workspace derived from the Codex template, independent of the template repository itself."""


def run_env_selector(page_size: int = 5, env_name: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Select a working environment.

    - If env_name is provided, attempt a non-interactive resolution and return the path.
    - Otherwise, fall back to the interactive selector.
    
    Returns:
        Tuple of (path, init_prompt):
        - path: The selected environment path
        - init_prompt: Initialization prompt if the folder needs setup, None otherwise
    """
    # Non-interactive fast path
    if env_name:
        # Special-case keywords for local work folder
        if env_name.lower() in ("local", "work", "local-work", "local_work"):
            try:
                path, needs_init = environments.get_or_create_local_work()
                init_prompt = get_local_work_init_prompt() if needs_init else None
                print(f"Using local work folder: {path}")
                if needs_init:
                    print("[INFO] Local work folder is empty and will be initialized with template...")
                try:
                    os.chdir(path)
                except Exception as e:
                    print(f"Failed to chdir to '{path}': {e}")
                return path, init_prompt
            except Exception as e:
                print(f"Failed to initialize local work folder: {e}")
                # If local fails, fall through to interactive selection

        env = environments.get_environment(env_name)
        if env:
            print(f"Using '{env_name}': {env.repo} -> {env.path}")
            try:
                os.chdir(env.path)
            except Exception as e:
                print(f"Failed to chdir to '{env.path}': {e}")
            return env.path, None
        else:
            print(f"Environment '{env_name}' not found. Entering interactive selector...")

    names = sorted(environments.list_environments().keys())
    if not names:
        # don't return early — allow the user to run 'add' interactively
        print("No environments found. Press Enter to open your local work folder, type 'add' to create one.")
    page = 0
    while True:
        names = sorted(environments.list_environments().keys())
        total_pages = max(1, (len(names) + page_size - 1) // page_size)
        if page >= total_pages:
            page = total_pages - 1

        _render_page(names, page, page_size)
        cmd = _prompt("> ").strip()
        if not cmd:
            # Use or create the persistent local work folder
            try:
                path, needs_init = environments.get_or_create_local_work()
                init_prompt = get_local_work_init_prompt() if needs_init else None
                print(f"Using local work folder: {path}")
                if needs_init:
                    print("[INFO] Local work folder is empty and will be initialized with template...")
                try:
                    os.chdir(path)
                except Exception as e:
                    print(f"Failed to chdir to '{path}': {e}")
                return path, init_prompt
            except Exception as e:
                print(f"Failed to initialize local work folder: {e}")
                continue
        if cmd in ("up", "u"):
            if page > 0:
                page -= 1
            else:
                print("Already at first page")
            continue
        if cmd in ("down", "d"):
            if page < total_pages - 1:
                page += 1
            else:
                print("Already at last page")
            continue
        if cmd == "add":
            name = _prompt("Environment name: ").strip()
            repo = _prompt("Git repo URL or path: ").strip()
            if not name or not repo:
                print("name and repo are required")
                continue
            try:
                environments.add_environment(name, repo, overwrite=False)
                print(f"Added environment '{name}'")
            except Exception as e:
                print("Failed to add:", e)
            continue
        if cmd == "remove":
            key = _prompt("Environment name or number: ").strip()
            # allow numeric selection
            if key.isdigit():
                idx = int(key) - 1 + page * page_size
                try:
                    name = sorted(environments.list_environments().keys())[idx]
                except Exception:
                    print("invalid selection")
                    continue
            else:
                name = key
            ok = environments.remove_environment(name, delete_files=True)
            print("removed" if ok else "no such environment")
            continue
        if cmd == "update":
            key = _prompt("Environment name or number: ").strip()
            if key.isdigit():
                idx = int(key) - 1 + page * page_size
                try:
                    name = sorted(environments.list_environments().keys())[idx]
                except Exception:
                    print("invalid selection")
                    continue
            else:
                name = key
            ok = environments.update_environment(name)
            print("updated" if ok else "update failed or env not found")
            continue
        # numeric selection 1-5
        if cmd.isdigit() and 1 <= int(cmd) <= page_size:
            idx = int(cmd) - 1 + page * page_size
            try:
                name = sorted(environments.list_environments().keys())[idx]
            except Exception:
                print("invalid selection")
                continue
            env = environments.get_environment(name)
            if not env:
                print("Environment not found")
                continue
            # Immediately use the selected environment (no extra confirmation)
            print(f"Using '{name}': {env.repo} -> {env.path}")
            try:
                os.chdir(env.path)
            except Exception as e:
                print(f"Failed to chdir to '{env.path}': {e}")
            return env.path, None

        print("Unknown command. Type 'add', 'remove', 'update', 'up', 'down'.")

    # if the loop exits without an explicit selection, return a sentinel
    return "no repo", None
