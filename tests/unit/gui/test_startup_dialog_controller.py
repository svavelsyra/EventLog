from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
import tkinter as tk
from typing import cast

import pytest

import src.app as app_module
from src.config import BootstrapUiConfig, DatabaseConfig, MainWindowConfig, load_app_config
from src.config.app_config import BootstrapTargetConfig
from src.core.app_runtime_state import AppRuntimeState
from src.core import ResetFollowUpIssue
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.startup_selection import PathExists, StartupFieldKind, StartupFieldName, StartupFieldRequirement
from src.db.repositories.startup_bootstrap import (
    BackendCleanup,
    BackendCleanupError,
    BackendCleanupOutcome,
    BackendCleanupReport,
    BackendCleanupStatus,
    BootstrapFailure,
    BootstrapFailureCode,
    BootstrapRepositoryResult,
    MigrationResult,
)
from src.gui.presenters.startup_dialog_presenter import (
    StartupDialogMode,
    StartupDialogPresenter,
    StartupDialogState,
    StartupDialogSubmission,
    StartupDialogSuccess,
    resolve_startup_mode,
)
from src.gui.app_shell import AppShell, MainWindowFactory, StartupControllerFactory
from src.gui.startup_dialog_controller import (
    EmergencyResetCallback,
    StartupDialogController,
    StartupDialogViewProtocol,
    TkRootProtocol,
    open_database_path_dialog,
)
from src.gui.views.startup_dialog_view import StartupDialogActionCallbacks
from src.security import ResetFailureCategory, ResetOutcome


pytestmark = pytest.mark.unit


class FakeRoot:
    def __init__(self) -> None:
        self.withdraw_called = False
        self.deiconify_called = False
        self.mainloop_called = False
        self.destroy_called = False
        self.waited_window: object | None = None
        self.on_wait_window: Callable[[], None] | None = None
        self.on_mainloop: Callable[[], None] | None = None

    def withdraw(self) -> None:
        self.withdraw_called = True

    def wait_window(self, window: object) -> None:
        self.waited_window = window
        if self.on_wait_window is not None:
            self.on_wait_window()

    def deiconify(self) -> None:
        self.deiconify_called = True

    def mainloop(self) -> None:
        self.mainloop_called = True
        if self.on_mainloop is not None:
            self.on_mainloop()

    def destroy(self) -> None:
        self.destroy_called = True


class FakeStringVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class FakeBooleanVar:
    def __init__(self, value: bool = False) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:
        self.value = value


class FakeView:
    def __init__(self, submission: StartupDialogSubmission) -> None:
        self.window = object()
        self.mode_var = FakeStringVar(submission.mode.value)
        self.use_remembered_target_var = FakeBooleanVar(submission.uses_remembered_target)
        self.dialect_var = FakeStringVar(submission.dialect)
        self.operator_value = submission.operator
        self.field_values = {
            StartupFieldName.DATABASE_PATH: submission.get_field_value(StartupFieldName.DATABASE_PATH),
            StartupFieldName.PASSWORD: submission.get_field_value(StartupFieldName.PASSWORD),
            StartupFieldName.PASSWORD_CONFIRMATION: submission.get_field_value(
                StartupFieldName.PASSWORD_CONFIRMATION
            ),
            StartupFieldName.KEY_FILE_PATH: submission.get_field_value(StartupFieldName.KEY_FILE_PATH),
        }
        self.submission = submission
        self.action_callbacks = StartupDialogActionCallbacks()
        self.submission_changed_callback: Callable[[], None] | None = None
        self.rendered_states = []
        self.error_messages: list[str] = []
        self.status_messages: list[str] = []
        self.clear_error_message_calls = 0
        self.clear_status_message_calls = 0
        self.focus_calls = 0
        self.destroy_called = False
        self.submission_modes: list[StartupDialogMode] = []
        self.clear_sensitive_fields_args: list[bool] = []
        self.set_field_value_calls: list[tuple[StartupFieldName, str]] = []

    def render_state(self, state) -> None:
        self.rendered_states.append(state)
        self.mode_var.set(state.mode.value)
        self.use_remembered_target_var.set(state.uses_remembered_target)
        self.dialect_var.set(state.dialect)
        self.operator_value = state.operator
        self.field_values[StartupFieldName.DATABASE_PATH] = state.database_path
        self.field_values[StartupFieldName.KEY_FILE_PATH] = state.key_file_path

    def get_submission(self) -> StartupDialogSubmission:
        selected_mode = StartupDialogMode(self.mode_var.get())
        self.submission_modes.append(selected_mode)
        return StartupDialogSubmission(
            mode=selected_mode,
            dialect=self.dialect_var.get(),
            operator=self.operator_value,
            uses_remembered_target=self.use_remembered_target_var.get(),
            field_values={
                field_name: self.get_field_value(field_name)
                for field_name in StartupFieldName
            },
        )

    def get_field_value(self, field_name: StartupFieldName) -> str:
        return self.field_values.get(field_name, "")

    def set_field_value(self, field_name: StartupFieldName, value: str) -> None:
        self.set_field_value_calls.append((field_name, value))
        self.field_values[field_name] = value

    def set_action_callbacks(self, callbacks: StartupDialogActionCallbacks) -> None:
        self.action_callbacks = callbacks

    def set_submission_changed_callback(self, callback: Callable[[], None]) -> None:
        self.submission_changed_callback = callback

    def select_mode(self, mode: StartupDialogMode) -> None:
        self.mode_var.set(mode.value)

    def select_dialect(self, dialect: str) -> None:
        self.dialect_var.set(dialect)

    def use_remembered_target(self) -> None:
        self.use_remembered_target_var.set(True)

    def use_manual_target(self) -> None:
        self.use_remembered_target_var.set(False)

    def set_operator(self, operator: str) -> None:
        self.operator_value = operator

    def invoke_submit(self) -> None:
        self._invoke_callback(self.action_callbacks.submit, "submit")

    def invoke_cancel(self) -> None:
        self._invoke_callback(self.action_callbacks.cancel, "cancel")

    def invoke_migrate(self) -> None:
        self._invoke_callback(self.action_callbacks.migrate, "migrate")

    def invoke_browse_database(self) -> None:
        self._invoke_callback(self.action_callbacks.browse_database, "browse_database")

    def invoke_browse_key_file(self) -> None:
        self._invoke_callback(self.action_callbacks.browse_key_file, "browse_key_file")

    def invoke_emergency_reset(self) -> None:
        self._invoke_callback(self.action_callbacks.emergency_reset, "emergency_reset")

    def invoke_submission_changed(self) -> None:
        self._invoke_callback(self.submission_changed_callback, "submission_changed")

    @staticmethod
    def _invoke_callback(callback: Callable[[], None] | None, callback_name: str) -> None:
        assert callback is not None, f"{callback_name} callback was not wired"
        callback()

    def set_error_message(self, message: str) -> None:
        self.error_messages.append(message)

    def clear_error_message(self) -> None:
        self.clear_error_message_calls += 1

    def set_status_message(self, message: str) -> None:
        self.status_messages.append(message)

    def clear_status_message(self) -> None:
        self.clear_status_message_calls += 1

    def clear_sensitive_fields(self, *, clear_password_confirmation: bool = False) -> None:
        self.clear_sensitive_fields_args.append(clear_password_confirmation)
        self.field_values[StartupFieldName.PASSWORD] = ""
        if clear_password_confirmation:
            self.field_values[StartupFieldName.PASSWORD_CONFIRMATION] = ""

    def focus_primary_input(self) -> None:
        self.focus_calls += 1

    def destroy(self) -> None:
        self.destroy_called = True


@dataclass
class ControllerHarness:
    root: FakeRoot
    view: FakeView
    controller: StartupDialogController

    def run(self) -> StartupDialogSuccess | None:
        return self.controller.run(root=self.root)


class FakeStartupDialogRunner:
    def __init__(self, result: StartupDialogSuccess | None) -> None:
        self.result = result
        self.received_root: TkRootProtocol | None = None

    def run(self, *, root: TkRootProtocol) -> StartupDialogSuccess | None:
        self.received_root = root
        return self.result


