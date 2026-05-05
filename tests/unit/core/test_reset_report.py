from __future__ import annotations

import pytest

from src.core import (
    ResetAttemptFacts,
    ResetFollowUpFacts,
    ResetFollowUpIssue,
    ResetReport,
    assemble_reset_report,
    assemble_reset_report_from_facts,
    normalize_reset_follow_up_issues,
)


pytestmark = pytest.mark.unit


def test_assemble_reset_report_returns_reset_status_without_follow_up_issues() -> None:
    report = assemble_reset_report(had_failure=False)

    assert report == ResetReport(
        success=True,
        follow_up_issues=(),
    )


def test_assemble_reset_report_returns_failed_status_with_follow_up_issues() -> None:
    report = assemble_reset_report(
        had_failure=True,
        follow_up_issues=(
            ResetFollowUpIssue.DATABASE_ARTIFACTS,
            ResetFollowUpIssue.LOG_ARTIFACTS,
        ),
    )

    assert report == ResetReport(
        success=False,
        follow_up_issues=(
            ResetFollowUpIssue.DATABASE_ARTIFACTS,
            ResetFollowUpIssue.LOG_ARTIFACTS,
        ),
    )


def test_assemble_reset_report_deduplicates_follow_up_issues_in_order() -> None:
    report = assemble_reset_report(
        had_failure=True,
        follow_up_issues=(
            ResetFollowUpIssue.LOG_ARTIFACTS,
            ResetFollowUpIssue.DATABASE_ARTIFACTS,
            ResetFollowUpIssue.LOG_ARTIFACTS,
            ResetFollowUpIssue.BOOTSTRAP_RESET,
        ),
    )

    assert report.follow_up_issues == (
        ResetFollowUpIssue.LOG_ARTIFACTS,
        ResetFollowUpIssue.DATABASE_ARTIFACTS,
        ResetFollowUpIssue.BOOTSTRAP_RESET,
    )


def test_normalize_reset_follow_up_issues_returns_empty_tuple_for_default_facts() -> None:
    assert normalize_reset_follow_up_issues(ResetFollowUpFacts()) == ()


def test_normalize_reset_follow_up_issues_maps_each_fact_to_one_issue_in_core_order() -> None:
    issues = normalize_reset_follow_up_issues(
        ResetFollowUpFacts(
            database_artifacts_issue=True,
            log_artifacts_issue=True,
            bootstrap_reset_issue=True,
        )
    )

    assert issues == (
        ResetFollowUpIssue.DATABASE_ARTIFACTS,
        ResetFollowUpIssue.LOG_ARTIFACTS,
        ResetFollowUpIssue.BOOTSTRAP_RESET,
    )


def test_normalize_reset_follow_up_issues_can_represent_partial_reset_failures_without_raw_strings() -> None:
    issues = normalize_reset_follow_up_issues(
        ResetFollowUpFacts(
            bootstrap_reset_issue=True,
        )
    )

    assert issues == (
        ResetFollowUpIssue.BOOTSTRAP_RESET,
    )


def test_assemble_reset_report_from_facts_treats_follow_up_issues_as_failure() -> None:
    report = assemble_reset_report_from_facts(
        ResetAttemptFacts(
            follow_up=ResetFollowUpFacts(
                log_artifacts_issue=True,
            )
        )
    )

    assert report == ResetReport(
        success=False,
        follow_up_issues=(ResetFollowUpIssue.LOG_ARTIFACTS,),
    )


def test_assemble_reset_report_from_facts_preserves_phase_failure_without_follow_up_issues() -> None:
    report = assemble_reset_report_from_facts(
        ResetAttemptFacts(
            phase_failure=True,
        )
    )

    assert report == ResetReport(
        success=False,
        follow_up_issues=(),
    )


