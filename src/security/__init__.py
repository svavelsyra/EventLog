"""Public security helper package surface for EventLog."""

from src.security.helpers import (
    DEFAULT_DERIVED_KEY_LENGTH_BYTES,
    DEFAULT_MIN_KEY_FILE_SIZE_BYTES,
    GENERIC_INVALID_CREDENTIALS_MESSAGE,
    KeyDerivationError,
    KeyFileValidationError,
    MAX_KDF_ITERATIONS,
    MAX_KEY_FILE_SIZE_BYTES,
    PasswordValidationError,
    RECOMMENDED_MIN_KEY_FILE_SIZE_BYTES,
    SecurityHelperError,
    best_effort_secure_delete,
    derive_encryption_key,
    load_key_file_bytes,
    validate_password,
)
from src.security.reset_flow import ResetCoordinator, ResetFailureCategory, ResetOutcome


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
    "ResetCoordinator",
    "ResetFailureCategory",
    "ResetOutcome",
    "SecurityHelperError",
    "best_effort_secure_delete",
    "derive_encryption_key",
    "load_key_file_bytes",
    "validate_password",
]


