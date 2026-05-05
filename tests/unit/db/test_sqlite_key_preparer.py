import hashlib

import pytest

from src.config import DatabaseConfig
from src.db.sqlite_key_preparer import (
    SQLITE_ENCRYPTION_KEY_LENGTH_BYTES,
    SQLITE_PASSWORD_ONLY_KDF_SALT,
    prepare_sqlite_encryption_key,
)
from src.security import derive_encryption_key


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("password", "iterations"),
    [
        ("lösenord123", 2),
        ("GrönaVagnarRullar2026", 3),
    ],
)
def test_prepare_sqlite_encryption_key_uses_backend_default_salt_for_password_only_mode(
    password: str,
    iterations: int,
) -> None:
    config = DatabaseConfig(kdf_iterations=iterations)

    prepared_key = prepare_sqlite_encryption_key(password, None, config)

    assert prepared_key == derive_encryption_key(
        password,
        salt=SQLITE_PASSWORD_ONLY_KDF_SALT,
        iterations=iterations,
        length=SQLITE_ENCRYPTION_KEY_LENGTH_BYTES,
    )


def test_prepare_sqlite_encryption_key_hashes_key_file_bytes_before_derivation() -> None:
    password = "lösenord123"
    key_file_bytes = b"raw-key-file-material"
    config = DatabaseConfig(kdf_iterations=2)

    prepared_key = prepare_sqlite_encryption_key(password, key_file_bytes, config)

    assert prepared_key == derive_encryption_key(
        password,
        salt=hashlib.sha256(key_file_bytes).digest(),
        iterations=2,
        length=SQLITE_ENCRYPTION_KEY_LENGTH_BYTES,
    )


def test_prepare_sqlite_encryption_key_allows_key_file_only_mode_when_backend_receives_bytes() -> None:
    key_file_bytes = b"key-file-only-mode"
    config = DatabaseConfig(kdf_iterations=1)

    prepared_key = prepare_sqlite_encryption_key("", key_file_bytes, config)

    assert prepared_key == derive_encryption_key(
        "",
        salt=hashlib.sha256(key_file_bytes).digest(),
        iterations=1,
        length=SQLITE_ENCRYPTION_KEY_LENGTH_BYTES,
    )


@pytest.mark.parametrize(
    ("password", "key_file_bytes", "database_config", "expected_exception", "expected_message"),
    [
        (123, None, DatabaseConfig(), TypeError, "password"),
        ("lösenord123", "not-bytes", DatabaseConfig(), TypeError, "key_file_bytes"),
        ("lösenord123", None, object(), TypeError, "database_config"),
    ],
)
def test_prepare_sqlite_encryption_key_rejects_invalid_structural_inputs(
    password: object,
    key_file_bytes: object,
    database_config: object,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    with pytest.raises(expected_exception, match=expected_message):
        prepare_sqlite_encryption_key(password, key_file_bytes, database_config)  # type: ignore[arg-type]


