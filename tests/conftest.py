"""Global pytest fixtures shared across the EventLog test suite."""

from pathlib import Path

import pytest

import src.app as app_module


@pytest.fixture
def isolated_config_dir(tmp_path: Path) -> Path:
	"""Return the per-test directory that owns the forced default config path."""
	config_dir = tmp_path / "app-config"
	config_dir.mkdir()
	return config_dir


@pytest.fixture
def isolated_default_config_path(isolated_config_dir: Path) -> Path:
	"""Return a per-test default config.ini path and seed it with an empty file."""
	config_path = isolated_config_dir / "data" / "config.ini"
	config_path.parent.mkdir(parents=True, exist_ok=True)
	config_path.write_text("", encoding="utf-8")
	return config_path


@pytest.fixture(autouse=True)
def force_isolated_default_config_path(
	monkeypatch: pytest.MonkeyPatch,
	isolated_default_config_path: Path,
) -> Path:
	"""Prevent tests from falling back to the real workspace config.ini path."""
	monkeypatch.setattr(app_module, "DEFAULT_CONFIG_PATH", isolated_default_config_path)
	return isolated_default_config_path

