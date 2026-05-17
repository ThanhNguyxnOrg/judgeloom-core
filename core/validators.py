"""
JudgeLoom — Core Validators
==============================

Shared validation functions used across models and serializers.

Functions:
    validate_slug: Ensure a string is a valid URL slug.
    validate_time_limit: Ensure a time limit is within platform bounds.
    validate_memory_limit: Ensure a memory limit is within platform bounds.
    validate_source_code_size: Check that source code doesn't exceed the cap.
    validate_file_extension: Restrict uploads to allowed extensions.
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?$")


def validate_slug(value: str) -> None:
    """Validate that a string is a clean URL slug.

    Rules: lowercase alphanumeric and hyphens only, must start and end
    with an alphanumeric character, max 128 characters.

    Args:
        value: The slug string to validate.

    Raises:
        ValidationError: If the slug is malformed.
    """
    if not value:
        raise ValidationError("Slug cannot be empty.")
    if len(value) > 128:
        raise ValidationError("Slug must be at most 128 characters.")
    if not _SLUG_RE.match(value):
        raise ValidationError(
            "Slug must contain only lowercase letters, numbers, and hyphens, "
            "and must start and end with a letter or number."
        )


def validate_time_limit(value: float) -> None:
    """Validate a problem time limit in seconds.

    Must be between 0.1 and 60 seconds (inclusive).

    Args:
        value: Time limit in seconds.

    Raises:
        ValidationError: If outside the allowed range.
    """
    if not (0.1 <= value <= 60.0):
        raise ValidationError(f"Time limit must be between 0.1 and 60 seconds, got {value}.")


def validate_memory_limit(value: int) -> None:
    """Validate a problem memory limit in kilobytes.

    Must be between 1024 KB (1 MB) and 1048576 KB (1 GB).

    Args:
        value: Memory limit in kilobytes.

    Raises:
        ValidationError: If outside the allowed range.
    """
    if not (1024 <= value <= 1_048_576):
        raise ValidationError(f"Memory limit must be between 1024 KB and 1048576 KB, got {value}.")


def validate_source_code_size(value: str | bytes) -> None:
    """Check that source code does not exceed the platform maximum.

    The limit is defined in ``settings.JUDGELOOM['MAX_SUBMISSION_SIZE']``.

    Args:
        value: The source code content (str or bytes).

    Raises:
        ValidationError: If the size exceeds the limit.
    """
    max_size: int = settings.JUDGELOOM["MAX_SUBMISSION_SIZE"]
    size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
    if size > max_size:
        raise ValidationError(f"Source code size ({size} bytes) exceeds the maximum allowed size ({max_size} bytes).")


_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".zip",
        ".tar",
        ".gz",
        ".txt",
        ".md",
    }
)


def validate_file_extension(filename: str, allowed: frozenset[str] | None = None) -> None:
    """Ensure a filename has an allowed extension.

    Args:
        filename: The file name to check (e.g. ``"report.pdf"``).
        allowed: Set of permitted extensions (lowercase, with dot).
            Defaults to ``_ALLOWED_EXTENSIONS``.

    Raises:
        ValidationError: If the extension is not in the allowed set.
    """
    if allowed is None:
        allowed = _ALLOWED_EXTENSIONS
    ext = "." + filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise ValidationError(f"File extension '{ext}' is not allowed. Permitted: {', '.join(sorted(allowed))}.")


def validate_positive_integer(value: Any) -> None:
    """Validate that a value is a positive integer.

    Args:
        value: The value to check.

    Raises:
        ValidationError: If not a positive integer.
    """
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(f"Expected a positive integer, got {value!r}.")
