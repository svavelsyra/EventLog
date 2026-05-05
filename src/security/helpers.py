"""Shared security helper implementation for credential validation and key derivation."""

from __future__ import annotations

import hashlib
from os import fsync
from os import PathLike
from pathlib import Path

from src.config.app_config import DEFAULT_KDF_ITERATIONS, DEFAULT_MIN_PASSWORD_LENGTH

DEFAULT_MIN_KEY_FILE_SIZE_BYTES = 0
RECOMMENDED_MIN_KEY_FILE_SIZE_BYTES = 1_024
DEFAULT_DERIVED_KEY_LENGTH_BYTES = 32
MAX_KEY_FILE_SIZE_BYTES = 100 * 1_024 * 1_024
MAX_KDF_ITERATIONS = 10_000_000
GENERIC_INVALID_CREDENTIALS_MESSAGE = "Ogiltigt lösenord eller nyckelfil. Försök igen."


class SecurityHelperError(ValueError):
    """Base exception for credential-preparation helper failures."""


class PasswordValidationError(SecurityHelperError):
    """Raised when a password does not satisfy the current validation contract."""


class KeyFileValidationError(SecurityHelperError):
    """Raised when a selected key file cannot be used safely."""


class KeyDerivationError(SecurityHelperError):
    """Raised when key-derivation inputs are structurally invalid."""



def validate_password(password: str, *, min_length: int = DEFAULT_MIN_PASSWORD_LENGTH) -> None:
    """Validate a password against a caller-supplied minimum-length policy."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    if not isinstance(min_length, int) or isinstance(min_length, bool):
        raise TypeError("min_length must be an integer")

    if min_length < 0:
        raise ValueError("min_length must be at least 0")

    if len(password) < min_length:
        raise PasswordValidationError(f"Lösenord måste vara minst {min_length} tecken")



def load_key_file_bytes(
    file_path: str | PathLike[str],
    *,
    min_size_bytes: int = DEFAULT_MIN_KEY_FILE_SIZE_BYTES,
    max_size_bytes: int = MAX_KEY_FILE_SIZE_BYTES,
) -> bytes:
    """Validate generic key-file usability and read the file into memory."""
    if not isinstance(min_size_bytes, int) or isinstance(min_size_bytes, bool):
        raise TypeError("min_size_bytes must be an integer")

    if not isinstance(max_size_bytes, int) or isinstance(max_size_bytes, bool):
        raise TypeError("max_size_bytes must be an integer")

    if min_size_bytes < 0:
        raise ValueError("min_size_bytes must be at least 0")

    if max_size_bytes < min_size_bytes:
        raise ValueError("max_size_bytes must be greater than or equal to min_size_bytes")

    normalized_path = Path(file_path).expanduser()

    if not normalized_path.exists():
        raise KeyFileValidationError("Fil finns inte")

    if not normalized_path.is_file():
        raise KeyFileValidationError("Måste vara en fil, inte katalog")

    try:
        file_size = normalized_path.stat().st_size
    except OSError as exc:
        raise KeyFileValidationError(f"Kan inte läsa filstorlek: {exc}") from exc

    if file_size < min_size_bytes:
        raise KeyFileValidationError("Fil för liten")

    if file_size > max_size_bytes:
        raise KeyFileValidationError("Fil för stor (maximum 100 MB)")

    try:
        return normalized_path.read_bytes()
    except PermissionError as exc:
        raise KeyFileValidationError("Kan inte läsa nyckelfilen (behörighet saknas)") from exc
    except OSError as exc:
        raise KeyFileValidationError(f"Kan inte öppna nyckelfilen: {exc}") from exc



def _best_effort_overwrite_file_contents(path: Path, *, secure_delete_passes: int) -> None:
    """Try to overwrite a file before deletion without making overwrite failures fatal."""
    if secure_delete_passes <= 0 or not path.exists() or not path.is_file():
        return

    try:
        file_size = path.stat().st_size
    except OSError:
        return

    if file_size <= 0:
        return

    chunk_size = min(4096, file_size)

    try:
        with path.open("r+b") as file_handle:
            for overwrite_pass in range(secure_delete_passes):
                overwrite_byte = b"\x00" if overwrite_pass % 2 == 0 else b"\xFF"
                bytes_remaining = file_size
                file_handle.seek(0)

                while bytes_remaining > 0:
                    current_chunk_size = min(chunk_size, bytes_remaining)
                    file_handle.write(overwrite_byte * current_chunk_size)
                    bytes_remaining -= current_chunk_size

                file_handle.flush()
                try:
                    fsync(file_handle.fileno())
                except OSError:
                    continue
    except OSError:
        return


def best_effort_secure_delete(
    path: str | PathLike[str],
    *,
    allow_secure_overwrite: bool = True,
    secure_delete_passes: int = 0,
) -> None:
    """Best-effort overwrite a file and then delete it.

    Overwrite failures are intentionally swallowed so deletion can still be
    attempted. Final deletion remains the authoritative success/failure signal.
    """
    normalized_path = Path(path)
    if allow_secure_overwrite:
        _best_effort_overwrite_file_contents(
            normalized_path,
            secure_delete_passes=secure_delete_passes,
        )

    normalized_path.unlink(missing_ok=True)



def derive_encryption_key(
    password: str,
    *,
    salt: bytes,
    iterations: int = DEFAULT_KDF_ITERATIONS,
    length: int = DEFAULT_DERIVED_KEY_LENGTH_BYTES,
) -> bytes:
    """Derive deterministic key material with the shared PBKDF2-HMAC-SHA256 primitive."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    if not isinstance(salt, bytes):
        raise TypeError("salt must be bytes")

    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise KeyDerivationError("KDF iterations must be an integer")

    if not isinstance(length, int) or isinstance(length, bool):
        raise KeyDerivationError("Derived key length must be an integer")

    if not salt:
        raise KeyDerivationError("KDF salt must not be empty")

    if iterations < 1:
        raise KeyDerivationError(f"KDF iterations must be >= 1 (got {iterations})")

    if iterations > MAX_KDF_ITERATIONS:
        raise KeyDerivationError(f"KDF iterations must be <= {MAX_KDF_ITERATIONS} (got {iterations})")

    if length < 1:
        raise KeyDerivationError(f"Derived key length must be >= 1 (got {length})")

    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=length,
    )


__all__ = [
    "DEFAULT_DERIVED_KEY_LENGTH_BYTES",
    "DEFAULT_MIN_KEY_FILE_SIZE_BYTES",
    "GENERIC_INVALID_CREDENTIALS_MESSAGE",
    "KeyDerivationError",
    "KeyFileValidationError",
    "MAX_KDF_ITERATIONS",
    "MAX_KEY_FILE_SIZE_BYTES",
    "PasswordValidationError",
    "RECOMMENDED_MIN_KEY_FILE_SIZE_BYTES",
    "SecurityHelperError",
    "best_effort_secure_delete",
    "derive_encryption_key",
    "load_key_file_bytes",
    "validate_password",
]

