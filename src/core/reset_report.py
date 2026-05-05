"""Core-owned reset report assembly for shared reset outcomes.

This module keeps reset-result interpretation out of app/bootstrap wiring while
remaining machine-readable. Lower layers report sanitized facts and concern
categories; higher layers may later map these core results to final GUI wording.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ResetFollowUpIssue(StrEnum):
    """Machine-readable follow-up issues for incomplete reset work."""

    DATABASE_ARTIFACTS = "database_artifacts"
    LOG_ARTIFACTS = "logs"
    BOOTSTRAP_RESET = "bootstrap_reset"


@dataclass(frozen=True, slots=True)
class ResetFollowUpFacts:
    """Core-owned sanitized facts used to derive reset follow-up issues."""

    database_artifacts_issue: bool = False
    log_artifacts_issue: bool = False
    bootstrap_reset_issue: bool = False


@dataclass(frozen=True, slots=True)
class ResetAttemptFacts:
    """Core-owned facts describing one caller-visible reset attempt."""

    phase_failure: bool = False
    follow_up: ResetFollowUpFacts = field(default_factory=ResetFollowUpFacts)


@dataclass(frozen=True, slots=True)
class ResetReport:
    """Core-owned reset report assembled from sanitized reset facts."""

    success: bool
    follow_up_issues: tuple[ResetFollowUpIssue, ...] = ()


def normalize_reset_follow_up_issues(
    facts: ResetFollowUpFacts,
) -> tuple[ResetFollowUpIssue, ...]:
    """Return normalized follow-up issues derived from sanitized reset facts."""
    ordered_issues: list[ResetFollowUpIssue] = []
    if facts.database_artifacts_issue:
        ordered_issues.append(ResetFollowUpIssue.DATABASE_ARTIFACTS)
    if facts.log_artifacts_issue:
        ordered_issues.append(ResetFollowUpIssue.LOG_ARTIFACTS)
    if facts.bootstrap_reset_issue:
        ordered_issues.append(ResetFollowUpIssue.BOOTSTRAP_RESET)

    return tuple(ordered_issues)


def assemble_reset_report(
    *,
    had_failure: bool,
    follow_up_issues: tuple[ResetFollowUpIssue, ...] = (),
) -> ResetReport:
    """Return the core reset report for the current shared reset attempt."""
    return ResetReport(
        success=not had_failure,
        follow_up_issues=tuple(dict.fromkeys(follow_up_issues)),
    )


def assemble_reset_report_from_facts(facts: ResetAttemptFacts) -> ResetReport:
    """Return the core reset report assembled directly from sanitized attempt facts."""
    follow_up_issues = normalize_reset_follow_up_issues(facts.follow_up)
    return assemble_reset_report(
        had_failure=facts.phase_failure or bool(follow_up_issues),
        follow_up_issues=follow_up_issues,
    )


__all__ = [
    "ResetAttemptFacts",
    "ResetFollowUpFacts",
    "ResetFollowUpIssue",
    "ResetReport",
    "assemble_reset_report",
    "assemble_reset_report_from_facts",
    "normalize_reset_follow_up_issues",
]