class FakeMainWindowFactory:
    def __init__(self) -> None:
        self.received_root: object | None = None
        self.received_startup_result: StartupDialogSuccess | None = None
        self.received_app_runtime_state: AppRuntimeState | None = None
        self.received_window_config: MainWindowConfig | None = None
        self.received_template_callback: Callable[[], str | None] | None = None
        self.received_reset_callback: Callable[[], str | None] | None = None
        self.received_close_callback: Callable[[], str | None] | None = None

    def __call__(
        self,
        root,
        startup_result: StartupDialogSuccess,
        *,
        app_runtime_state: AppRuntimeState,
        window_config: MainWindowConfig | None = None,
        template_callback: Callable[[], str | None] | None = None,
        reset_callback: Callable[[], str | None] | None = None,
        close_callback: Callable[[], str | None] | None = None,
    ) -> object:
        self.received_root = root
        self.received_startup_result = startup_result
        self.received_app_runtime_state = app_runtime_state
        self.received_window_config = window_config
        self.received_template_callback = template_callback
        self.received_reset_callback = reset_callback
        self.received_close_callback = close_callback
        return object()


@dataclass(frozen=True)
class FakeEmergencyResetResult:
    success: bool
    follow_up_hints: tuple[ResetFollowUpIssue, ...] = ()
    manual_key_file_cleanup_advisory: bool = False


def _make_submission(
    *,
    mode: StartupDialogMode,
    dialect: str = "sqlite",
    operator: str = "",
    uses_remembered_target: bool = False,
    database_path: str = "eventlog.db",
    password: str = "",
    password_confirmation: str = "",
    key_file_path: str | Path | None = None,
) -> StartupDialogSubmission:
    return StartupDialogSubmission(
        mode=mode,
        dialect=dialect,
        operator=operator,
        uses_remembered_target=uses_remembered_target,
        field_values={
            StartupFieldName.DATABASE_PATH: database_path,
            StartupFieldName.PASSWORD: password,
            StartupFieldName.PASSWORD_CONFIRMATION: password_confirmation,
            StartupFieldName.KEY_FILE_PATH: "" if key_file_path is None else str(key_file_path),
        },
    )


def _field_names(state) -> list[StartupFieldName]:
    return [field.field_name for field in state.backend_fields]


class _DatabasePathDoesNotExist(PathExists):
    def __call__(self, _path: str | PathLike[str]) -> bool:
        return False


class _PathExistsShouldNotBeCalled(PathExists):
    def __call__(self, _path: str | PathLike[str]) -> bool:
        raise AssertionError("controller should not perform startup mode inference")


DATABASE_PATH_DOES_NOT_EXIST: PathExists = _DatabasePathDoesNotExist()
PATH_EXISTS_SHOULD_NOT_BE_CALLED: PathExists = _PathExistsShouldNotBeCalled()


def _make_presenter(
    database_config: DatabaseConfig,
    *,
    bootstrap_result: BootstrapRepositoryResult | None = None,
    migration_result: MigrationResult | None = None,
    database_path_exists: PathExists | None = None,
) -> StartupDialogPresenter:
    if database_path_exists is None:
        resolved_database_path_exists: PathExists = DATABASE_PATH_DOES_NOT_EXIST
    else:
        resolved_database_path_exists = database_path_exists

    def _startup_mode_resolver(
        dialect: str,
        database_path: str,
        fallback_mode: StartupDialogMode,
    ) -> StartupDialogMode:
        return resolve_startup_mode(
            dialect,
            database_path,
            fallback_mode,
            path_exists=resolved_database_path_exists,
        )

    if bootstrap_result is None:
        if migration_result is None:
            return StartupDialogPresenter(
                database_config,
                startup_mode_resolver=_startup_mode_resolver,
            )

        resolved_migration_result: MigrationResult = migration_result

        def _migrate(_request) -> MigrationResult:
            return resolved_migration_result

        return StartupDialogPresenter(
            database_config,
            migration_callback=_migrate,
            startup_mode_resolver=_startup_mode_resolver,
        )

    resolved_bootstrap_result = bootstrap_result

    def _bootstrap(_request) -> BootstrapRepositoryResult:
        return resolved_bootstrap_result

    if migration_result is None:
        return StartupDialogPresenter(
            database_config,
            bootstrap_callback=_bootstrap,
            startup_mode_resolver=_startup_mode_resolver,
        )

    resolved_migration_result: MigrationResult = migration_result

    def _migrate(_request) -> MigrationResult:
        return resolved_migration_result

    return StartupDialogPresenter(
        database_config,
        bootstrap_callback=_bootstrap,
        migration_callback=_migrate,
        startup_mode_resolver=_startup_mode_resolver,
    )
def _make_harness(
    *,
    database_config: DatabaseConfig,
    submission: StartupDialogSubmission,
    bootstrap_result: BootstrapRepositoryResult | None = None,
    migration_result: MigrationResult | None = None,
    database_path_dialog_result: str = "",
    database_path_exists: PathExists | None = None,
    key_file_dialog_result: str = "",
    emergency_reset_callback: EmergencyResetCallback | None = None,
    last_operator_prefill: str = "",
) -> ControllerHarness:
    root = FakeRoot()
    view = FakeView(submission=submission)
    if database_path_exists is None:
        resolved_database_path_exists: PathExists = DATABASE_PATH_DOES_NOT_EXIST
    else:
        resolved_database_path_exists = database_path_exists
    presenter = _make_presenter(
        database_config,
        bootstrap_result=bootstrap_result,
        migration_result=migration_result,
        database_path_exists=resolved_database_path_exists,
    )

    controller = StartupDialogController(
        database_config,
        last_operator_prefill=last_operator_prefill,
        presenter=presenter,
        view_factory=lambda _master: cast(StartupDialogViewProtocol, cast(object, view)),
        database_path_dialog_opener=lambda _parent: database_path_dialog_result,
        database_path_exists=resolved_database_path_exists,
        key_file_dialog_opener=lambda _parent: key_file_dialog_result,
        emergency_reset_callback=emergency_reset_callback,
    )
    return ControllerHarness(root=root, view=view, controller=controller)


class SpyPresenter:
    def __init__(
        self,
        *,
        initial_state: StartupDialogState,
        recomputed_state: StartupDialogState,
    ) -> None:
        self.initial_state = initial_state
        self.recomputed_state = recomputed_state
        self.recompute_calls: list[StartupDialogSubmission] = []
        self.initial_operator_inputs: list[str] = []

    def get_initial_state(self, *, operator: str = "") -> StartupDialogState:
        self.initial_operator_inputs.append(operator)
        return self.initial_state

    def recompute_state(
        self,
        submission: StartupDialogSubmission,
    ) -> StartupDialogState:
        self.recompute_calls.append(submission)
        return self.recomputed_state

    def submit(self, submission: StartupDialogSubmission):
        raise AssertionError(f"submit should not be called in this test: {submission!r}")


def test_run_renders_initial_create_state_and_focuses_primary_input() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
    )

    result = harness.run()

    assert result is None
    assert harness.root.waited_window is harness.view.window
    assert harness.root.withdraw_called is False
    assert harness.root.destroy_called is False
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert harness.view.rendered_states[-1].title == "EventLog - Välj eller skapa databas"
    assert harness.view.clear_error_message_calls == 1
    assert harness.view.focus_calls == 1
    assert harness.view.action_callbacks.submit is not None
    assert harness.view.action_callbacks.cancel is not None
    assert harness.view.action_callbacks.migrate is not None
    assert harness.view.action_callbacks.browse_database is not None
    assert harness.view.action_callbacks.browse_key_file is not None
    assert harness.view.action_callbacks.emergency_reset is None
    assert harness.view.submission_changed_callback is not None


def test_run_prefills_operator_from_bootstrap_config() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        last_operator_prefill="Sgt Example",
    )

    harness.run()

    assert harness.view.rendered_states[-1].operator == "Sgt Example"


def test_run_passes_operator_prefill_into_presenter_owned_initial_state() -> None:
    root = FakeRoot()
    view = FakeView(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="",
            database_path="",
        )
    )
    real_presenter = StartupDialogPresenter(DatabaseConfig())
    spy_presenter = SpyPresenter(
        initial_state=real_presenter.build_state(
            mode=StartupDialogMode.CREATE,
            dialect="",
            operator="Sgt Example",
        ),
        recomputed_state=real_presenter.build_state(mode=StartupDialogMode.CREATE, dialect=""),
    )
    controller = StartupDialogController(
        DatabaseConfig(),
        last_operator_prefill="Sgt Example",
        presenter=cast(StartupDialogPresenter, cast(object, spy_presenter)),
        view_factory=lambda _master: cast(StartupDialogViewProtocol, cast(object, view)),
    )

    controller.run(root=root)

    assert spy_presenter.initial_operator_inputs == ["Sgt Example"]
    assert view.rendered_states[-1].operator == "Sgt Example"


