from __future__ import annotations

import argparse
import os
import sys

from textwrap import dedent

import tomli_w

from codexd.models import AccountRecord
from codexd.models import AccountStatusSnapshot
from codexd.models import RateLimitWindow
from codexd.launcher import is_admin_passthrough_command
from codexd.paths import CodexdPaths
from codexd.service import CodexdError
from codexd.service import CodexdService
from codexd.installer import build_wrapper_script
from codexd.registry import _strip_none


HELP_FORMATTER = argparse.RawDescriptionHelpFormatter
MANAGE_SUBCOMMANDS = ("default", "refresh", "inspect")
TOP_LEVEL_COMMANDS = ("import", "add", "remove", "manage", "debug-wrapper")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    service = CodexdService(CodexdPaths.discover())
    try:
        if argv and argv[0] in {"-h", "--help"}:
            _build_root_help_parser().parse_args(argv)
            return 0
        if argv and argv[0] == "import":
            name = _parse_import_args(argv[1:]).name
            service.import_current_home(name)
            print(f"Imported ~/.codex into managed account {name}.")
            return 0
        if argv and argv[0] == "add":
            args = _parse_add_args(argv[1:])
            credential_store_mode = "file" if args.allow_file_auth else "keyring"
            service.add_account(
                args.name,
                access_token=_read_access_token(),
                credential_store_mode=credential_store_mode,
            )
            print(f"Added managed account {args.name}.")
            return 0
        if argv and argv[0] == "remove":
            name = _parse_remove_args(argv[1:]).name
            replacement = service.remove_account(name)
            if replacement is None:
                print(f"Removed {name}; no managed accounts remain.")
            else:
                print(f"Removed {name}; default account is now {replacement}.")
            return 0
        if argv and argv[0] == "manage":
            return _handle_manage(service, argv[1:])
        if argv and argv[0] == "debug-wrapper":
            _parse_debug_wrapper_args(argv[1:])
            print(build_wrapper_script(CodexdPaths.discover().project_root), end="")
            return 0
        return _handle_launch(service, argv)
    except CodexdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _handle_manage(service: CodexdService, argv: list[str]) -> int:
    parser = _build_manage_parser()
    args = parser.parse_args(argv)
    if args.subcommand is None:
        registry, decision = service.manage_summary()
        print(f"default_account = {registry.default_account or '<unset>'}")
        print(f"auto_pick_now = {decision.name if decision is not None else '<none>'}")
        for name, record in sorted(registry.accounts.items()):
            print(_format_manage_account_line(name, record, registry.default_account))
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
                print(_format_refresh_account_line(name, result.source, result.snapshot))
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
    forced_account, passthrough_args = _extract_account_passthrough(argv)
    if is_admin_passthrough_command(passthrough_args):
        service.passthrough(passthrough_args, forced_account=forced_account)
        return 0
    parser = _build_launch_parser()
    args, codex_args = parser.parse_known_args(argv)
    service.launch(codex_args, forced_account=args.account)
    return 0


def _parse_import_args(argv: list[str]) -> argparse.Namespace:
    return _build_import_parser().parse_args(argv)


def _parse_add_args(argv: list[str]) -> argparse.Namespace:
    return _build_add_parser().parse_args(argv)


def _parse_remove_args(argv: list[str]) -> argparse.Namespace:
    return _build_remove_parser().parse_args(argv)


def _parse_debug_wrapper_args(argv: list[str]) -> argparse.Namespace:
    return _build_debug_wrapper_parser().parse_args(argv)


def _extract_account_passthrough(argv: list[str]) -> tuple[str | None, list[str]]:
    if len(argv) >= 2 and argv[0] == "--account":
        return argv[1], argv[2:]
    if argv and argv[0].startswith("--account="):
        return argv[0].split("=", 1)[1], argv[1:]
    return None, argv


def _read_access_token() -> str:
    if not sys.stdin.isatty():
        token = sys.stdin.read().strip()
        if token:
            return token
    token = os.environ.get("CODEX_ACCESS_TOKEN", "").strip()
    return token


def _format_manage_account_line(
    name: str,
    record: AccountRecord,
    default_account: str | None,
) -> str:
    prefix = name
    if default_account == name:
        prefix = f"{prefix} [default]"
    if record.last_status_error:
        prefix = f"{prefix} [error]"
    parts = [_format_status_summary(record.cached_snapshot())]
    if record.last_status_source and record.last_status_source != "live":
        parts.append(f"Source: {record.last_status_source.title()}")
    if record.last_status_error:
        parts.append(f"Error: {record.last_status_error}")
    return f"{prefix}: {' | '.join(parts)}"


def _format_refresh_account_line(
    name: str,
    source: str,
    snapshot: AccountStatusSnapshot,
) -> str:
    parts = [_format_status_summary(snapshot)]
    if source != "live":
        parts.append(f"Source: {source.title()}")
    return f"{name}: {' | '.join(parts)}"


def _format_status_summary(snapshot: AccountStatusSnapshot | None) -> str:
    if snapshot is None:
        return "Plan: ? | Primary: ? | Secondary: ?"
    return " | ".join(
        [
            f"Plan: {_format_plan(snapshot.plan_type)}",
            f"{_window_label(snapshot.primary, 'Primary')}: {_remaining_percent(snapshot.primary)}",
            f"{_window_label(snapshot.secondary, 'Secondary')}: {_remaining_percent(snapshot.secondary)}",
        ],
    )


