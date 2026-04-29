from __future__ import annotations

from datetime import datetime
import sqlite3
from typing import Protocol

import pytest

import src.db.repositories.sqlite.event_log_repository as event_log_repository_module


class _RepositoryWithConnection(Protocol):
    """Compatibility seam for DB test helpers that use direct SQL access."""

    connection: sqlite3.Connection


def set_edit_grace_period_seconds(
    repository: _RepositoryWithConnection,
    value: int | str,
) -> None:
    repository.connection.execute(
        "UPDATE settings SET value = ?, modified_time = ? WHERE key = ?",
        (str(value), datetime.now().isoformat(), "edited_flag_grace_period_seconds"),
    )
    repository.connection.commit()


def set_communication_logged_time(
    repository: _RepositoryWithConnection,
    entry_id: int,
    logged_time: datetime,
) -> None:
    repository.connection.execute(
        "UPDATE communication_entries SET logged_time = ? WHERE id = ?",
        (logged_time.isoformat(), entry_id),
    )
    repository.connection.commit()


def set_event_logged_time(
    repository: _RepositoryWithConnection,
    entry_id: int,
    logged_time: datetime,
) -> None:
    repository.connection.execute(
        "UPDATE event_entries SET logged_time = ? WHERE id = ?",
        (logged_time.isoformat(), entry_id),
    )
    repository.connection.commit()


def freeze_repository_now(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return cls.fromtimestamp(fixed_now.timestamp(), tz)
            return cls.fromtimestamp(fixed_now.timestamp())

    monkeypatch.setattr(event_log_repository_module, "datetime", FixedDateTime)

