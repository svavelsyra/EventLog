from __future__ import annotations

from functools import partial
from pathlib import Path
import tkinter as tk
from typing import cast

import pytest

import src.app as app_module
from src.config import BootstrapUiConfig, DatabaseConfig, MainWindowConfig, load_app_config, load_bootstrap_ui_config
from src.core.app_runtime_state import AppRuntimeState
from src.db.repositories.startup_bootstrap import (
    BackendCleanupConcern,
    BackendCleanupError,
    BackendCleanupOutcome,
    BackendCleanupReport,
    BackendCleanupStatus,
    BootstrapRepositoryRequest,
    bootstrap_repository,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.gui.app_shell import AppShell
from src.gui.presenters.startup_dialog_presenter import StartupDialogSuccess
from src.gui.startup_dialog_controller import StartupDialogController
from src.gui.views.main_window_shell_view import MainWindowShellView
from src.gui.views.startup_dialog_view import StartupDialogView
from tests.gui_support import run_isolated_tk_scenario


pytestmark = pytest.mark.integration


def _make_database_config(database_path: Path) -> DatabaseConfig:
    return DatabaseConfig(
        dialect="sqlite",
        database_path=str(database_path),
        require_key_file=False,
        min_password_length=8,
        kdf_iterations=2,
    )


def _build_bootstrap_request(
    database_config: DatabaseConfig,
    *,
    create_new_database: bool,
) -> BootstrapRepositoryRequest:
    return BootstrapRepositoryRequest(
        target=database_config.bootstrap_target,
        creation_defaults=database_config.creation_defaults,
        password="",
        key_file_path=None,
        create_new_database=create_new_database,
        key_preparer=None,
    )


def _write_runtime_config(config_path: Path, *, database_path: Path, log_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    relative_log_path = log_path.relative_to(config_path.parent).as_posix()
    config_path.write_text(
        (
            "[DEFAULT]\n"
            "db_type = sqlite\n\n"
            "[sqlite]\n"
            f"database_path = {database_path.name}\n\n"
            "[Logging]\n"
            "file_logging_enabled = true\n"
            f"log_file_path = {relative_log_path}\n"
            "log_file_backup_count = 0\n"
        ),
        encoding="utf-8",
    )


def _prepare_startup_reset_artifacts(base_dir: Path) -> tuple[DatabaseConfig, Path, Path, Path]:
    database_path = base_dir / "remembered.db"
    wal_path = Path(f"{database_path}-wal")
    log_path = base_dir / "logs" / "eventlog.log"
    config_path = base_dir / "config.ini"

    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("current", encoding="utf-8")
    _write_runtime_config(config_path, database_path=database_path, log_path=log_path)

    return _make_database_config(database_path), config_path, log_path, wal_path


def _prepare_main_window_reset_artifacts(base_dir: Path) -> tuple[DatabaseConfig, Path, Path]:
    database_path = base_dir / "active.db"
    log_path = base_dir / "logs" / "eventlog.log"
    config_path = base_dir / "config.ini"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("current", encoding="utf-8")
    _write_runtime_config(config_path, database_path=database_path, log_path=log_path)

    return _make_database_config(database_path), config_path, log_path


def _build_active_startup_result(database_config: DatabaseConfig) -> StartupDialogSuccess:
    create_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            create_new_database=True,
        )
    )
    assert create_result.succeeded is True
    assert create_result.failure is None
    assert create_result.invalidate_access is not None
    create_result.invalidate_access()

    reopen_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            create_new_database=False,
        )
    )
    assert reopen_result.succeeded is True
    assert reopen_result.failure is None
    assert reopen_result.repository is not None
    assert reopen_result.invalidate_access is not None
    assert reopen_result.backend_cleanup is not None

    return StartupDialogSuccess(
        repository=reopen_result.repository,
        remembered_target=database_config.bootstrap_target,
        invalidate_access=reopen_result.invalidate_access,
        backend_cleanup=reopen_result.backend_cleanup,
    )


