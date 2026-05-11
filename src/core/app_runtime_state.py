"""App-owned runtime state kept only in memory after startup.

Current scope is intentionally small: the running session's active operator.
Bootstrap persistence of the remembered operator remains a `config.ini`
concern, while historical database rows continue to snapshot their own
`operator` values when later workflows save entries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppRuntimeState:
    """App-owned runtime values for the current application session."""

    active_operator: str = ""

    def __post_init__(self) -> None:
        self.active_operator = self.active_operator.strip()

__all__ = ["AppRuntimeState"]

