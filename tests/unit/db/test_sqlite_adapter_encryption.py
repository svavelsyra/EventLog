import pytest
from pathlib import Path

import src.db.sqlite_adapter as sqlite_adapter_module
from src.db.database_adapter import (
    BackendCleanupArtifactMetadata,
    BackendCleanupMetadata,
    DatabaseAdapterError,
    DatabaseNewer,
    EncryptedDatabaseProfileMismatch,
    EncryptedDatabaseUnreadable,
    EncryptedDatabaseWrongKey,
    MigrationNeeded,
)
from src.db.sqlite_adapter import (
    SQLCipherUnavailable,
    SQLITE_APPLICATION_ID,
    SQLITE_USER_VERSION,
    SQLiteAdapter,
)


pytestmark = pytest.mark.unit

ENCRYPTION_KEY = bytes.fromhex(
    "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
)


class _FakeCursor:
    pass


class _FakeQueryResult:
    def __init__(self, row: object | None = None) -> None:
        self._row = row

    def fetchone(self) -> object | None:
        return self._row


class _RecordingConnection:
    def __init__(self) -> None:
        self.row_factory = None
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.cursor_instance = _FakeCursor()

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def execute(self, query: str, params: tuple[object, ...] = ()) -> _FakeQueryResult:
        self.executed.append((query, params))
        return _FakeQueryResult((1,))


class _RecordingDBAPIModule:
    Row = object()

    def __init__(self, connection: _RecordingConnection | _QueryMappingConnection) -> None:
        self._connection = connection
        self.connected_path: str | None = None

    def connect(self, database_path: str) -> _RecordingConnection | _QueryMappingConnection:
        self.connected_path = database_path
        return self._connection


class _FailingConnection:
    def __init__(self, error_message: str) -> None:
        self._error_message = error_message

    def execute(self, query: str, params: tuple[object, ...] = ()) -> _FakeQueryResult:
        raise RuntimeError(self._error_message)


class _QueryMappingConnection:
    def __init__(self, rows_by_query: dict[str, object | None]) -> None:
        self.row_factory = None
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.cursor_instance = _FakeCursor()
        self._rows_by_query = rows_by_query

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def execute(self, query: str, params: tuple[object, ...] = ()) -> _FakeQueryResult:
        self.executed.append((query, params))
        return _FakeQueryResult(self._rows_by_query.get(query, (1,)))


@pytest.mark.parametrize(
    "value",
    ["not-bytes", 123, object()],
)
def test_normalize_encryption_key_rejects_non_bytes(value: object) -> None:
    with pytest.raises(TypeError, match="encryption_key must be bytes or None"):
        SQLiteAdapter._normalize_encryption_key(value)  # type: ignore[arg-type]


def test_normalize_encryption_key_rejects_empty_bytes() -> None:
    with pytest.raises(ValueError, match="encryption_key must not be empty"):
        SQLiteAdapter._normalize_encryption_key(b"")


def test_encrypted_adapter_connect_uses_sqlcipher_module_and_applies_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "encrypted-adapter.db"
    fake_connection = _RecordingConnection()
    fake_dbapi_module = _RecordingDBAPIModule(fake_connection)

    monkeypatch.setattr(sqlite_adapter_module, "sqlcipher3", fake_dbapi_module)
    monkeypatch.setattr(SQLiteAdapter, "initialize_schema", lambda self: None)

    adapter = SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY)

    expected_key_pragma = f'PRAGMA key = "x\'{ENCRYPTION_KEY.hex()}\'"'

    assert fake_dbapi_module.connected_path == str(database_path)
    assert adapter.connection is fake_connection
    assert adapter.cursor is fake_connection.cursor_instance
    assert adapter.connection.row_factory is fake_dbapi_module.Row
    assert fake_connection.executed == [
        (expected_key_pragma, ()),
        ("SELECT COUNT(*) FROM sqlite_master", ()),
    ]


def test_encrypted_adapter_connect_validates_profile_metadata_for_preexisting_encrypted_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "existing-encrypted.db"
    database_path.write_bytes(b"")
    fake_connection = _QueryMappingConnection(
        {
            "PRAGMA application_id": (SQLITE_APPLICATION_ID,),
            "PRAGMA user_version": (SQLITE_USER_VERSION,),
        }
    )
    fake_dbapi_module = _RecordingDBAPIModule(fake_connection)

    monkeypatch.setattr(sqlite_adapter_module, "sqlcipher3", fake_dbapi_module)

    SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY)

    expected_key_pragma = f'PRAGMA key = "x\'{ENCRYPTION_KEY.hex()}\'"'
    assert fake_connection.executed == [
        (expected_key_pragma, ()),
        ("SELECT COUNT(*) FROM sqlite_master", ()),
        ("PRAGMA application_id", ()),
        ("PRAGMA user_version", ()),
    ]