def _safe_widget_exists(widget: tk.Misc) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _scenario_startup_emergency_reset(
    root: tk.Tk,
    *,
    database_config: DatabaseConfig,
    config_path: Path,
    fail_bootstrap_save: bool,
    fail_log_cleanup: bool,
) -> dict[str, object]:
    captured_view: dict[str, StartupDialogView] = {}
    captured_error_message = ""
    window_was_open_before_teardown = False
    original_save = app_module.save_bootstrap_target_config
    original_unlink = app_module.Path.unlink
    log_path = config_path.parent / "logs" / "eventlog.log"

    def view_factory(master: tk.Misc) -> StartupDialogView:
        view = StartupDialogView(master)
        captured_view["view"] = view
        return view

    if fail_bootstrap_save:
        def _failing_save(_config_path: Path, _target: object) -> None:
            raise OSError("locked")

        app_module.save_bootstrap_target_config = _failing_save

    if fail_log_cleanup:
        def _failing_unlink(self: Path, *, missing_ok: bool = False) -> None:
            if self == log_path:
                raise OSError("locked")
            original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

        app_module.Path.unlink = _failing_unlink

    callback = app_module._build_startup_emergency_reset_callback(
        database_config,
        config_path=config_path,
    )
    assert callback is not None
    controller = StartupDialogController(
        database_config,
        view_factory=view_factory,
        emergency_reset_callback=callback,
    )

    def trigger_reset(_scheduled: str) -> None:
        nonlocal captured_error_message, window_was_open_before_teardown
        view = captured_view["view"]
        view.emergency_reset_button.invoke()
        window_was_open_before_teardown = _safe_widget_exists(view.window)
        if window_was_open_before_teardown:
            captured_error_message = view.error_message_var.get()
            view.destroy()

    root.after(0, trigger_reset, "scheduled")
    try:
        controller_result = controller.run(root=root)
    finally:
        app_module.save_bootstrap_target_config = original_save
        app_module.Path.unlink = original_unlink

    view = captured_view["view"]
    return {
        "controller_result_is_none": controller_result is None,
        "window_exists_after_run": _safe_widget_exists(view.window),
        "window_was_open_before_teardown": window_was_open_before_teardown,
        "error_message_after_reset": captured_error_message,
    }


class _ShellSpy:
    def __init__(self, *, snapshot_config: MainWindowConfig | None = None) -> None:
        self.close_called = False
        self.snapshot_config = snapshot_config

    def close(self) -> None:
        self.close_called = True

    def snapshot_main_window_config(self) -> MainWindowConfig | None:
        return self.snapshot_config


def _scenario_main_window_reset(
    root: tk.Tk,
    *,
    database_config: DatabaseConfig,
    config_path: Path,
    fail_bootstrap_save: bool,
    fail_log_cleanup: bool,
    backend_cleanup_failure: bool,
    missing_invalidator: bool,
) -> dict[str, object]:
    startup_result = _build_active_startup_result(database_config)
    original_save = app_module.save_bootstrap_target_config
    original_unlink = app_module.Path.unlink
    log_path = config_path.parent / "logs" / "eventlog.log"

    if fail_bootstrap_save:
        def _failing_save(_config_path: Path, _target: object) -> None:
            raise OSError("locked")

        app_module.save_bootstrap_target_config = _failing_save

    if fail_log_cleanup:
        def _failing_unlink(self: Path, *, missing_ok: bool = False) -> None:
            if self == log_path:
                raise OSError("locked")
            original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

        app_module.Path.unlink = _failing_unlink

    if backend_cleanup_failure:
        def _failing_backend_cleanup() -> BackendCleanupOutcome:
            raise BackendCleanupError(
                "sanitized cleanup failure",
                outcome=BackendCleanupOutcome(
                    status=BackendCleanupStatus.PARTIAL,
                    cleanup_performed=False,
                    report=BackendCleanupReport(
                        access_release_performed=True,
                        artifacts_enumerated=1,
                        artifacts_removed=0,
                        artifacts_failed=1,
                        failed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
                        failed_artifact_kinds=("database",),
                    ),
                ),
            )

        startup_result = StartupDialogSuccess(
            repository=startup_result.repository,
            remembered_target=startup_result.remembered_target,
            invalidate_access=startup_result.invalidate_access,
            backend_cleanup=_failing_backend_cleanup,
        )

    if missing_invalidator:
        startup_result = StartupDialogSuccess(
            repository=startup_result.repository,
            remembered_target=startup_result.remembered_target,
            invalidate_access=None,
            backend_cleanup=startup_result.backend_cleanup,
        )

    shell = _ShellSpy()
    callback = app_module._build_main_window_reset_callback(
        cast(AppShell, cast(object, shell)),
        startup_result,
        config_path=config_path,
    )
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        reset_callback=callback,
    )
    database_exists_before_reset = Path(database_config.database_path).exists()

    try:
        view.reset_button.invoke()
    finally:
        app_module.save_bootstrap_target_config = original_save
        app_module.Path.unlink = original_unlink

    return {
        "close_called": shell.close_called,
        "status_text": view.status_label.cget("text"),
        "database_exists_before_reset": database_exists_before_reset,
    }