def test_run_with_caller_owned_root_uses_provided_root_without_destroying_it() -> None:
    sentinel_repository = cast(BaseRepository, object())
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(repository=sentinel_repository),
        database_path_exists=lambda path: path == "eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_submit

    result = harness.run()

    assert result is not None
    assert result.repository is sentinel_repository
    assert harness.root.withdraw_called is False
    assert harness.root.destroy_called is False
    assert harness.root.waited_window is harness.view.window
    assert harness.view.destroy_called is True


def test_app_shell_keeps_root_alive_after_successful_startup_until_main_window_runs() -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    root = FakeRoot()
    sentinel_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=database_config.bootstrap_target,
    )
    runner = FakeStartupDialogRunner(sentinel_result)
    main_window_factory = FakeMainWindowFactory()
    captured: dict[str, object] = {}

    def _startup_controller_factory(
        config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> FakeStartupDialogRunner:
        captured["config"] = config
        captured["last_operator_prefill"] = last_operator_prefill
        captured["emergency_reset_callback"] = emergency_reset_callback
        return runner

    shell = AppShell(
        root_factory=lambda: root,
        startup_controller_factory=cast(
            StartupControllerFactory,
            cast(object, _startup_controller_factory),
        ),
        main_window_factory=cast(MainWindowFactory, cast(object, main_window_factory)),
    )
    template_callback = lambda: "Skrev config.ini.template."
    reset_callback = lambda: None
    close_callback = lambda: None
    window_config = MainWindowConfig(window_state="zoomed")
    app_runtime_state = AppRuntimeState(active_operator="Sgt Example")

    result = shell.run_startup_dialog(database_config)
    assert result is sentinel_result

    shell.show_main_window(
        sentinel_result,
        app_runtime_state=app_runtime_state,
        window_config=window_config,
        template_callback=template_callback,
        reset_callback=reset_callback,
        close_callback=close_callback,
    )

    assert captured == {
        "config": database_config,
        "last_operator_prefill": "",
        "emergency_reset_callback": None,
    }
    assert root.withdraw_called is True
    assert root.deiconify_called is True
    assert root.mainloop_called is True
    assert root.destroy_called is True
    assert runner.received_root is root
    assert main_window_factory.received_root is root
    assert main_window_factory.received_startup_result is sentinel_result
    assert main_window_factory.received_app_runtime_state is app_runtime_state
    assert main_window_factory.received_window_config == window_config
    assert main_window_factory.received_template_callback is template_callback
    assert main_window_factory.received_reset_callback is reset_callback
    assert main_window_factory.received_close_callback is close_callback


def test_app_shell_destroys_root_after_cancelled_startup() -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    root = FakeRoot()
    runner = FakeStartupDialogRunner(None)

    def _startup_controller_factory(
        _config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> FakeStartupDialogRunner:
        assert last_operator_prefill == ""
        assert emergency_reset_callback is None
        return runner

    shell = AppShell(
        root_factory=lambda: root,
        startup_controller_factory=cast(
            StartupControllerFactory,
            cast(object, _startup_controller_factory),
        ),
    )

    result = shell.run_startup_dialog(database_config)

    assert result is None
    assert root.withdraw_called is True
    assert root.deiconify_called is False
    assert root.mainloop_called is False
    assert root.destroy_called is True
    assert runner.received_root is root


def test_app_shell_closes_root_and_reraises_when_startup_runner_fails() -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    root = FakeRoot()
    captured: dict[str, object] = {}

    class FailingStartupDialogRunner:
        def run(self, *, root: TkRootProtocol) -> StartupDialogSuccess | None:
            captured["received_root"] = root
            raise RuntimeError("startup runner failed")

    def _startup_controller_factory(
        config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> FailingStartupDialogRunner:
        captured["config"] = config
        captured["last_operator_prefill"] = last_operator_prefill
        captured["emergency_reset_callback"] = emergency_reset_callback
        return FailingStartupDialogRunner()

    shell = AppShell(
        root_factory=lambda: root,
        startup_controller_factory=cast(
            StartupControllerFactory,
            cast(object, _startup_controller_factory),
        ),
    )

    with pytest.raises(RuntimeError, match="startup runner failed"):
        shell.run_startup_dialog(database_config)

    assert captured == {
        "config": database_config,
        "last_operator_prefill": "",
        "emergency_reset_callback": None,
        "received_root": root,
    }
    assert root.withdraw_called is True
    assert root.deiconify_called is False
    assert root.mainloop_called is False
    assert root.destroy_called is True


def test_app_shell_closes_root_and_reraises_when_mainloop_fails() -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    root = FakeRoot()
    sentinel_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=database_config.bootstrap_target,
    )
    runner = FakeStartupDialogRunner(sentinel_result)
    main_window_factory = FakeMainWindowFactory()
    root.on_mainloop = lambda: (_ for _ in ()).throw(RuntimeError("mainloop failed"))

    shell = AppShell(
        root_factory=lambda: root,
        startup_controller_factory=cast(
            StartupControllerFactory,
            cast(
                object,
                lambda _config, *, last_operator_prefill="", emergency_reset_callback=None: runner,
            ),
        ),
        main_window_factory=cast(MainWindowFactory, cast(object, main_window_factory)),
    )

    startup_result = shell.run_startup_dialog(database_config)

    assert startup_result is sentinel_result

    with pytest.raises(RuntimeError, match="mainloop failed"):
        shell.show_main_window(
            sentinel_result,
            app_runtime_state=AppRuntimeState(),
        )

    assert root.withdraw_called is True
    assert root.deiconify_called is True
    assert root.mainloop_called is True
    assert root.destroy_called is True
    assert runner.received_root is root
    assert main_window_factory.received_root is root
    assert main_window_factory.received_startup_result is sentinel_result
    assert isinstance(main_window_factory.received_app_runtime_state, AppRuntimeState)

    with pytest.raises(RuntimeError, match="App shell root is not available"):
        shell.show_main_window(
            sentinel_result,
            app_runtime_state=AppRuntimeState(),
        )


def test_dialect_selection_reveals_backend_fields_after_initial_blank_state() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
    )

    def _select_sqlite() -> None:
        harness.view.set_field_value(StartupFieldName.DATABASE_PATH, "C:/Ops/eventlog.db")
        harness.view.select_dialect("sqlite")
        harness.view.invoke_submission_changed()

    harness.root.on_wait_window = _select_sqlite

    harness.run()

    assert harness.view.rendered_states[0].backend_fields == ()
    assert harness.view.rendered_states[-1].dialect == "sqlite"
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert _field_names(harness.view.rendered_states[-1]) == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.PASSWORD_CONFIRMATION,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert harness.view.clear_error_message_calls == 2
    assert harness.view.focus_calls == 2


def test_dialect_selection_without_target_path_keeps_create_state_target_only() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
    )

    def _select_sqlite_without_path() -> None:
        harness.view.select_dialect("sqlite")
        harness.view.invoke_submission_changed()

    harness.root.on_wait_window = _select_sqlite_without_path

    harness.run()

    assert harness.view.rendered_states[0].backend_fields == ()
    assert harness.view.rendered_states[-1].dialect == "sqlite"
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert harness.view.rendered_states[-1].title == "EventLog - Välj eller skapa databas"
    assert _field_names(harness.view.rendered_states[-1]) == [
        StartupFieldName.DATABASE_PATH,
    ]
    assert harness.view.clear_error_message_calls == 2
    assert harness.view.focus_calls == 2


def test_manual_database_path_entry_reveals_create_password_fields_without_browse_dialog() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
    )

    def _type_database_path_manually() -> None:
        harness.view.set_field_value(StartupFieldName.DATABASE_PATH, "C:/Ops/new-eventlog.db")
        harness.view.invoke_submission_changed()

    harness.root.on_wait_window = _type_database_path_manually

    harness.run()

    assert harness.view.rendered_states[0].dialect == "sqlite"
    assert harness.view.rendered_states[0].mode is StartupDialogMode.CREATE
    assert _field_names(harness.view.rendered_states[0]) == [
        StartupFieldName.DATABASE_PATH,
    ]
    assert harness.view.rendered_states[-1].database_path == "C:/Ops/new-eventlog.db"
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert _field_names(harness.view.rendered_states[-1]) == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.PASSWORD_CONFIRMATION,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert harness.view.clear_error_message_calls == 2
    assert harness.view.focus_calls == 2


