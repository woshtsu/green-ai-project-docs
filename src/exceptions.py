"""Domain errors for the ML component."""

from __future__ import annotations

from typing import Any


class MLError(Exception):
    """Base error for the ML component."""

    code = "ML_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(MLError):
    """Raised when a dataset or feature payload is invalid."""

    code = "VALIDATION_ERROR"


class LeakageError(MLError):
    """Raised when a future-looking feature is detected."""

    code = "DATA_LEAKAGE"


class InsufficientDataError(MLError):
    """Raised when there is not enough data to train or evaluate."""

    code = "INSUFFICIENT_DATA"


class ModelNotFoundError(MLError):
    """Raised when a serialized model artifact is missing."""

    code = "MODEL_NOT_FOUND"
