"""Focused tests for the intentionally small AppRuntimeState contract.

These tests mainly protect two decisions:
- startup seeding trims the remembered operator once on creation
- later runtime mutation stays plain/direct instead of reintroducing setter-style rules
"""

import pytest

from src.core.app_runtime_state import AppRuntimeState


pytestmark = pytest.mark.unit


def test_app_runtime_state_normalizes_active_operator_on_creation() -> None:
    """Creation trims bootstrap input before the app starts using the value."""
    state = AppRuntimeState(active_operator="  Sgt Example  ")

    assert state.active_operator == "Sgt Example"


def test_app_runtime_state_allows_plain_runtime_mutation_and_blank_fallback() -> None:
    """Runtime writes stay intentionally dumb: direct assignment with no extra policy."""
    state = AppRuntimeState()

    assert state.active_operator == ""

    # This guards the simplified design: normalization happens only at creation,
    # not on every later runtime write.
    state.active_operator = "  Captain Runtime  "
    assert state.active_operator == "  Captain Runtime  "

    state.active_operator = ""
    assert state.active_operator == ""


