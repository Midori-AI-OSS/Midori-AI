from __future__ import annotations

import os
from typing import List
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


def run_env_selector(page_size: int = 5) -> str:
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
                path = environments.get_or_create_local_work()
                print(f"Using local work folder: {path}")
                try:
                    os.chdir(path)
                except Exception as e:
                    print(f"Failed to chdir to '{path}': {e}")
                return path
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
            return env.path

        print("Unknown command. Type 'add', 'remove', 'update', 'up', 'down'.")

    # if the loop exits without an explicit selection, return a sentinel
    return "no repo"
