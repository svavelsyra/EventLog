"""Unit test specific fixtures and configuration."""

from collections.abc import Iterator
from typing import cast

import pytest

from src.db.repositories.repository_factory import RepositoryFactory
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


@pytest.fixture
def repository() -> Iterator[EventLogRepository]:
	"""Provide a fresh in-memory repository for each unit test."""
	repo = cast(EventLogRepository, RepositoryFactory.create_in_memory_repository())
	try:
		yield repo
	finally:
		repo.close()

