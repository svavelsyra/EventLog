from pathlib import Path

import pytest

from src.security import (
    DEFAULT_DERIVED_KEY_LENGTH_BYTES,
    GENERIC_INVALID_CREDENTIALS_MESSAGE,
    KeyDerivationError,
    KeyFileValidationError,
    MAX_KDF_ITERATIONS,
    PasswordValidationError,
    RECOMMENDED_MIN_KEY_FILE_SIZE_BYTES,
    SecurityHelperError,
    best_effort_secure_delete,
    derive_encryption_key,
    load_key_file_bytes,
    validate_password,
)


pytestmark = pytest.mark.unit



def test_validate_password_accepts_unicode_password_when_long_enough() -> None:
    validate_password("GrönaVagnarRullar2026", min_length=8)



def test_validate_password_allows_empty_password_when_policy_permits() -> None:
    validate_password("", min_length=0)



def test_validate_password_rejects_short_passwords_for_active_policy() -> None:
    with pytest.raises(PasswordValidationError, match="minst 12 tecken"):
        validate_password("kort", min_length=12)


def test_validate_password_rejects_non_string_passwords() -> None:
    with pytest.raises(TypeError, match="password"):
        validate_password(password=123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("min_length", "expected_exception"),
    [(-1, ValueError), (True, TypeError)],
)
def test_validate_password_rejects_invalid_minimum_length_values(
    min_length: int,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception):
        validate_password("giltigt lösenord", min_length=min_length)



def test_load_key_file_bytes_returns_contents_for_small_valid_file_by_default(tmp_path: Path) -> None:
    key_file_path = tmp_path / "key.bin"
    payload = b"tiny"
    key_file_path.write_bytes(payload)

    assert load_key_file_bytes(key_file_path) == payload
    assert RECOMMENDED_MIN_KEY_FILE_SIZE_BYTES == 1_024


@pytest.mark.parametrize(
    ("path_factory", "expected_message"),
    [
        (lambda tmp_path: tmp_path / "missing.bin", "Fil finns inte"),
        (lambda tmp_path: tmp_path, "Måste vara en fil, inte katalog"),
    ],
)
def test_load_key_file_bytes_rejects_missing_files_and_directories(
    tmp_path: Path,
    path_factory,
    expected_message: str,
) -> None:
    with pytest.raises(KeyFileValidationError, match=expected_message):
        load_key_file_bytes(path_factory(tmp_path))



def test_load_key_file_bytes_rejects_small_file_when_caller_sets_lower_bound(tmp_path: Path) -> None:
    key_file_path = tmp_path / "small.bin"
    key_file_path.write_bytes(b"tiny")

    with pytest.raises(KeyFileValidationError, match="Fil för liten"):
        load_key_file_bytes(key_file_path, min_size_bytes=8)



def test_load_key_file_bytes_rejects_large_file_when_limit_lowered(tmp_path: Path) -> None:
    key_file_path = tmp_path / "large.bin"
    payload = b"A" * 32
    key_file_path.write_bytes(payload)

    with pytest.raises(KeyFileValidationError, match="Fil för stor"):
        load_key_file_bytes(key_file_path, min_size_bytes=1, max_size_bytes=16)


@pytest.mark.parametrize(
    ("min_size_bytes", "max_size_bytes", "expected_exception"),
    [
        (-1, 16, ValueError),
        (True, 16, TypeError),
        (0, False, TypeError),
        (16, 8, ValueError),
    ],
)
def test_load_key_file_bytes_rejects_invalid_size_bounds(
    tmp_path: Path,
    min_size_bytes: int,
    max_size_bytes: int,
    expected_exception: type[Exception],
) -> None:
    key_file_path = tmp_path / "key.bin"
    key_file_path.write_bytes(b"A" * 8)

    with pytest.raises(expected_exception):
        load_key_file_bytes(
            key_file_path,
            min_size_bytes=min_size_bytes,
            max_size_bytes=max_size_bytes,
        )



def test_load_key_file_bytes_reports_unreadable_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file_path = tmp_path / "locked.bin"
    key_file_path.write_bytes(b"A" * 8)

    def raise_permission_error(self: Path) -> bytes:
        if self == key_file_path:
            raise PermissionError("no read access")
        return Path.read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", raise_permission_error)

    with pytest.raises(KeyFileValidationError, match="behörighet saknas"):
        load_key_file_bytes(key_file_path)


def test_load_key_file_bytes_reports_open_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file_path = tmp_path / "broken.bin"
    key_file_path.write_bytes(b"A" * 8)

    def raise_os_error(self: Path) -> bytes:
        if self == key_file_path:
            raise OSError("broken device")
        return Path.read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    with pytest.raises(KeyFileValidationError, match="Kan inte öppna nyckelfilen"):
        load_key_file_bytes(key_file_path)


