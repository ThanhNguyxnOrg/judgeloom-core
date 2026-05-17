from __future__ import annotations

import importlib
from typing import TypeVar

from apps.contests.formats.base import AbstractContestFormat

FormatType = TypeVar("FormatType", bound=type[AbstractContestFormat])

registry: dict[str, type[AbstractContestFormat]] = {}
_DISCOVERED = False


def register_format[FormatType: type[AbstractContestFormat]](format_cls: FormatType) -> FormatType:
    """Register a contest format class in global registry.

    Args:
        format_cls: Concrete format class.

    Returns:
        Registered class for decorator usage.
    """

    registry[format_cls.key] = format_cls
    return format_cls


def _autodiscover_formats() -> None:
    """Import format modules once to populate registry."""

    global _DISCOVERED
    if _DISCOVERED:
        return

    modules = (
        "apps.contests.formats.default",
        "apps.contests.formats.icpc",
        "apps.contests.formats.ioi",
        "apps.contests.formats.atcoder",
        "apps.contests.formats.ecoo",
    )
    for module_path in modules:
        importlib.import_module(module_path)
    _DISCOVERED = True


def get_format(format_key: str) -> AbstractContestFormat:
    """Instantiate format implementation by key.

    Args:
        format_key: Format identifier.

    Returns:
        Instantiated format object.

    Raises:
        KeyError: If format key is unknown.
    """

    _autodiscover_formats()
    if format_key not in registry:
        raise KeyError(f"Unknown contest format: {format_key}")
    return registry[format_key]()


__all__ = ["AbstractContestFormat", "get_format", "register_format", "registry"]