def test_run_falls_back_to_create_when_remembered_sqlite_target_no_longer_exists() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/missing.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/missing.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
        database_path_exists=DATABASE_PATH_DOES_NOT_EXIST,
    )

    harness.run()

    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert harness.view.rendered_states[-1].title == "EventLog - Skapa krypterad databas"
    assert harness.view.rendered_states[-1].show_target_source_selector is False
    assert StartupFieldName.PASSWORD_CONFIRMATION in _field_names(harness.view.rendered_states[-1])


def test_unlock_state_hides_emergency_reset_when_no_callback_is_configured() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )

    harness.run()

    assert harness.view.rendered_states[-1].mode is StartupDialogMode.UNLOCK
    assert harness.view.rendered_states[-1].allow_emergency_reset is False


def test_target_source_change_switches_unlock_view_to_manual_target_fields() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )

    def _switch_to_manual_target() -> None:
        harness.view.use_manual_target()
        harness.view.invoke_submission_changed()

    harness.root.on_wait_window = _switch_to_manual_target

    harness.run()

    assert harness.view.rendered_states[0].uses_remembered_target is True
    assert harness.view.rendered_states[-1].uses_remembered_target is False
    assert harness.view.rendered_states[-1].title == "EventLog - Öppna befintlig databas"
    assert harness.view.rendered_states[-1].show_dialect_picker is True
    assert _field_names(harness.view.rendered_states[-1]) == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert harness.view.rendered_states[-1].backend_fields[-1].required is False


def test_existing_database_selection_does_not_reuse_create_key_file_policy() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(require_key_file_for_creation=True),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
        database_path_dialog_result="C:/Ops/existing-eventlog.db",
        database_path_exists=lambda path: path == "C:/Ops/existing-eventlog.db",
    )

    def _select_existing_database() -> None:
        harness.view.select_dialect("sqlite")
        harness.view.invoke_browse_database()

    harness.root.on_wait_window = _select_existing_database

    harness.run()

    assert harness.view.rendered_states[-1].mode is StartupDialogMode.UNLOCK
    assert _field_names(harness.view.rendered_states[-1]) == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert harness.view.rendered_states[-1].backend_fields[-1].required is False


def test_new_database_selection_uses_create_policy_not_remembered_unlock_hint() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
            require_key_file=True,
            require_key_file_for_creation=False,
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_dialog_result="C:/Ops/new-eventlog.db",
        database_path_exists=lambda path: path == "eventlog.db",
    )

    def _select_new_database() -> None:
        harness.view.invoke_browse_database()

    harness.root.on_wait_window = _select_new_database

    harness.run()

    assert harness.view.rendered_states[0].backend_fields[-1].required is True
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert StartupFieldName.KEY_FILE_PATH in _field_names(harness.view.rendered_states[-1])
    assert harness.view.rendered_states[-1].backend_fields[-1].required is False


def test_submit_failure_shows_error_and_clears_passwords_when_presenter_requests_retry_cleanup() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.INVALID_CREDENTIALS,
                "Fel lösenord eller fel nyckelfil.",
            )
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_submit

    result = harness.run()

    assert result is None
    assert harness.view.submission_modes == [StartupDialogMode.UNLOCK]
    assert harness.view.error_messages == ["Fel lösenord eller fel nyckelfil."]
    assert harness.view.clear_sensitive_fields_args == [False]
    assert harness.view.focus_calls == 2
    assert harness.view.destroy_called is False


def test_submit_failure_shows_presenter_owned_migration_guidance_instead_of_backend_detail() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_NEEDED,
                "technical backend detail",
                retryable=False,
            )
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_submit

    result = harness.run()

    assert result is None
    assert harness.view.error_messages == [
        "Databasen behöver migreras innan den kan öppnas. Kör databasmigrering för databasen först."
    ]
    assert harness.view.clear_sensitive_fields_args == []
    assert harness.view.destroy_called is False


def test_submit_failure_with_migration_needed_exposes_dedicated_migrate_action() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_NEEDED,
                "technical backend detail",
                retryable=False,
            )
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_submit

    result = harness.run()

    assert result is None
    assert harness.view.rendered_states[-1].show_migration_action is True
    assert harness.view.rendered_states[-1].submit_enabled is True
    assert harness.view.rendered_states[-1].migration_action_enabled is True
    assert harness.view.destroy_called is False


def test_migrate_action_runs_presenter_migration_and_shows_success_status() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_NEEDED,
                "technical backend detail",
                retryable=False,
            )
        ),
        migration_result=MigrationResult(
            migration_performed=True,
            message="Databasmigreringen slutfördes.",
        ),
        database_path_exists=lambda path: path == "eventlog.db",
    )

    def _submit_then_migrate() -> None:
        harness.view.invoke_submit()
        harness.view.invoke_migrate()

    harness.root.on_wait_window = _submit_then_migrate

    result = harness.run()

    assert result is None
    assert harness.view.status_messages == ["Databasmigreringen slutfördes."]
    assert harness.view.rendered_states[-1].show_migration_action is False
    assert harness.view.rendered_states[-1].submit_enabled is True
    assert harness.view.destroy_called is False


def test_submit_success_closes_dialog_and_returns_startup_success() -> None:
    sentinel_repository = cast(BaseRepository, object())
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        bootstrap_result=BootstrapRepositoryResult(repository=sentinel_repository),
        database_path_exists=lambda path: path == "eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_submit

    result = harness.run()

    assert result is not None
    assert result.repository is sentinel_repository
    assert result.remembered_target.dialect == "sqlite"
    assert result.remembered_target.database_path == "eventlog.db"
    assert harness.view.destroy_called is True


def test_cancel_closes_dialog_without_result() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
    )
    harness.root.on_wait_window = harness.view.invoke_cancel

    result = harness.run()

    assert result is None
    assert harness.view.destroy_called is True


def test_emergency_reset_success_closes_dialog_after_clearing_sensitive_fields() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_exists=lambda path: path == "eventlog.db",
        emergency_reset_callback=lambda: FakeEmergencyResetResult(success=True),
    )
    harness.root.on_wait_window = harness.view.invoke_emergency_reset

    result = harness.run()

    assert result is None
    assert harness.view.clear_sensitive_fields_args == [True]
    assert harness.view.error_messages == []
    assert harness.view.destroy_called is True


def test_emergency_reset_failure_shows_sanitized_follow_up_message_and_keeps_dialog_open() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_exists=lambda path: path == "eventlog.db",
        emergency_reset_callback=lambda: FakeEmergencyResetResult(
            success=False,
            follow_up_hints=(
                ResetFollowUpIssue.LOG_ARTIFACTS,
                ResetFollowUpIssue.BOOTSTRAP_RESET,
                ResetFollowUpIssue.LOG_ARTIFACTS,
            ),
        ),
    )
    harness.root.on_wait_window = harness.view.invoke_emergency_reset

    result = harness.run()

    assert result is None
    assert harness.view.clear_sensitive_fields_args == [True]
    assert harness.view.error_messages == [
        "MISSLYCKADES\nFölj upp manuellt: loggar, startupminne.",
    ]
    assert harness.view.destroy_called is False


def test_emergency_reset_failure_can_append_manual_key_file_advisory() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_exists=lambda path: path == "eventlog.db",
        emergency_reset_callback=lambda: FakeEmergencyResetResult(
            success=False,
            follow_up_hints=(ResetFollowUpIssue.LOG_ARTIFACTS,),
            manual_key_file_cleanup_advisory=True,
        ),
    )
    harness.root.on_wait_window = harness.view.invoke_emergency_reset

    result = harness.run()

    assert result is None
    assert harness.view.error_messages == [
        "MISSLYCKADES\nFölj upp manuellt: loggar.\nEventuella nyckelfiler behöver tas bort manuellt.",
    ]
    assert harness.view.destroy_called is False


def test_emergency_reset_success_does_not_show_manual_key_file_advisory_in_first_slice() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_exists=lambda path: path == "eventlog.db",
        emergency_reset_callback=lambda: FakeEmergencyResetResult(
            success=True,
            manual_key_file_cleanup_advisory=True,
        ),
    )
    harness.root.on_wait_window = harness.view.invoke_emergency_reset

    result = harness.run()

    assert result is None
    assert harness.view.error_messages == []
    assert harness.view.destroy_called is True


