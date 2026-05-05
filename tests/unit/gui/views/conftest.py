import tkinter as tk
from collections.abc import Callable
from typing import Any

import pytest

from tests.gui_support import run_isolated_tk_scenario


@pytest.fixture
def run_tk_scenario() -> Callable[[Callable[[tk.Tk], object]], Any]:
    """Run one GUI view scenario through the shared isolated Tk helper."""

    def _run(scenario: Callable[[tk.Tk], object]) -> Any:
        return run_isolated_tk_scenario(scenario)

    return _run