def test_encrypted_adapter_raises_sqlcipher_unavailable_when_backend_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sqlite_adapter_module, "sqlcipher3", None)

    with pytest.raises(SQLCipherUnavailable, match="SQLCipher support is unavailable"):
        SQLiteAdapter(":memory:", encryption_key=ENCRYPTION_KEY)


def test_apply_sqlcipher_key_raises_encrypted_database_unreadable_on_execute_failure() -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.encryption_key = ENCRYPTION_KEY
    adapter.database_path = "broken-encrypted.db"
    adapter.connection = _FailingConnection("key apply failed")

    with pytest.raises(EncryptedDatabaseUnreadable, match="Could not apply encrypted SQLite key material"):
        adapter._apply_sqlcipher_key()


def test_initialize_schema_stamps_encrypted_profile_metadata_for_new_encrypted_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = "new-encrypted.db"
    adapter.connection = _RecordingConnection()
    adapter._database_preexisted = False
    adapter._uses_encryption = True

    schema_calls: list[object] = []

    monkeypatch.setattr(
        sqlite_adapter_module,
        "execute_schema_file",
        lambda connection, schema_path: schema_calls.append((connection, schema_path)),
    )

    adapter.initialize_schema()

    assert len(schema_calls) == 1
    assert adapter.connection.executed == [
        (f"PRAGMA application_id = {SQLITE_APPLICATION_ID}", ()),
        (f"PRAGMA user_version = {SQLITE_USER_VERSION}", ()),
    ]


@pytest.mark.parametrize(
    "error_message",
    [
        "file is not a database",
        "file is encrypted or is not a database",
        "SQL logic error: file is not a database",
    ],
)
def test_verify_encrypted_readiness_classifies_known_wrong_key_failures_for_existing_database(
    error_message: str,
) -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = "locked-encrypted.db"
    adapter._database_preexisted = True
    adapter.connection = _FailingConnection(error_message)

    with pytest.raises(EncryptedDatabaseWrongKey, match="Could not unlock encrypted SQLite database"):
        adapter._verify_encrypted_readiness()


@pytest.mark.parametrize(
    ("application_id", "user_version", "expected_exception", "expected_message"),
    [
        (0, SQLITE_USER_VERSION, EncryptedDatabaseProfileMismatch, "application_id"),
        (SQLITE_APPLICATION_ID, SQLITE_USER_VERSION - 1, MigrationNeeded, "requires migration"),
        (SQLITE_APPLICATION_ID, SQLITE_USER_VERSION + 1, DatabaseNewer, "has newer user_version"),
    ],
)
def test_validate_existing_encrypted_profile_metadata_classifies_application_or_version_mismatch(
    application_id: int,
    user_version: int,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = "wrong-profile.db"
    adapter._uses_encryption = True
    adapter.connection = _QueryMappingConnection(
        {
            "PRAGMA application_id": (application_id,),
            "PRAGMA user_version": (user_version,),
        }
    )

    with pytest.raises(expected_exception, match=expected_message):
        adapter._validate_existing_profile_metadata()


@pytest.mark.parametrize(
    ("database_preexisted", "error_message", "expected_operation"),
    [
        (False, "catalog read failed", "create"),
        (True, "catalog read failed", "open"),
        (False, "file is not a database", "create"),
    ],
)
def test_verify_encrypted_readiness_raises_operation_specific_unreadable_error(
    database_preexisted: bool,
    error_message: str,
    expected_operation: str,
) -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = "unreadable-encrypted.db"
    adapter._database_preexisted = database_preexisted
    adapter.connection = _FailingConnection(error_message)

    with pytest.raises(
        EncryptedDatabaseUnreadable,
        match=rf"Could not {expected_operation} encrypted SQLite database",
    ):
        adapter._verify_encrypted_readiness()


def test_get_cleanup_metadata_returns_sqlite_owned_artifact_kinds_for_existing_footprint(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    shm_path = Path(f"{database_path}-shm")
    journal_path = Path(f"{database_path}-journal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")
    journal_path.write_text("journal", encoding="utf-8")

    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = str(database_path)

    assert adapter.get_cleanup_metadata() == BackendCleanupMetadata(
        artifacts=(
            BackendCleanupArtifactMetadata(path=database_path, artifact_kind="database"),
            BackendCleanupArtifactMetadata(path=wal_path, artifact_kind="wal"),
            BackendCleanupArtifactMetadata(path=shm_path, artifact_kind="shm"),
            BackendCleanupArtifactMetadata(path=journal_path, artifact_kind="journal"),
        )
    )


def test_get_cleanup_metadata_returns_empty_for_in_memory_sqlite() -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = ":memory:"

    assert adapter.get_cleanup_metadata() == BackendCleanupMetadata()


def test_fetch_raises_stable_closed_database_error_after_adapter_close() -> None:
    adapter = object.__new__(SQLiteAdapter)
    adapter.database_path = "closed-eventlog.db"
    adapter.connection = None

    with pytest.raises(DatabaseAdapterError, match="closed"):
        adapter.fetch("SELECT 1")