def test_browse_key_file_rerenders_presenter_owned_path_when_file_is_selected() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            operator="Sgt Example",
            database_path="eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
        key_file_dialog_result="C:/keys/startup.key",
    )
    def _set_operator_and_browse_key_file() -> None:
        harness.view.set_operator("Sgt Example")
        harness.view.set_field_value(StartupFieldName.DATABASE_PATH, "eventlog.db")
        harness.view.invoke_browse_key_file()

    harness.root.on_wait_window = _set_operator_and_browse_key_file

    harness.run()

    assert (
        StartupFieldName.KEY_FILE_PATH,
        "C:/keys/startup.key",
    ) not in harness.view.set_field_value_calls
    assert harness.view.rendered_states[-1].operator == "Sgt Example"
    assert harness.view.rendered_states[-1].database_path == "eventlog.db"
    assert harness.view.rendered_states[-1].key_file_path == "C:/keys/startup.key"
    assert harness.view.get_field_value(StartupFieldName.KEY_FILE_PATH) == "C:/keys/startup.key"


def test_open_database_path_dialog_suppresses_overwrite_confirmation_for_existing_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_asksaveasfilename(**kwargs: object) -> str:
        captured.update(kwargs)
        return "C:/Ops/eventlog.db"

    monkeypatch.setattr("src.gui.startup_dialog_controller.filedialog.asksaveasfilename", fake_asksaveasfilename)

    parent = cast(tk.Misc, object())
    selected_path = open_database_path_dialog(parent)

    assert selected_path == "C:/Ops/eventlog.db"
    assert captured == {
        "parent": parent,
        "title": "Välj eller ange databassökväg",
        "defaultextension": ".db",
        "filetypes": (("Databasfiler", "*.db"), ("Alla filer", "*.*")),
        "confirmoverwrite": False,
    }


def test_browse_database_switches_to_unlock_when_selected_database_exists() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        ),
        database_path_dialog_result="C:/Ops/eventlog.db",
        database_path_exists=lambda path: path == "C:/Ops/eventlog.db",
    )

    def _select_sqlite_and_browse_database() -> None:
        harness.view.select_dialect("sqlite")
        harness.view.invoke_browse_database()

    harness.root.on_wait_window = _select_sqlite_and_browse_database

    harness.run()

    assert harness.view.get_field_value(StartupFieldName.DATABASE_PATH) == "C:/Ops/eventlog.db"
    assert (
        StartupFieldName.DATABASE_PATH,
        "C:/Ops/eventlog.db",
    ) not in harness.view.set_field_value_calls
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.UNLOCK
    assert harness.view.rendered_states[-1].title == "EventLog - Öppna befintlig databas"
    assert StartupFieldName.PASSWORD_CONFIRMATION not in _field_names(harness.view.rendered_states[-1])
    assert harness.view.clear_error_message_calls == 2
    assert harness.view.focus_calls == 2


def test_browse_database_switches_to_create_when_selected_database_does_not_exist() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(
            dialect="sqlite",
            database_path="eventlog.db",
        ),
        submission=_make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            uses_remembered_target=True,
        ),
        database_path_dialog_result="C:/Ops/new-eventlog.db",
    )
    harness.root.on_wait_window = harness.view.invoke_browse_database

    harness.run()

    assert harness.view.get_field_value(StartupFieldName.DATABASE_PATH) == "C:/Ops/new-eventlog.db"
    assert (
        StartupFieldName.DATABASE_PATH,
        "C:/Ops/new-eventlog.db",
    ) not in harness.view.set_field_value_calls
    assert harness.view.rendered_states[-1].mode is StartupDialogMode.CREATE
    assert harness.view.rendered_states[-1].title == "EventLog - Skapa krypterad databas"
    assert StartupFieldName.PASSWORD_CONFIRMATION in _field_names(harness.view.rendered_states[-1])


def test_database_path_rerender_preserves_other_visible_backend_field_values() -> None:
    harness = _make_harness(
        database_config=DatabaseConfig(),
        submission=_make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            operator="Sgt Example",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
            key_file_path="C:/keys/startup.key",
        ),
        database_path_dialog_result="C:/Ops/eventlog.db",
        database_path_exists=lambda path: path == "C:/Ops/eventlog.db",
    )

    def _select_sqlite_and_browse_database() -> None:
        harness.view.select_dialect("sqlite")
        harness.view.set_operator("Sgt Example")
        harness.view.set_field_value(StartupFieldName.PASSWORD, "lösenord123")
        harness.view.set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "lösenord123")
        harness.view.set_field_value(StartupFieldName.KEY_FILE_PATH, "C:/keys/startup.key")
        harness.view.invoke_browse_database()

    harness.root.on_wait_window = _select_sqlite_and_browse_database

    harness.run()

    assert harness.view.rendered_states[-1].mode is StartupDialogMode.UNLOCK
    assert (
        StartupFieldName.DATABASE_PATH,
        "C:/Ops/eventlog.db",
    ) not in harness.view.set_field_value_calls
    assert harness.view.rendered_states[-1].operator == "Sgt Example"
    assert harness.view.get_field_value(StartupFieldName.PASSWORD) == "lösenord123"
    assert harness.view.get_field_value(StartupFieldName.KEY_FILE_PATH) == "C:/keys/startup.key"


def test_dialect_change_delegates_state_recomputation_to_presenter_instead_of_controller_inference() -> None:
    root = FakeRoot()
    view = FakeView(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="",
            database_path="",
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )
    real_presenter = StartupDialogPresenter(DatabaseConfig())
    spy_presenter = SpyPresenter(
        initial_state=real_presenter.build_state(mode=StartupDialogMode.CREATE, dialect=""),
        recomputed_state=real_presenter.build_state(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
            use_remembered_target=False,
        ),
    )

    controller = StartupDialogController(
        DatabaseConfig(),
        presenter=cast(StartupDialogPresenter, cast(object, spy_presenter)),
        view_factory=lambda _master: cast(StartupDialogViewProtocol, cast(object, view)),
        database_path_exists=PATH_EXISTS_SHOULD_NOT_BE_CALLED,
    )

    def _change_dialect() -> None:
        view.select_dialect("sqlite")
        view.set_field_value(StartupFieldName.DATABASE_PATH, "C:/Ops/eventlog.db")
        view.invoke_submission_changed()

    root.on_wait_window = _change_dialect

    controller.run(root=root)

    assert spy_presenter.recompute_calls == [
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    ]
    assert view.rendered_states[-1].mode is StartupDialogMode.UNLOCK
    assert [field.field_name for field in view.rendered_states[-1].backend_fields] == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert view.rendered_states[-1].backend_fields == (
        StartupFieldRequirement(
            field_name=StartupFieldName.DATABASE_PATH,
            kind=StartupFieldKind.FILE_PATH,
            required=True,
            editable=True,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
            required=False,
            editable=True,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.KEY_FILE_PATH,
            kind=StartupFieldKind.FILE_PATH,
            required=False,
            editable=True,
        ),
    )


def test_mode_change_reads_selected_mode_from_view_submission_and_rerenders() -> None:
    root = FakeRoot()
    view = FakeView(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
            password="lösenord123",
        )
    )
    real_presenter = StartupDialogPresenter(DatabaseConfig())
    spy_presenter = SpyPresenter(
        initial_state=real_presenter.build_state(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ),
        recomputed_state=real_presenter.build_state(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
            use_remembered_target=False,
        ),
    )
    controller = StartupDialogController(
        DatabaseConfig(),
        presenter=cast(StartupDialogPresenter, cast(object, spy_presenter)),
        view_factory=lambda _master: cast(StartupDialogViewProtocol, cast(object, view)),
    )

    def _change_mode() -> None:
        view.select_mode(StartupDialogMode.UNLOCK)
        view.invoke_submission_changed()

    root.on_wait_window = _change_mode

    controller.run(root=root)

    assert spy_presenter.recompute_calls == [
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
            password="lösenord123",
        )
    ]
    assert view.rendered_states[-1].mode is StartupDialogMode.UNLOCK


