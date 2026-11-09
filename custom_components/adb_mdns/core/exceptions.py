"""Exceptions for Android TV ADB core communication."""

from __future__ import annotations


class AdbError(Exception):
    """Base class for ADB errors."""


class AdbConnectionError(AdbError):
    """Connection failure or stream closed unexpectedly."""


class AdbAuthError(AdbError):
    """Pairing / authentication failure."""


class AdbTimeoutError(AdbError):
    """Timed out awaiting ADB response."""


__all__ = [
    "AdbAuthError",
    "AdbConnectionError",
    "AdbError",
    "AdbTimeoutError",
]
