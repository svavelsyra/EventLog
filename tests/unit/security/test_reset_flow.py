from pathlib import Path

import pytest
import src.security.reset_flow as reset_flow_module

from src.security import ResetCoordinator, ResetFailureCategory, ResetOutcome


pytestmark = pytest.mark.unit

delete_log_cleanup_targets = getattr(reset_flow_module, "delete_log_cleanup_targets")



def test_reset_coordinator_runs_immediate_denial_before_cleanup() -> None:
    phase_order: list[str] = []

    def deny_access() -> None:
        phase_order.append("deny")

    def cleanup() -> None:
        phase_order.append("cleanup")

    outcome = ResetCoordinator(deny_access=deny_access, cleanup=cleanup).run()

    assert phase_order == ["deny", "cleanup"]
    assert outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=True,
        cleanup_started=True,
        cleanup_completed=True,
    )



def test_reset_coordinator_returns_safe_outcome_when_no_active_context_loaded() -> None:
    cleanup_called = False

    def cleanup() -> None:
        nonlocal cleanup_called
        cleanup_called = True

    outcome = ResetCoordinator(deny_access=None, cleanup=cleanup).run()

    assert cleanup_called is False
    assert outcome == ResetOutcome(
        had_active_context=False,
        denial_succeeded=True,
        cleanup_started=False,
        cleanup_completed=False,
    )



def test_reset_coordinator_blocks_cleanup_when_immediate_denial_fails() -> None:
    cleanup_called = False

    def deny_access() -> None:
        raise RuntimeError("secret-handle-details should not leak")

    def cleanup() -> None:
        nonlocal cleanup_called
        cleanup_called = True

    outcome = ResetCoordinator(deny_access=deny_access, cleanup=cleanup).run()

    assert cleanup_called is False
    assert outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=False,
        cleanup_started=False,
        cleanup_completed=False,
        failure_categories=(ResetFailureCategory.ACCESS_DENIAL,),
    )



def test_reset_coordinator_reports_cleanup_failure_with_sanitized_category_only() -> None:
    def cleanup() -> None:
        raise RuntimeError("do not leak C:/secret/keyfile.bin")

    outcome = ResetCoordinator(deny_access=lambda: None, cleanup=cleanup).run()

    assert outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=True,
        cleanup_started=True,
        cleanup_completed=False,
        failure_categories=(ResetFailureCategory.CLEANUP,),
    )


def test_enumerate_log_cleanup_targets_returns_existing_runtime_known_log_files(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    current_log = logs_dir / "eventlog.log"
    rotated_first = logs_dir / "eventlog.log.1"
    rotated_second = logs_dir / "eventlog.log.2"
    current_log.write_text("current", encoding="utf-8")
    rotated_first.write_text("older", encoding="utf-8")
    rotated_second.write_text("oldest", encoding="utf-8")
    config_path.write_text(
        """
[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 3
        """.strip(),
        encoding="utf-8",
    )

    assert reset_flow_module.enumerate_log_cleanup_targets(config_path) == (
        current_log,
        rotated_first,
        rotated_second,
    )


@pytest.mark.parametrize(
    ("config_text", "expected_targets"),
    [
        (
            """
[Logging]
file_logging_enabled = false
log_file_path = logs/eventlog.log
log_file_backup_count = 2
            """.strip(),
            (),
        ),
        (
            """
[Logging]
file_logging_enabled = true
log_file_path =
log_file_backup_count = 2
            """.strip(),
            (),
        ),
        (
            """
[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 0
            """.strip(),
            (),
        ),
    ],
)
def test_enumerate_log_cleanup_targets_returns_empty_for_disabled_blank_or_missing_targets(
    tmp_path: Path,
    config_text: str,
    expected_targets: tuple[Path, ...],
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(config_text, encoding="utf-8")

    assert reset_flow_module.enumerate_log_cleanup_targets(config_path) == expected_targets


def test_delete_log_cleanup_targets_removes_existing_current_and_rotated_logs(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    current_log = logs_dir / "eventlog.log"
    rotated_first = logs_dir / "eventlog.log.1"
    rotated_second = logs_dir / "eventlog.log.2"
    current_log.write_text("current", encoding="utf-8")
    rotated_first.write_text("older", encoding="utf-8")
    rotated_second.write_text("oldest", encoding="utf-8")
    config_path.write_text(
        """
[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 3
        """.strip(),
        encoding="utf-8",
    )

    delete_log_cleanup_targets(config_path)

    assert current_log.exists() is False
    assert rotated_first.exists() is False
    assert rotated_second.exists() is False


def test_delete_log_cleanup_targets_is_rerun_safe_after_previous_log_cleanup(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    current_log = logs_dir / "eventlog.log"
    rotated_first = logs_dir / "eventlog.log.1"
    current_log.write_text("current", encoding="utf-8")
    rotated_first.write_text("older", encoding="utf-8")
    config_path.write_text(
        """
[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 2
        """.strip(),
        encoding="utf-8",
    )

    delete_log_cleanup_targets(config_path)
    delete_log_cleanup_targets(config_path)

    assert current_log.exists() is False
    assert rotated_first.exists() is False