def test_load_key_file_bytes_reports_stat_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file_path = tmp_path / "broken-stat.bin"
    key_file_path.write_bytes(b"A" * 8)

    def raise_os_error(self: Path):
        if self == key_file_path:
            raise OSError("stat failed")
        return Path.stat(self)

    monkeypatch.setattr(Path, "stat", raise_os_error)

    with pytest.raises(KeyFileValidationError, match="Kan inte läsa filstorlek"):
        load_key_file_bytes(key_file_path)



def test_best_effort_secure_delete_ignores_missing_files(tmp_path: Path) -> None:
    best_effort_secure_delete(tmp_path / "missing.bin", secure_delete_passes=3)



def test_best_effort_secure_delete_falls_back_to_delete_when_overwrite_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.bin"
    artifact_path.write_bytes(b"payload")
    original_open = Path.open

    def fake_open(self: Path, mode: str = "r", *args, **kwargs):
        if self == artifact_path and mode == "r+b":
            raise OSError("overwrite blocked")
        return original_open(self, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", fake_open)

    best_effort_secure_delete(artifact_path, secure_delete_passes=2)

    assert artifact_path.exists() is False



def test_best_effort_secure_delete_propagates_delete_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.bin"
    artifact_path.write_bytes(b"payload")
    original_unlink = Path.unlink

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self == artifact_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    with pytest.raises(OSError, match="locked"):
        best_effort_secure_delete(artifact_path, secure_delete_passes=1)



def test_derive_encryption_key_is_deterministic_for_same_inputs() -> None:
    salt = b"backend-owned-salt"
    first_key = derive_encryption_key(
        "lösenord123",
        salt=salt,
        iterations=2,
        length=DEFAULT_DERIVED_KEY_LENGTH_BYTES,
    )
    second_key = derive_encryption_key(
        "lösenord123",
        salt=salt,
        iterations=2,
        length=DEFAULT_DERIVED_KEY_LENGTH_BYTES,
    )

    assert first_key == second_key
    assert len(first_key) == DEFAULT_DERIVED_KEY_LENGTH_BYTES



def test_derive_encryption_key_changes_when_password_salt_iteration_or_length_changes() -> None:
    base_key = derive_encryption_key("lösenord123", salt=b"salt-a", iterations=2, length=32)
    different_password = derive_encryption_key("annat-lösenord", salt=b"salt-a", iterations=2, length=32)
    different_salt = derive_encryption_key("lösenord123", salt=b"salt-b", iterations=2, length=32)
    different_iterations = derive_encryption_key("lösenord123", salt=b"salt-a", iterations=3, length=32)
    different_length = derive_encryption_key("lösenord123", salt=b"salt-a", iterations=2, length=16)

    assert base_key != different_password
    assert base_key != different_salt
    assert base_key != different_iterations
    assert base_key != different_length


def test_derive_encryption_key_allows_empty_password_when_other_inputs_are_valid() -> None:
    derived_key = derive_encryption_key("", salt=b"backend-owned-salt", iterations=1, length=16)

    assert len(derived_key) == 16


@pytest.mark.parametrize("iterations", [0, -1, MAX_KDF_ITERATIONS + 1, True])
def test_derive_encryption_key_rejects_invalid_iteration_values(iterations: int) -> None:
    with pytest.raises(KeyDerivationError):
        derive_encryption_key("lösenord123", salt=b"backend-owned-salt", iterations=iterations, length=32)


@pytest.mark.parametrize("length", [0, -1, True])
def test_derive_encryption_key_rejects_invalid_output_length_values(length: int) -> None:
    with pytest.raises(KeyDerivationError):
        derive_encryption_key("lösenord123", salt=b"backend-owned-salt", iterations=1, length=length)


def test_derive_encryption_key_rejects_invalid_salt_values() -> None:
    with pytest.raises(TypeError, match="salt"):
        derive_encryption_key("lösenord123", salt="not-bytes", iterations=1, length=32)  # type: ignore[arg-type]

    with pytest.raises(KeyDerivationError, match="salt must not be empty"):
        derive_encryption_key("lösenord123", salt=b"", iterations=1, length=32)


def test_derive_encryption_key_rejects_non_string_passwords() -> None:
    with pytest.raises(TypeError, match="password"):
        derive_encryption_key(password=123456, salt=b"backend-owned-salt", iterations=1, length=32)  # type: ignore[arg-type]



def test_security_helper_failures_can_be_handled_generically(tmp_path: Path) -> None:
    key_file_path = tmp_path / "missing.bin"

    with pytest.raises(SecurityHelperError):
        validate_password("x", min_length=2)

    with pytest.raises(SecurityHelperError):
        load_key_file_bytes(key_file_path)

    with pytest.raises(SecurityHelperError):
        derive_encryption_key("lösenord123", salt=b"backend-owned-salt", iterations=0, length=32)

    assert GENERIC_INVALID_CREDENTIALS_MESSAGE == "Ogiltigt lösenord eller nyckelfil. Försök igen."