def _scenario_main_window_close(
    root: tk.Tk,
    *,
    database_config: DatabaseConfig,
    config_path: Path,
    missing_invalidator: bool,
    runtime_operator: str,
) -> dict[str, object]:
    startup_result = _build_active_startup_result(database_config)
    repository = cast(EventLogRepository, startup_result.repository)
    startup_result = StartupDialogSuccess(
        repository=startup_result.repository,
        remembered_target=startup_result.remembered_target,
        invalidate_access=startup_result.invalidate_access,
        backend_cleanup=startup_result.backend_cleanup,
        last_operator="Sgt Example",
    )
    snapshot_config = MainWindowConfig(
        window_state="zoomed",
        window_width=1440,
        window_height=900,
        window_x=25,
        window_y=35,
    )
    bootstrap_ui_config = BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="normal",
            window_width=1200,
            window_height=700,
            window_x=100,
            window_y=100,
        ),
        language="en",
        last_operator="Earlier Operator",
    )

    if missing_invalidator:
        startup_result = StartupDialogSuccess(
            repository=startup_result.repository,
            remembered_target=startup_result.remembered_target,
            invalidate_access=None,
            backend_cleanup=startup_result.backend_cleanup,
            last_operator=startup_result.last_operator,
        )

    shell = _ShellSpy(snapshot_config=snapshot_config)
    app_runtime_state = AppRuntimeState(active_operator=startup_result.last_operator)
    app_runtime_state.active_operator = runtime_operator
    callback = app_module._build_main_window_close_callback(
        cast(AppShell, cast(object, shell)),
        startup_result,
        config_path=config_path,
        bootstrap_ui_config=bootstrap_ui_config,
        app_runtime_state=app_runtime_state,
    )
    view = MainWindowShellView(
        root,
        app_runtime_state=app_runtime_state,
        close_callback=callback,
    )
    database_exists_before_close = Path(database_config.database_path).exists()
    view.handle_close_requested()

    repository_access_denied = False
    try:
        repository.get_all_event_entries()
    except Exception as exc:
        repository_access_denied = "closed" in str(exc).lower()

    return {
        "close_called": shell.close_called,
        "status_text": view.status_label.cget("text"),
        "database_exists_before_close": database_exists_before_close,
        "repository_access_denied": repository_access_denied,
    }


def test_startup_dialog_emergency_reset_button_cleans_remembered_runtime_artifacts_and_closes_dialog(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path, wal_path = _prepare_startup_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_startup_emergency_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=False,
            fail_log_cleanup=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "controller_result_is_none": True,
        "window_exists_after_run": False,
        "window_was_open_before_teardown": False,
        "error_message_after_reset": "",
    }
    assert Path(database_config.database_path).exists() is False
    assert wal_path.exists() is False
    assert log_path.exists() is False
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False
    assert parser.get("Logging", "log_file_path") == "logs/eventlog.log"