def test_resolve_database_config_returns_defaults_when_config_file_has_no_bootstrap_section(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_database_config", lambda _path: None)

    resolved = app_module.resolve_database_config()

    assert resolved == DatabaseConfig()


def test_resolve_database_config_normalizes_relative_sqlite_target_via_runtime_resolver(
    tmp_path,
) -> None:
    config_directory = tmp_path / "instance"
    config_directory.mkdir()
    config_path = config_directory / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = data/eventlog.db
        """.strip(),
        encoding="utf-8",
    )

    resolved = app_module.resolve_database_config(config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_directory / "data" / "eventlog.db").resolve()),
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_run_active_context_reset_uses_startup_result_invalidator_before_cleanup() -> None:
    phase_order: list[str] = []

    def backend_cleanup() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.UNSUPPORTED,
            cleanup_performed=False,
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: phase_order.append("deny"),
        backend_cleanup=backend_cleanup,
    )

    outcome = app_module.run_active_context_reset(startup_result)

    assert phase_order == ["deny", "cleanup"]
    assert outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )


def test_run_active_context_close_uses_startup_result_invalidator_without_backend_cleanup() -> None:
    phase_order: list[str] = []

    def _backend_cleanup_not_expected() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=True,
        )

    def _invalidate_access() -> None:
        phase_order.append("deny")

    remembered_target = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    ).bootstrap_target

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=remembered_target,
        invalidate_access=_invalidate_access,
        backend_cleanup=cast(BackendCleanup, _backend_cleanup_not_expected),
    )

    outcome = app_module.run_active_context_close(startup_result)

    assert phase_order == ["deny"]
    assert outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=True,
        cleanup_started=False,
        cleanup_completed=False,
    )


def test_run_active_context_reset_returns_safe_outcome_without_active_startup_result() -> None:
    cleanup_called = False

    def cleanup() -> None:
        nonlocal cleanup_called
        cleanup_called = True

    outcome = app_module.run_active_context_reset(None, cleanup=cleanup)

    assert cleanup_called is False
    assert outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=False,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
    )


def test_run_active_context_reset_reports_missing_invalidator_on_active_context() -> None:
    cleanup_called = False

    def backend_cleanup() -> BackendCleanupOutcome:
        nonlocal cleanup_called
        cleanup_called = True
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.UNSUPPORTED,
            cleanup_performed=False,
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=None,
        backend_cleanup=backend_cleanup,
    )

    outcome = app_module.run_active_context_reset(startup_result)

    assert cleanup_called is False
    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=False,
            cleanup_started=False,
            cleanup_completed=False,
            failure_categories=(ResetFailureCategory.ACCESS_DENIAL,),
        ),
        manual_key_file_cleanup_advisory=True,
    )


def test_run_active_context_reset_clears_remembered_bootstrap_selectors_after_successful_reset(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = true
min_password_length = 12
secure_delete_passes = 5
kdf_iterations = 250000

[sqlite]
database_path = old-eventlog.db
require_key_file = true

[Logging]
log_level = INFO

[Application]
language = sv
        """.strip(),
        encoding="utf-8",
    )
    phase_order: list[str] = []

    def backend_cleanup() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.UNSUPPORTED,
            cleanup_performed=False,
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: phase_order.append("deny"),
        backend_cleanup=backend_cleanup,
    )

    outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)
    parser = load_app_config(config_path)

    assert phase_order == ["deny", "cleanup"]
    assert outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False
    assert parser.has_option("sqlite", "require_key_file") is False
    assert parser.get(parser.default_section, "require_key_file_for_creation") == "true"
    assert parser.get(parser.default_section, "min_password_length") == "12"
    assert parser.get(parser.default_section, "secure_delete_passes") == "5"
    assert parser.get(parser.default_section, "kdf_iterations") == "250000"
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.get("Application", "language") == "sv"


def test_run_active_context_reset_deletes_runtime_known_log_artifacts_and_is_rerun_safe(
    tmp_path,
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
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db

[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 2
        """.strip(),
        encoding="utf-8",
    )
    phase_order: list[str] = []

    def backend_cleanup() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.UNSUPPORTED,
            cleanup_performed=False,
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: phase_order.append("deny"),
        backend_cleanup=backend_cleanup,
    )

    first_outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)
    second_outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)

    assert phase_order == ["deny", "cleanup", "deny", "cleanup"]
    assert first_outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )
    assert second_outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )
    assert current_log.exists() is False
    assert rotated_first.exists() is False


def test_run_active_context_reset_relies_on_backend_owned_cleanup_for_key_file_artifacts_and_is_rerun_safe(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db
        """.strip(),
        encoding="utf-8",
    )
    key_file_path = tmp_path / "active.key"
    key_file_path.write_text("secret", encoding="utf-8")
    phase_order: list[str] = []

    def backend_cleanup() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        key_file_path.unlink(missing_ok=True)
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=True,
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: phase_order.append("deny"),
        backend_cleanup=backend_cleanup,
    )

    first_outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)
    second_outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)

    assert phase_order == ["deny", "cleanup", "deny", "cleanup"]
    assert first_outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )
    assert second_outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
    )
    assert key_file_path.exists() is False


def test_run_active_context_reset_reports_cleanup_failure_when_backend_owned_cleanup_raises(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db
        """.strip(),
        encoding="utf-8",
    )
    phase_order: list[str] = []

    def backend_cleanup() -> BackendCleanupOutcome:
        phase_order.append("cleanup")
        raise RuntimeError("do not leak specific artifact path details")

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: phase_order.append("deny"),
        backend_cleanup=backend_cleanup,
    )

    outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)

    assert phase_order == ["deny", "cleanup"]
    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=False,
            failure_categories=(ResetFailureCategory.CLEANUP,),
        ),
        follow_up_hints=(app_module.ResetFollowUpHint.DATABASE_ARTIFACTS,),
        manual_key_file_cleanup_advisory=True,
    )


def test_run_active_context_reset_treats_external_key_file_cleanup_as_out_of_scope() -> None:
    def backend_cleanup() -> BackendCleanupOutcome:
        raise BackendCleanupError(
            "Backend cleanup could not remove one or more backend-owned active artifacts.",
            outcome=BackendCleanupOutcome(
                status=BackendCleanupStatus.PARTIAL,
                cleanup_performed=True,
                report=BackendCleanupReport(
                    access_release_performed=False,
                    artifacts_enumerated=1,
                    artifacts_removed=0,
                    artifacts_failed=1,
                    failed_concerns=(),
                    failed_artifact_kinds=("key_file",),
                ),
            ),
        )

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: None,
        backend_cleanup=backend_cleanup,
    )

    outcome = app_module.run_active_context_reset(startup_result)

    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=False,
            failure_categories=(ResetFailureCategory.CLEANUP,),
        ),
        follow_up_hints=(),
        manual_key_file_cleanup_advisory=True,
    )


def test_run_active_context_reset_surfaces_log_follow_up_hint_when_log_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    log_path = tmp_path / "eventlog.log"
    log_path.write_text("current", encoding="utf-8")
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db

[Logging]
file_logging_enabled = true
log_file_path = eventlog.log
log_file_backup_count = 0
        """.strip(),
        encoding="utf-8",
    )

    original_unlink = app_module.Path.unlink

    def fake_unlink(self, *, missing_ok: bool = False) -> None:
        if self == log_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    monkeypatch.setattr(app_module.Path, "unlink", fake_unlink)

    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: None,
        backend_cleanup=lambda: BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=True,
        ),
    )

    outcome = app_module.run_active_context_reset(startup_result, config_path=config_path)

    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=False,
            failure_categories=(ResetFailureCategory.CLEANUP,),
        ),
        follow_up_hints=(app_module.ResetFollowUpHint.LOG_ARTIFACTS,),
        manual_key_file_cleanup_advisory=True,
    )
    assert log_path.exists() is True


def test_run_active_context_reset_surfaces_bootstrap_reset_follow_up_hint_when_selector_clear_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    startup_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=DatabaseConfig(
            dialect="sqlite",
            database_path="C:/Ops/eventlog.db",
        ).bootstrap_target,
        invalidate_access=lambda: None,
        backend_cleanup=lambda: BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=True,
        ),
    )

    monkeypatch.setattr(
        app_module,
        "save_bootstrap_target_config",
        lambda _config_path, _target: (_ for _ in ()).throw(OSError("locked")),
    )

    outcome = app_module.run_active_context_reset(startup_result)

    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=True,
            cleanup_completed=True,
        ),
        follow_up_hints=(app_module.ResetFollowUpHint.BOOTSTRAP_RESET,),
        manual_key_file_cleanup_advisory=True,
    )


