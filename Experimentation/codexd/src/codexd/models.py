from __future__ import annotations

from dataclasses import field
from dataclasses import dataclass


@dataclass(slots=True)
class RateLimitWindow:
    used_percent: int
    resets_at: int | None = None
    window_duration_mins: int | None = None

    @classmethod
    def from_api(cls, payload: object) -> "RateLimitWindow | None":
        if not isinstance(payload, dict):
            return None
        used_percent = payload.get("usedPercent")
        if not isinstance(used_percent, int):
            return None
        resets_at = payload.get("resetsAt")
        window_duration_mins = payload.get("windowDurationMins")
        return cls(
            used_percent=used_percent,
            resets_at=resets_at if isinstance(resets_at, int) else None,
            window_duration_mins=(
                window_duration_mins if isinstance(window_duration_mins, int) else None
            ),
        )


@dataclass(slots=True)
class AccountStatusSnapshot:
    plan_type: str | None = None
    primary: RateLimitWindow | None = None
    secondary: RateLimitWindow | None = None
    account_type: str | None = None
    email: str | None = None
    requires_openai_auth: bool | None = None

    @classmethod
    def from_api(
        cls,
        account_payload: object,
        rate_limit_payload: object,
    ) -> "AccountStatusSnapshot":
        account = None
        requires_openai_auth = None
        if isinstance(account_payload, dict):
            maybe_account = account_payload.get("account")
            if isinstance(maybe_account, dict):
                account = maybe_account
            if isinstance(account_payload.get("requiresOpenaiAuth"), bool):
                requires_openai_auth = account_payload["requiresOpenaiAuth"]

        bucket = _select_rate_limit_bucket(rate_limit_payload)
        primary = None
        secondary = None
        plan_type = None
        if bucket is not None:
            primary = RateLimitWindow.from_api(bucket.get("primary"))
            secondary = RateLimitWindow.from_api(bucket.get("secondary"))
            maybe_plan_type = bucket.get("planType")
            if isinstance(maybe_plan_type, str):
                plan_type = maybe_plan_type

        account_type = None
        email = None
        if account is not None:
            maybe_type = account.get("type")
            maybe_email = account.get("email")
            maybe_plan = account.get("planType")
            if isinstance(maybe_type, str):
                account_type = maybe_type
            if isinstance(maybe_email, str):
                email = maybe_email
            if plan_type is None and isinstance(maybe_plan, str):
                plan_type = maybe_plan

        return cls(
            plan_type=plan_type,
            primary=primary,
            secondary=secondary,
            account_type=account_type,
            email=email,
            requires_openai_auth=requires_openai_auth,
        )

    @classmethod
    def from_registry_fields(cls, payload: dict[str, object]) -> "AccountStatusSnapshot | None":
        primary_used = payload.get("last_primary_used_percent")
        secondary_used = payload.get("last_secondary_used_percent")
        plan_type = payload.get("last_plan_type")
        account_type = payload.get("last_account_type")
        email = payload.get("last_account_email")
        requires_openai_auth = payload.get("last_requires_openai_auth")

        primary = None
        secondary = None
        if isinstance(primary_used, int):
            primary = RateLimitWindow(
                used_percent=primary_used,
                resets_at=(
                    payload.get("last_primary_resets_at")
                    if isinstance(payload.get("last_primary_resets_at"), int)
                    else None
                ),
            )
        if isinstance(secondary_used, int):
            secondary = RateLimitWindow(
                used_percent=secondary_used,
                resets_at=(
                    payload.get("last_secondary_resets_at")
                    if isinstance(payload.get("last_secondary_resets_at"), int)
                    else None
                ),
            )
        if not any(
            [
                primary is not None,
                secondary is not None,
                isinstance(plan_type, str),
            ]
        ):
            return None
        return cls(
            plan_type=plan_type if isinstance(plan_type, str) else None,
            primary=primary,
            secondary=secondary,
            account_type=account_type if isinstance(account_type, str) else None,
            email=email if isinstance(email, str) else None,
            requires_openai_auth=(
                requires_openai_auth if isinstance(requires_openai_auth, bool) else None
            ),
        )


@dataclass(slots=True)
class StatusReadResult:
    source: str
    snapshot: AccountStatusSnapshot | None = None
    error: str | None = None