def test_startup_dialog_emergency_reset_button_shows_failure_message_when_bootstrap_memory_clear_fails(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path, wal_path = _prepare_startup_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_startup_emergency_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=True,
            fail_log_cleanup=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "controller_result_is_none": True,
        "window_exists_after_run": False,
        "window_was_open_before_teardown": True,
        "error_message_after_reset": (
            "MISSLYCKADES\n"
            "Följ upp manuellt: startupminne.\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
    }
    assert Path(database_config.database_path).exists() is False
    assert wal_path.exists() is False
    assert log_path.exists() is False
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name


def test_startup_dialog_emergency_reset_button_keeps_dialog_open_and_lists_combined_follow_up_failures(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path, wal_path = _prepare_startup_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_startup_emergency_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=True,
            fail_log_cleanup=True,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "controller_result_is_none": True,
        "window_exists_after_run": False,
        "window_was_open_before_teardown": True,
        "error_message_after_reset": (
            "MISSLYCKADES\n"
            "Följ upp manuellt: loggar, startupminne.\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
    }
    assert Path(database_config.database_path).exists() is False
    assert wal_path.exists() is False
    assert log_path.exists() is True
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name


def test_main_window_reset_button_runs_active_context_reset_and_closes_shell_on_success(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=False,
            fail_log_cleanup=False,
            backend_cleanup_failure=False,
            missing_invalidator=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": True,
        "status_text": "Statusyta - loggning och operatörsstatus kommer senare.",
        "database_exists_before_reset": True,
    }
    assert Path(database_config.database_path).exists() is False
    assert log_path.exists() is False
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False


def test_main_window_reset_button_keeps_shell_open_and_shows_failure_message_when_bootstrap_memory_clear_fails(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=True,
            fail_log_cleanup=False,
            backend_cleanup_failure=False,
            missing_invalidator=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": False,
        "status_text": (
            "MISSLYCKADES\n"
            "Följ upp manuellt.\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
        "database_exists_before_reset": True,
    }
    assert Path(database_config.database_path).exists() is False
    assert log_path.exists() is False
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name


def test_main_window_reset_button_keeps_shell_open_when_log_cleanup_fails_after_active_cleanup(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=False,
            fail_log_cleanup=True,
            backend_cleanup_failure=False,
            missing_invalidator=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": False,
        "status_text": (
            "MISSLYCKADES\n"
            "Följ upp manuellt.\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
        "database_exists_before_reset": True,
    }
    assert Path(database_config.database_path).exists() is False
    assert log_path.exists() is True
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False


def test_main_window_reset_button_blocks_close_and_keeps_artifacts_when_backend_cleanup_fails_before_log_phase(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=False,
            fail_log_cleanup=False,
            backend_cleanup_failure=True,
            missing_invalidator=False,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": False,
        "status_text": (
            "MISSLYCKADES\n"
            "Följ upp manuellt.\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
        "database_exists_before_reset": True,
    }
    assert Path(database_config.database_path).exists() is True
    assert log_path.exists() is True
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False


def test_main_window_reset_button_surfaces_access_denial_failure_when_active_context_exposes_no_invalidator(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_reset,
            database_config=database_config,
            config_path=config_path,
            fail_bootstrap_save=False,
            fail_log_cleanup=False,
            backend_cleanup_failure=False,
            missing_invalidator=True,
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": False,
        "status_text": (
            "MISSLYCKADES\n"
            "Eventuella nyckelfiler behöver tas bort manuellt."
        ),
        "database_exists_before_reset": True,
    }
    assert Path(database_config.database_path).exists() is True
    assert log_path.exists() is True
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name


def test_main_window_close_request_releases_active_context_and_closes_shell_without_deleting_runtime_artifacts(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_close,
            database_config=database_config,
            config_path=config_path,
            missing_invalidator=False,
            runtime_operator="Captain Runtime",
        )
    )
    parser = load_app_config(config_path)
    bootstrap_ui = load_bootstrap_ui_config(config_path)

    assert result == {
        "close_called": True,
        "status_text": "Statusyta - loggning och operatörsstatus kommer senare.",
        "database_exists_before_close": True,
        "repository_access_denied": True,
    }
    assert Path(database_config.database_path).exists() is True
    assert log_path.exists() is True
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name
    assert bootstrap_ui == BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="zoomed",
            window_width=1440,
            window_height=900,
            window_x=25,
            window_y=35,
        ),
        language="en",
        last_operator="Captain Runtime",
    )


def test_main_window_close_request_keeps_shell_open_and_preserves_access_when_active_context_exposes_no_invalidator(
    tmp_path: Path,
) -> None:
    database_config, config_path, log_path = _prepare_main_window_reset_artifacts(tmp_path)

    result = run_isolated_tk_scenario(
        partial(
            _scenario_main_window_close,
            database_config=database_config,
            config_path=config_path,
            missing_invalidator=True,
            runtime_operator="",
        )
    )
    parser = load_app_config(config_path)

    assert result == {
        "close_called": False,
        "status_text": "MISSLYCKADES",
        "database_exists_before_close": True,
        "repository_access_denied": False,
    }
    assert Path(database_config.database_path).exists() is True
    assert log_path.exists() is True
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == Path(database_config.database_path).name
    assert parser.has_section("Application") is False
    assert parser.has_section("User") is False