def test_run_startup_bootstrap_reset_deletes_remembered_database_artifacts_without_reporting_external_key_files(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_path = logs_dir / "eventlog.log"
    database_path = tmp_path / "remembered.db"
    wal_path = Path(f"{database_path}-wal")
    log_path.write_text("current", encoding="utf-8")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = true

[sqlite]
database_path = old-eventlog.db
require_key_file = true

[Logging]
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_backup_count = 0
        """.strip(),
        encoding="utf-8",
    )

    outcome = app_module.run_startup_bootstrap_reset(
        DatabaseConfig(
            dialect="sqlite",
            database_path=str(database_path),
            require_key_file=True,
        ),
        config_path=config_path,
    )
    parser = load_app_config(config_path)

    assert outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=False,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
    )
    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.has_option("sqlite", "database_path") is False
    assert parser.has_option("sqlite", "require_key_file") is False
    assert parser.get(parser.default_section, "require_key_file_for_creation") == "true"
    assert database_path.exists() is False
    assert wal_path.exists() is False
    assert log_path.exists() is False


def test_run_startup_bootstrap_reset_returns_success_when_remembered_database_cleanup_and_bootstrap_clear_finish(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    database_path = tmp_path / "remembered.db"
    database_path.write_text("db", encoding="utf-8")
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = remembered.db
        """.strip(),
        encoding="utf-8",
    )

    outcome = app_module.run_startup_bootstrap_reset(
        DatabaseConfig(
            dialect="sqlite",
            database_path=str(database_path),
            require_key_file=False,
        ),
        config_path=config_path,
    )

    assert outcome == app_module.ActiveContextResetResult(
        success=True,
        shared_outcome=ResetOutcome(
            had_active_context=False,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
    )
    assert database_path.exists() is False


def test_run_startup_bootstrap_reset_reports_log_and_bootstrap_follow_up_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "config.ini"
    log_path = tmp_path / "eventlog.log"
    database_path = tmp_path / "remembered.db"
    log_path.write_text("current", encoding="utf-8")
    database_path.write_text("db", encoding="utf-8")
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db

[Logging]
file_logging_enabled = true
log_file_path = eventlog.log
log_file_backup_count = 0
        """.strip(),
        encoding="utf-8",
    )

    original_unlink = app_module.Path.unlink

    def fake_unlink(self, *, missing_ok: bool = False) -> None:
        if self == log_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    monkeypatch.setattr(app_module.Path, "unlink", fake_unlink)
    monkeypatch.setattr(
        app_module,
        "save_bootstrap_target_config",
        lambda _config_path, _target: (_ for _ in ()).throw(OSError("locked")),
    )

    outcome = app_module.run_startup_bootstrap_reset(
        DatabaseConfig(
            dialect="sqlite",
            database_path=str(database_path),
        ),
        config_path=config_path,
    )

    assert outcome == app_module.ActiveContextResetResult(
        success=False,
        shared_outcome=ResetOutcome(
            had_active_context=False,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
        follow_up_hints=(
            app_module.ResetFollowUpHint.LOG_ARTIFACTS,
            app_module.ResetFollowUpHint.BOOTSTRAP_RESET,
        ),
        manual_key_file_cleanup_advisory=True,
    )
    assert database_path.exists() is False
    assert log_path.exists() is True


def test_run_app_loads_config_and_shows_main_window_after_successful_startup(monkeypatch) -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
    )
    bootstrap_ui_config = BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="zoomed",
            window_width=1440,
            window_height=900,
            window_x=20,
            window_y=30,
        ),
        language="sv",
        last_operator="Sgt Example",
    )
    runtime_database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    sentinel_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=runtime_database_config.bootstrap_target,
    )
    captured: dict[str, object] = {}
    persisted_target: dict[str, object] = {}
    persisted_ui: dict[str, object] = {}
    persisted_template: dict[str, object] = {}
    shell_close_calls: list[str] = []
    reset_calls: list[tuple[StartupDialogSuccess, object]] = []
    close_calls: list[StartupDialogSuccess] = []

    class FakeAppShell:
        def __init__(self) -> None:
            captured["shell"] = self

        def run_startup_dialog(
            self,
            config: DatabaseConfig,
            *,
            last_operator_prefill="",
            emergency_reset_callback=None,
        ):
            captured["config"] = config
            captured["last_operator_prefill"] = last_operator_prefill
            captured["emergency_reset_callback"] = emergency_reset_callback
            captured["run_called"] = True
            return sentinel_result

        def show_main_window(
            self,
            startup_result: StartupDialogSuccess,
            *,
            app_runtime_state: AppRuntimeState,
            window_config=None,
            template_callback=None,
            reset_callback=None,
            close_callback=None,
        ) -> None:
            captured["show_main_window_called"] = True
            captured["main_window_startup_result"] = startup_result
            captured["app_runtime_state"] = app_runtime_state
            captured["window_config"] = window_config
            captured["template_callback"] = template_callback
            captured["reset_callback"] = reset_callback
            captured["close_callback"] = close_callback

        def close(self) -> None:
            shell_close_calls.append("close")

        def snapshot_main_window_config(self):
            return MainWindowConfig(
                window_state="zoomed",
                window_width=1600,
                window_height=900,
                window_x=0,
                window_y=0,
            )

    monkeypatch.setattr(app_module, "load_database_config", lambda _path: database_config)
    monkeypatch.setattr(
        app_module,
        "resolve_bootstrap_ui_settings",
        lambda _path: bootstrap_ui_config,
    )
    monkeypatch.setattr(
        app_module,
        "resolve_runtime_database_config",
        lambda loaded_config, *, config_path: runtime_database_config,
    )
    monkeypatch.setattr(app_module, "AppShell", FakeAppShell)
    monkeypatch.setattr(
        app_module,
        "run_active_context_reset",
        lambda startup_result, *, config_path=None: reset_calls.append((startup_result, config_path))
        or app_module.ActiveContextResetResult(
            success=True,
            shared_outcome=ResetOutcome(
                had_active_context=True,
                denial_succeeded=True,
                cleanup_started=True,
                cleanup_completed=True,
            ),
        ),
    )
    monkeypatch.setattr(
        app_module,
        "run_active_context_close",
        lambda startup_result: close_calls.append(startup_result)
        or ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "save_bootstrap_target_config",
        lambda config_path, target: persisted_target.update(
            {
                "config_path": config_path,
                "target": target,
            }
        ),
    )
    monkeypatch.setattr(
        app_module,
        "save_bootstrap_ui_config",
        lambda config_path, config: persisted_ui.update(
            {
                "config_path": config_path,
                "config": config,
            }
        ),
    )
    monkeypatch.setattr(
        app_module,
        "write_config_template",
        lambda template_path: persisted_template.update({"template_path": Path(template_path)})
        or Path(template_path),
    )

    result = app_module.run_app()
    template_callback = cast(Callable[[], str | None], captured["template_callback"])
    reset_callback = cast(Callable[[], str | None], captured["reset_callback"])
    close_callback = cast(Callable[[], str | None], captured["close_callback"])
    app_runtime_state = cast(AppRuntimeState, captured["app_runtime_state"])

    assert captured == {
        "shell": captured["shell"],
        "config": runtime_database_config,
        "last_operator_prefill": "Sgt Example",
        "emergency_reset_callback": captured["emergency_reset_callback"],
        "run_called": True,
        "show_main_window_called": True,
        "main_window_startup_result": sentinel_result,
        "app_runtime_state": app_runtime_state,
        "window_config": bootstrap_ui_config.main_window,
        "template_callback": captured["template_callback"],
        "reset_callback": captured["reset_callback"],
        "close_callback": captured["close_callback"],
    }
    assert callable(captured["emergency_reset_callback"])
    assert callable(template_callback)
    assert callable(reset_callback)
    assert callable(close_callback)
    assert app_runtime_state.active_operator == ""
    assert persisted_target == {
        "config_path": app_module.DEFAULT_CONFIG_PATH,
        "target": runtime_database_config.bootstrap_target,
    }
    assert template_callback() == "Skrev config.ini.template."
    assert persisted_template == {
        "template_path": app_module.DEFAULT_CONFIG_PATH.with_name("config.ini.template"),
    }
    assert reset_callback() is None
    app_runtime_state.active_operator = "Captain Runtime"
    assert close_callback() is None
    assert persisted_ui == {
        "config_path": app_module.DEFAULT_CONFIG_PATH,
        "config": BootstrapUiConfig(
            main_window=MainWindowConfig(
                window_state="zoomed",
                window_width=1600,
                window_height=900,
                window_x=0,
                window_y=0,
            ),
            language="sv",
            last_operator="Captain Runtime",
        ),
    }
    assert reset_calls == [(sentinel_result, app_module.DEFAULT_CONFIG_PATH)]
    assert close_calls == [sentinel_result]
    assert shell_close_calls == ["close", "close"]
    assert result is sentinel_result


def test_run_app_does_not_persist_remembered_target_when_startup_is_cancelled(monkeypatch) -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
    )
    bootstrap_ui_config = BootstrapUiConfig(last_operator="Sgt Example")
    runtime_database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    persisted: list[tuple[object, object]] = []

    class FakeAppShell:
        def run_startup_dialog(
            self,
            config: DatabaseConfig,
            *,
            last_operator_prefill="",
            emergency_reset_callback=None,
        ):
            assert config == runtime_database_config
            assert last_operator_prefill == "Sgt Example"
            assert callable(emergency_reset_callback)
            return None

        def show_main_window(
            self,
            startup_result: StartupDialogSuccess,
            *,
            app_runtime_state: AppRuntimeState,
            window_config=None,
            template_callback=None,
            reset_callback=None,
            close_callback=None,
        ) -> None:
            raise AssertionError(f"show_main_window should not be called: {startup_result!r}")

        def close(self) -> None:
            raise AssertionError("close should not be called for cancelled startup")

    monkeypatch.setattr(app_module, "load_database_config", lambda _path: database_config)
    monkeypatch.setattr(
        app_module,
        "resolve_bootstrap_ui_settings",
        lambda _path: bootstrap_ui_config,
    )
    monkeypatch.setattr(
        app_module,
        "resolve_runtime_database_config",
        lambda loaded_config, *, config_path: runtime_database_config,
    )
    monkeypatch.setattr(app_module, "AppShell", FakeAppShell)
    monkeypatch.setattr(
        app_module,
        "save_bootstrap_target_config",
        lambda config_path, target: persisted.append((config_path, target)),
    )

    result = app_module.run_app()

    assert result is None
    assert persisted == []


def test_run_app_closes_shell_and_reraises_when_persisting_remembered_target_fails(monkeypatch) -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
    )
    bootstrap_ui_config = BootstrapUiConfig(last_operator="Sgt Example")
    runtime_database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="C:/Ops/eventlog.db",
    )
    sentinel_result = app_module.StartupDialogSuccess(
        repository=object(),
        remembered_target=runtime_database_config.bootstrap_target,
    )
    captured: dict[str, object] = {}
    shell_close_calls: list[str] = []

    class FakeAppShell:
        def __init__(self) -> None:
            captured["shell"] = self

        def run_startup_dialog(
            self,
            config: DatabaseConfig,
            *,
            last_operator_prefill="",
            emergency_reset_callback=None,
        ):
            captured["config"] = config
            captured["last_operator_prefill"] = last_operator_prefill
            captured["emergency_reset_callback"] = emergency_reset_callback
            captured["run_called"] = True
            return sentinel_result

        def show_main_window(
            self,
            startup_result: StartupDialogSuccess,
            *,
            app_runtime_state: AppRuntimeState,
            window_config=None,
            template_callback=None,
            reset_callback=None,
            close_callback=None,
        ) -> None:
            raise AssertionError(f"show_main_window should not be called: {startup_result!r}")

        def close(self) -> None:
            shell_close_calls.append("close")

    monkeypatch.setattr(app_module, "load_database_config", lambda _path: database_config)
    monkeypatch.setattr(
        app_module,
        "resolve_bootstrap_ui_settings",
        lambda _path: bootstrap_ui_config,
    )
    monkeypatch.setattr(
        app_module,
        "resolve_runtime_database_config",
        lambda loaded_config, *, config_path: runtime_database_config,
    )
    monkeypatch.setattr(app_module, "AppShell", FakeAppShell)

    def _failing_save(config_path, target) -> None:
        captured["persist_config_path"] = config_path
        captured["persist_target"] = target
        raise OSError("locked")

    monkeypatch.setattr(app_module, "save_bootstrap_target_config", _failing_save)

    with pytest.raises(OSError, match="locked"):
        app_module.run_app()

    assert captured == {
        "shell": captured["shell"],
        "config": runtime_database_config,
        "last_operator_prefill": "Sgt Example",
        "emergency_reset_callback": captured["emergency_reset_callback"],
        "run_called": True,
        "persist_config_path": app_module.DEFAULT_CONFIG_PATH,
        "persist_target": runtime_database_config.bootstrap_target,
    }
    assert callable(captured["emergency_reset_callback"])
    assert shell_close_calls == ["close"]


def test_run_app_does_not_wire_startup_reset_callback_without_remembered_target(monkeypatch) -> None:
    database_config = DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
    )
    bootstrap_ui_config = BootstrapUiConfig()
    runtime_database_config = DatabaseConfig(dialect="", database_path="")
    captured: dict[str, object] = {}

    class FakeAppShell:
        def run_startup_dialog(
            self,
            config: DatabaseConfig,
            *,
            last_operator_prefill="",
            emergency_reset_callback=None,
        ):
            captured["config"] = config
            captured["last_operator_prefill"] = last_operator_prefill
            captured["emergency_reset_callback"] = emergency_reset_callback
            captured["run_called"] = True
            return None

        def show_main_window(
            self,
            startup_result: StartupDialogSuccess,
            *,
            app_runtime_state: AppRuntimeState,
            window_config=None,
            template_callback=None,
            reset_callback=None,
            close_callback=None,
        ) -> None:
            raise AssertionError(f"show_main_window should not be called: {startup_result!r}")

        def close(self) -> None:
            raise AssertionError("close should not be called when startup is cancelled")

    monkeypatch.setattr(app_module, "load_database_config", lambda _path: database_config)
    monkeypatch.setattr(
        app_module,
        "resolve_bootstrap_ui_settings",
        lambda _path: bootstrap_ui_config,
    )
    monkeypatch.setattr(
        app_module,
        "resolve_runtime_database_config",
        lambda loaded_config, *, config_path: runtime_database_config,
    )
    monkeypatch.setattr(app_module, "AppShell", FakeAppShell)

    result = app_module.run_app()

    assert result is None
    assert captured == {
        "config": runtime_database_config,
        "last_operator_prefill": "",
        "emergency_reset_callback": None,
        "run_called": True,
    }


def test_main_window_close_callback_persists_blank_last_operator_from_runtime_context(monkeypatch) -> None:
    startup_result = StartupDialogSuccess(
        repository=object(),
        remembered_target=BootstrapTargetConfig(dialect="sqlite", database_path="eventlog.db"),
        last_operator="Sgt Example",
    )
    bootstrap_ui_config = BootstrapUiConfig(
        main_window=MainWindowConfig(window_state="normal", window_width=1200, window_height=700),
        language="sv",
        last_operator="Earlier Operator",
    )
    persisted_ui: dict[str, object] = {}
    close_calls: list[StartupDialogSuccess] = []
    shell_close_calls: list[str] = []

    class FakeAppShell:
        def snapshot_main_window_config(self):
            return None

        def close(self) -> None:
            shell_close_calls.append("close")

    monkeypatch.setattr(
        app_module,
        "run_active_context_close",
        lambda received_startup_result: close_calls.append(received_startup_result)
        or ResetOutcome(
            had_active_context=True,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "save_bootstrap_ui_config",
        lambda config_path, config: persisted_ui.update(
            {
                "config_path": config_path,
                "config": config,
            }
        ),
    )

    callback = app_module._build_main_window_close_callback(
        cast(app_module.AppShell, cast(object, FakeAppShell())),
        startup_result,
        config_path=app_module.DEFAULT_CONFIG_PATH,
        bootstrap_ui_config=bootstrap_ui_config,
        app_runtime_state=AppRuntimeState(),
    )

    assert callback() is None
    assert persisted_ui == {
        "config_path": app_module.DEFAULT_CONFIG_PATH,
        "config": BootstrapUiConfig(
            main_window=bootstrap_ui_config.main_window,
            language="sv",
            last_operator="",
        ),
    }
    assert close_calls == [startup_result]
    assert shell_close_calls == ["close"]