@dataclass(slots=True)
class AccountRecord:
    name: str
    home_path: str
    created_at: str
    imported_from_current_codex_home: bool = False
    last_status_read_at: str | None = None
    last_status_source: str | None = None
    last_primary_used_percent: int | None = None
    last_primary_resets_at: int | None = None
    last_secondary_used_percent: int | None = None
    last_secondary_resets_at: int | None = None
    last_plan_type: str | None = None
    last_successful_launch_at: str | None = None
    last_selected_at: str | None = None
    last_status_error: str | None = None
    last_account_type: str | None = None
    last_account_email: str | None = None
    last_requires_openai_auth: bool | None = None

    def cached_snapshot(self) -> AccountStatusSnapshot | None:
        return AccountStatusSnapshot.from_registry_fields(self.to_registry_dict())

    def apply_status(self, result: StatusReadResult, read_at: str) -> None:
        self.last_status_read_at = read_at
        self.last_status_source = result.source
        self.last_status_error = result.error
        if result.snapshot is None:
            return
        self.last_plan_type = result.snapshot.plan_type
        self.last_account_type = result.snapshot.account_type
        self.last_account_email = result.snapshot.email
        self.last_requires_openai_auth = result.snapshot.requires_openai_auth
        if result.snapshot.primary is not None:
            self.last_primary_used_percent = result.snapshot.primary.used_percent
            self.last_primary_resets_at = result.snapshot.primary.resets_at
        if result.snapshot.secondary is not None:
            self.last_secondary_used_percent = result.snapshot.secondary.used_percent
            self.last_secondary_resets_at = result.snapshot.secondary.resets_at

    def to_registry_dict(self) -> dict[str, object]:
        return {
            "home_path": self.home_path,
            "created_at": self.created_at,
            "imported_from_current_codex_home": self.imported_from_current_codex_home,
            "last_status_read_at": self.last_status_read_at,
            "last_status_source": self.last_status_source,
            "last_primary_used_percent": self.last_primary_used_percent,
            "last_primary_resets_at": self.last_primary_resets_at,
            "last_secondary_used_percent": self.last_secondary_used_percent,
            "last_secondary_resets_at": self.last_secondary_resets_at,
            "last_plan_type": self.last_plan_type,
            "last_successful_launch_at": self.last_successful_launch_at,
            "last_selected_at": self.last_selected_at,
            "last_status_error": self.last_status_error,
            "last_account_type": self.last_account_type,
            "last_account_email": self.last_account_email,
            "last_requires_openai_auth": self.last_requires_openai_auth,
        }

    @classmethod
    def from_registry_dict(cls, name: str, payload: dict[str, object]) -> "AccountRecord":
        return cls(
            name=name,
            home_path=str(payload["home_path"]),
            created_at=str(payload["created_at"]),
            imported_from_current_codex_home=bool(
                payload.get("imported_from_current_codex_home", False)
            ),
            last_status_read_at=_maybe_str(payload.get("last_status_read_at")),
            last_status_source=_maybe_str(payload.get("last_status_source")),
            last_primary_used_percent=_maybe_int(payload.get("last_primary_used_percent")),
            last_primary_resets_at=_maybe_int(payload.get("last_primary_resets_at")),
            last_secondary_used_percent=_maybe_int(
                payload.get("last_secondary_used_percent")
            ),
            last_secondary_resets_at=_maybe_int(payload.get("last_secondary_resets_at")),
            last_plan_type=_maybe_str(payload.get("last_plan_type")),
            last_successful_launch_at=_maybe_str(payload.get("last_successful_launch_at")),
            last_selected_at=_maybe_str(payload.get("last_selected_at")),
            last_status_error=_maybe_str(payload.get("last_status_error")),
            last_account_type=_maybe_str(payload.get("last_account_type")),
            last_account_email=_maybe_str(payload.get("last_account_email")),
            last_requires_openai_auth=(
                payload.get("last_requires_openai_auth")
                if isinstance(payload.get("last_requires_openai_auth"), bool)
                else None
            ),
        )


@dataclass(slots=True)
class Registry:
    default_account: str | None = None
    accounts: dict[str, AccountRecord] = field(default_factory=dict)


def _select_rate_limit_bucket(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    buckets = payload.get("rateLimitsByLimitId")
    if isinstance(buckets, dict):
        preferred = buckets.get("codex")
        if isinstance(preferred, dict):
            return preferred
        for value in buckets.values():
            if isinstance(value, dict):
                return value
    direct = payload.get("rateLimits")
    if isinstance(direct, dict):
        return direct
    if "primary" in payload or "secondary" in payload:
        return payload
    return None


def _maybe_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _maybe_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
