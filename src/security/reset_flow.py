"""Shared reset-flow contract for denial-first emergency reset sequencing.

This module defines a small, caller-neutral coordinator that always attempts
immediate access denial before any slower cleanup phase. Later reset stories
can attach backend-owned cleanup behavior and caller-specific interpretation
without redefining the top-level sequencing contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from pathlib import Path
from typing import Callable

from src.config import load_app_config


ResetStep = Callable[[], None]


class ResetFailureCategory(StrEnum):
    """Sanitized reset-phase failure categories exposed to callers."""

    ACCESS_DENIAL = "access_denial"
    CLEANUP = "cleanup"


@dataclass(frozen=True, slots=True)
class ResetOutcome:
    """Neutral phase-oriented outcome for a shared reset attempt."""

    had_active_context: bool
    denial_succeeded: bool
    cleanup_started: bool
    cleanup_completed: bool
    failure_categories: tuple[ResetFailureCategory, ...] = ()


class ResetCoordinator:
    """Coordinate denial-first reset sequencing for the active secured context."""

    def __init__(
        self,
        *,
        deny_access: ResetStep | None,
        cleanup: ResetStep | None = None,
    ) -> None:
        self._deny_access = deny_access
        self._cleanup = cleanup

    def run(self) -> ResetOutcome:
        """Run the shared reset flow with immediate denial before slower cleanup."""
        if self._deny_access is None:
            return ResetOutcome(
                had_active_context=False,
                denial_succeeded=True,
                cleanup_started=False,
                cleanup_completed=False,
            )

        failure_categories: list[ResetFailureCategory] = []
        denial_succeeded = False
        cleanup_started = False
        cleanup_completed = False

        try:
            self._deny_access()
            denial_succeeded = True
        except Exception:
            failure_categories.append(ResetFailureCategory.ACCESS_DENIAL)
            return ResetOutcome(
                had_active_context=True,
                denial_succeeded=False,
                cleanup_started=False,
                cleanup_completed=False,
                failure_categories=tuple(failure_categories),
            )

        if self._cleanup is not None:
            cleanup_started = True
            try:
                self._cleanup()
                cleanup_completed = True
            except Exception:
                failure_categories.append(ResetFailureCategory.CLEANUP)

        return ResetOutcome(
            had_active_context=True,
            denial_succeeded=denial_succeeded,
            cleanup_started=cleanup_started,
            cleanup_completed=cleanup_completed,
            failure_categories=tuple(failure_categories),
        )


def enumerate_log_cleanup_targets(config_path: str | PathLike[str]) -> tuple[Path, ...]:
    """Return existing runtime-known log artifacts derived from current config.

    This helper stays deliberately narrow and neutral for `002.006.004`:
    - file logging must be explicitly enabled
    - `log_file_path` may be relative to the active config file location
    - only the current log file and existing rotated siblings are returned
    - missing files or malformed logging config degrade to an empty result
    """

    parser = load_app_config(config_path)

    try:
        file_logging_enabled = parser.getboolean("Logging", "file_logging_enabled", fallback=False)
    except ValueError:
        return ()

    if not file_logging_enabled:
        return ()

    log_file_path = parser.get("Logging", "log_file_path", fallback="").strip()
    if not log_file_path:
        return ()

    try:
        backup_count = parser.getint("Logging", "log_file_backup_count", fallback=0)
    except ValueError:
        backup_count = 0

    normalized_config_path = Path(config_path).expanduser()
    configured_log_path = Path(log_file_path).expanduser()
    if not configured_log_path.is_absolute():
        configured_log_path = normalized_config_path.parent / configured_log_path

    candidate_paths = [configured_log_path]
    for backup_index in range(1, max(0, backup_count) + 1):
        candidate_paths.append(configured_log_path.with_name(f"{configured_log_path.name}.{backup_index}"))

    return tuple(path for path in candidate_paths if path.is_file())


def delete_log_cleanup_targets(config_path: str | PathLike[str]) -> None:
    """Delete runtime-known current and rotated log targets for the active config.

    The helper is intentionally narrow for the current `002.006.004` slice:
    it only targets files already enumerated by the runtime-known log-target
    contract and treats reruns neutrally through existing-only enumeration plus
    ``missing_ok=True`` deletion.
    """

    for target_path in enumerate_log_cleanup_targets(config_path):
        target_path.unlink(missing_ok=True)


__all__ = [
    "ResetCoordinator",
    "ResetFailureCategory",
    "ResetOutcome",
    "delete_log_cleanup_targets",
    "enumerate_log_cleanup_targets",
]

