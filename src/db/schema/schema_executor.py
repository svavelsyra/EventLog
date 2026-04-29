"""Utilities for applying SQLite schema files to a database connection."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
import sqlite3


def execute_schema_file(
    connection: sqlite3.Connection,
    sql_file_path: str | PathLike[str],
) -> None:
    """Execute a SQL schema file against an SQLite connection and commit it."""
    schema_path = Path(sql_file_path)
    schema_sql = schema_path.read_text(encoding="utf-8")

    connection.executescript(schema_sql)
    connection.commit()

