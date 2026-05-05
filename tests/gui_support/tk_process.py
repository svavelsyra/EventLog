"""Reusable Tk subprocess-isolation helpers for GUI tests."""

from __future__ import annotations

import multiprocessing as mp
import tkinter as tk
import traceback
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

import pytest


TkScenario = Callable[[tk.Tk], object]


def _drain_tk_events(root: tk.Tk) -> None:
    """Run pending idle/UI work so teardown happens from a settled Tk state."""
    root.update_idletasks()
    root.update()



def _destroy_child_windows(root: tk.Tk) -> None:
    """Destroy any remaining direct child windows owned by the root."""
    for child in tuple(root.winfo_children()):
        child.destroy()



def _run_tk_scenario_in_child(
    child_connection: Connection,
    scenario: TkScenario,
) -> None:
    """Execute one Tk scenario in a fresh child process."""
    cleanup_root: tk.Tk | None = None

    try:
        root = tk.Tk()
        cleanup_root = root
        root.withdraw()
        _drain_tk_events(root)
        result = scenario(root)
        _drain_tk_events(root)
        _destroy_child_windows(root)
        _drain_tk_events(root)
        root.destroy()
        child_connection.send(("ok", result))
    except BaseException:
        child_connection.send(("error", traceback.format_exc()))
    finally:
        if cleanup_root is not None:
            try:
                if cleanup_root.winfo_exists():
                    _destroy_child_windows(cleanup_root)
                    cleanup_root.destroy()
            except Exception:
                pass

        child_connection.close()



def run_isolated_tk_scenario(
    scenario: TkScenario,
    *,
    timeout_seconds: float = 15,
    join_timeout_seconds: float = 5,
) -> Any:
    """Run one GUI scenario in a fresh spawned Tk process.

    Tkinter is a hard project prerequisite, so setup must fail loudly if the
    runtime is broken or unavailable. Each scenario runs in its own child
    process so Tk interpreter corruption cannot leak between tests.
    """
    context = mp.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_run_tk_scenario_in_child,
        args=(child_connection, scenario),
    )
    process.start()
    child_connection.close()

    if not parent_connection.poll(timeout_seconds):
        process.terminate()
        process.join(timeout=join_timeout_seconds)
        pytest.fail("Tk scenario process timed out before returning a result.")

    status, payload = parent_connection.recv()
    parent_connection.close()
    process.join(timeout=join_timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(timeout=join_timeout_seconds)
        pytest.fail("Tk scenario process did not exit cleanly.")

    if status == "error":
        pytest.fail(f"Tk scenario failed in child process:\n{payload}")

    if process.exitcode != 0:
        pytest.fail(
            f"Tk scenario process exited with code {process.exitcode} despite reporting success."
        )

    return payload


__all__ = ["TkScenario", "run_isolated_tk_scenario"]