def _format_plan(plan_type: str | None) -> str:
    if not plan_type:
        return "?"
    return plan_type.replace("_", " ").title()


def _remaining_percent(window: RateLimitWindow | None) -> str:
    if window is None:
        return "?"
    remaining = max(0, min(100, 100 - window.used_percent))
    return f"{remaining}%"


def _window_label(window: RateLimitWindow | None, fallback: str) -> str:
    if window is None or window.window_duration_mins is None:
        return fallback
    minutes = window.window_duration_mins
    if minutes == 10080:
        return "Weekly"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "1-day" if days == 1 else f"{days}-days"
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1-hour" if hours == 1 else f"{hours}-hours"
    return f"{minutes}-mins"


def _build_root_help_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd",
        usage="codexd [--account NAME] [codex args...] | codexd <command> ...",
        description=dedent(
            """
            Codexd manages multiple isolated Codex homes and routes Codex through the
            best available managed account.

            Codex CLI:
              codexd [codex args...]     Run the Codex CLI under the selected managed account.
              --account NAME             Force a specific managed account for the forwarded Codex run.

            Codexd commands:
              import NAME                Import the current real ~/.codex into managed storage.
              add NAME                   Create a managed account home and log in with a Codex access token.
              remove NAME                Remove an account from management and move it to trash.
              manage                     Show or update managed-account state.
              debug-wrapper              Print the generated install wrapper script for maintenance/debugging.

            Manage subcommands:
              manage default NAME        Set the default compatibility account.
              manage refresh [NAME]      Refresh cached account status for one account.
              manage refresh --all       Refresh cached account status for every managed account.
              manage inspect NAME        Print detailed stored metadata for one account.
            """
        ).strip(),
        epilog=dedent(
            """
            Forwarded Codex flags and subcommands are passed through as plain Codex CLI arguments.
            For Codex-native command details, run: codex --help
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--account",
        metavar="NAME",
        help="force a specific managed account for the forwarded Codex CLI run",
    )
    return parser


def _build_launch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd",
        usage="codexd [--account NAME] [codex args...]",
        description=dedent(
            """
            Run the Codex CLI under codexd account management.

            Any remaining flags and subcommands are forwarded to Codex itself.
            For the full forwarded CLI surface, see: codex --help
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--account",
        metavar="NAME",
        help="force a specific managed account instead of auto-picking the best account",
    )
    return parser


def _build_import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd import",
        description=dedent(
            """
            Import the current real ~/.codex home into managed storage.

            This copies the full durable Codex home into the named managed account,
            verifies the import, and then replaces ~/.codex with the compatibility symlink.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    parser.add_argument(
        "name",
        metavar="NAME",
        help="managed account name to create from the current ~/.codex home",
    )
    return parser


def _build_add_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd add",
        description=dedent(
            """
            Create a fresh managed account home and log into Codex there.

            The new account is stored in codexd-managed state rather than in the shared ~/.codex path.
            Provide the access token on stdin or through CODEX_ACCESS_TOKEN.
            Managed accounts default to OS keyring credential storage unless --allow-file-auth is set.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    parser.add_argument(
        "name",
        metavar="NAME",
        help="managed account name to create and log into",
    )
    parser.add_argument(
        "--allow-file-auth",
        action="store_true",
        help="allow plaintext auth.json storage instead of requiring OS keyring-backed credentials",
    )
    return parser


def _build_remove_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd remove",
        description=dedent(
            """
            Remove a managed account from codexd.

            The account home is moved into the codexd trash area instead of being deleted immediately.
            If the removed account was the default, codexd reassigns the default when possible.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    parser.add_argument(
        "name",
        metavar="NAME",
        help="managed account name to remove",
    )
    return parser


def _build_manage_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexd manage",
        description=dedent(
            """
            Show or update codexd managed-account state.

            Running `codexd manage` with no subcommand prints the current summary view,
            including the default account, the current auto-pick choice, and last-known status.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="subcommands",
        metavar="{default,refresh,inspect}",
    )

    default_parser = subparsers.add_parser(
        "default",
        help="set the default compatibility account",
        description="Set the default compatibility account and repoint ~/.codex to that managed home.",
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    default_parser.add_argument(
        "name",
        metavar="NAME",
        help="managed account name to make the default compatibility account",
    )

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="refresh cached account status",
        description=dedent(
            """
            Refresh stored rate-limit and account status information.

            Refresh one named account, or use --all to refresh every managed account.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    refresh_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        help="managed account name to refresh; defaults to the configured default account when omitted",
    )
    refresh_parser.add_argument(
        "--all",
        action="store_true",
        help="refresh every managed account instead of just one account",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="print detailed stored metadata for one account",
        description="Print detailed stored metadata for one managed account in TOML form.",
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
    inspect_parser.add_argument(
        "name",
        metavar="NAME",
        help="managed account name to inspect",
    )

    return parser


def _build_debug_wrapper_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="codexd debug-wrapper",
        description=dedent(
            """
            Print the generated install wrapper script.

            This is a maintenance/debug command for inspecting the wrapper content without installing it.
            """
        ).strip(),
        formatter_class=HELP_FORMATTER,
        allow_abbrev=False,
    )
