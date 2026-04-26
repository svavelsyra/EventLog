"""
Global test configuration and fixtures for EventLog tests.

This conftest.py is automatically discovered by pytest and provides
fixtures available to all tests.

Fixtures defined here:
- Database fixtures (in-memory SQLite)
- Sample data fixtures
- Common test utilities
"""

import pytest
import sqlite3
from datetime import datetime


# Example fixture structure (to be implemented):

# @pytest.fixture
# def in_memory_db():
#     """Create an in-memory SQLite database for testing."""
#     conn = sqlite3.connect(':memory:')
#     # Setup schema here
#     yield conn
#     conn.close()


# @pytest.fixture
# def sample_message_entry():
#     """Provide sample message log entry data for testing."""
#     return {
#         'content': 'Test radio message',
#         'from': 'Station Alpha',
#         'to': 'Station Bravo',
#         'event_time': datetime.now(),
#         'communication_method': 'Radio',
#         'operator': 'Test Operator',
#         'confirmed': True
#     }

