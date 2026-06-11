from __future__ import annotations

import sys
import argparse

import tomli_w

from codexd.paths import CodexdPaths
from codexd.service import CodexdError
from codexd.service import CodexdService
from codexd.installer import build_wrapper_script
from codexd.registry import _strip_none


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    service = CodexdService(CodexdPaths.discover())
    try:
        if argv and argv[0] == "import":
            name = _parse_single_name("import", argv[1:])
            service.import_current_home(name)
            print(f"Imported ~/.codex into managed account {name}.")
            return 0
        if argv and argv[0] == "add":
            name = _parse_single_name("add", argv[1:])
            service.add_account(name)
            print(f"Added managed account {name}.")
            return 0
        if argv and argv[0] == "remove":
            name = _parse_single_name("remove", argv[1:])
            replacement = service.remove_account(name)
            if replacement is None:
                print(f"Removed {name}; no managed accounts remain.")
            else:
                print(f"Removed {name}; default account is now {replacement}.")
            return 0
        if argv and argv[0] == "manage":
            return _handle_manage(service, argv[1:])
        if argv and argv[0] in {"install-wrapper-preview"}:
            print(build_wrapper_script(CodexdPaths.discover().project_root), end="")
            return 0
        return _handle_launch(service, argv)
    except CodexdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _handle_manage(service: CodexdService, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="codexd manage")
    subparsers = parser.add_subparsers(dest="subcommand")

    default_parser = subparsers.add_parser("default")
    default_parser.add_argument("name")

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("name", nargs="?")
    refresh_parser.add_argument("--all", action="store_true")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("name")

    args = parser.parse_args(argv)
    if args.subcommand is None:
        registry, decision = service.manage_summary()
        print(f"default_account = {registry.default_account or '<unset>'}")
        print(f"auto_pick_now = {decision.name if decision is not None else '<none>'}")
        for name, record in sorted(registry.accounts.items()):
            print(
                " | ".join(
                    [
                        name,
                        f"default={'yes' if registry.default_account == name else 'no'}",
                        f"home={record.home_path}",
                        f"plan={record.last_plan_type or '?'}",
                        f"primary={_percent(record.last_primary_used_percent)}",
                        f"secondary={_percent(record.last_secondary_used_percent)}",
                        f"status_source={record.last_status_source or '?'}",
                        f"last_launch={record.last_successful_launch_at or '?'}",
                        f"error={record.last_status_error or '-'}",
                    ],
                ),
            )
        return 0
    if args.subcommand == "default":
        service.set_default_account(args.name)
        print(f"Default account set to {args.name}.")
        return 0
    if args.subcommand == "refresh":
        target = "--all" if args.all else args.name
        if target is None:
            registry, _ = service.manage_summary()
            target = registry.default_account or "--all"
        results = service.refresh_status(target)
        for name, result in sorted(results.items()):
            if result.snapshot is None:
                print(f"{name}: failed ({result.error})")
            else:
                primary = result.snapshot.primary.used_percent if result.snapshot.primary else "?"
                secondary = (
                    result.snapshot.secondary.used_percent
                    if result.snapshot.secondary
                    else "?"
                )
                print(
                    f"{name}: source={result.source} primary={primary}% secondary={secondary}% plan={result.snapshot.plan_type or '?'}",
                )
        return 0
    if args.subcommand == "inspect":
        record = service.inspect_account(args.name)
        payload = {
            "account": {
                args.name: record.to_registry_dict(),
            },
        }
        print(tomli_w.dumps(_strip_none(payload)), end="")
        return 0
    raise AssertionError("unreachable")


def _handle_launch(service: CodexdService, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="codexd", add_help=True, allow_abbrev=False)
    parser.add_argument("--account")
    args, codex_args = parser.parse_known_args(argv)
    service.launch(codex_args, forced_account=args.account)
    return 0


def _parse_single_name(command: str, argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog=f"codexd {command}")
    parser.add_argument("name")
    args = parser.parse_args(argv)
    return args.name


def _percent(value: int | None) -> str:
    return "?" if value is None else f"{value}%"
