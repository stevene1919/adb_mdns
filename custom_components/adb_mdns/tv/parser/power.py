"""Power state, foreground activity, and keyboard proto/text parsing for Android TV."""

from __future__ import annotations

import re
from typing import Any

_RE_WAKEFULNESS = re.compile(r"mWakefulness=([A-Za-z]+)")
_RE_SCREEN_ON = re.compile(r"(?:Display Power: state=ON|mScreenOn=true|mScreenState=ON)")
_RE_SCREEN_OFF = re.compile(r"(?:Display Power: state=OFF|mScreenOn=false|mScreenState=OFF)")
_RE_ACTIVITY = re.compile(r"(?:mResumedActivity|topResumedActivity|ResumedActivity)[:=].*?\bu\d+\s+([\w.]+)/")
_RE_FOCUS = re.compile(r"mCurrentFocus=Window\{[0-9a-fA-F]+\s+(?:u\d+\s+)?([\w.]+)/")
_RE_DREAMING = re.compile(r"(?:mWakefulness=Dreaming|isDreaming=true|mDreaming=true)")

_RE_IME_SHOWN = re.compile(r"\bmInputShown=true\b")
_RE_IME_FIELD = re.compile(r"\binputType=0x([0-9a-fA-F]+)\b.*\bfieldId=")

_RE_WAKE_LOCK = re.compile(
    r"^\s*(PARTIAL_WAKE_LOCK|FULL_WAKE_LOCK|SCREEN_\w+_WAKE_LOCK|DOZE_WAKE_LOCK|DRAW_WAKE_LOCK)\s+'([^']*)'",
    re.MULTILINE,
)


def parse_awake(power: str) -> bool | None:
    """Return True/False from ``dumpsys power`` lines, ``None`` if unknown."""
    if m := _RE_WAKEFULNESS.search(power):
        return m.group(1).lower() in ("awake", "dreaming")
    if _RE_SCREEN_ON.search(power):
        return True
    if _RE_SCREEN_OFF.search(power):
        return False
    return None


def parse_wakefulness(power: str) -> str | None:
    """Return the raw wakefulness (``Awake``, ``Asleep``, ``Dreaming``, ``Dozing``)."""
    if m := _RE_WAKEFULNESS.search(power):
        return m.group(1)
    return None


def parse_foreground(activities: str, window: str = "") -> str | None:
    """Return the foreground package (Android 11-14+ aware)."""
    if m := _RE_ACTIVITY.search(activities):
        return m.group(1)
    if m := _RE_FOCUS.search(window):
        return m.group(1)
    return None


def _proto_fields(data: list[int], start: int, end: int) -> dict[int, Any] | None:
    """Read one protobuf message: varints → int, length-delimited → (start, end)."""
    out: dict[int, Any] = {}
    i = start

    def varint() -> int | None:
        nonlocal i
        value = 0
        shift = 0
        while i < end and shift < 64:
            byte = data[i]
            i += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value
            shift += 7
        return None

    while i < end:
        key = varint()
        if key is None:
            return None
        number = key >> 3
        wire = key & 7
        if wire == 0:
            val = varint()
            if val is None:
                return None
            out[number] = val
        elif wire == 1:
            i += 8
        elif wire == 2:
            length = varint()
            if length is None or length < 0 or i + length > end:
                return None
            out[number] = (i, i + length)
            i += length
        elif wire == 5:
            i += 4
        else:
            return None
    return out if i == end else None


def parse_keyboard_proto(hex_dump: str) -> bool | None:
    """Parse ``dumpsys input_method --proto | od -An -tx1 -v``.

    Returns True if the on-screen keyboard is shown or a text field has focus,
    False if not, ``None`` if the output isn't the expected protobuf.
    """
    tokens = hex_dump.split()
    if not tokens:
        return None
    try:
        data = [int(tok, 16) for tok in tokens]
    except ValueError:
        return None
    top = _proto_fields(data, 0, len(data))
    if top is None:
        return None
    ims = top
    if isinstance(top.get(3), tuple):
        inner = _proto_fields(data, *top[3])
        if inner is not None:
            ims = inner
    if not isinstance(ims.get(1), tuple):
        return None  # cur_method_id missing: not InputMethodManagerService's message
    input_type = 0
    if isinstance(ims.get(7), tuple):
        attr = _proto_fields(data, *ims[7])
        if attr is not None and isinstance(attr.get(1), int):
            input_type = attr[1]
    return ims.get(12) == 1 or input_type != 0


def parse_keyboard_text(text: str) -> bool:
    """Parse the text ``dumpsys input_method`` grep fallback."""
    if _RE_IME_SHOWN.search(text):
        return True
    matches = _RE_IME_FIELD.findall(text)
    if matches:
        try:
            return int(matches[-1], 16) != 0
        except ValueError:
            return False
    return False


def parse_power_reasons(text: str) -> dict[str, Any]:
    """Parse last wake / sleep reasons and active wake locks from ``dumpsys power``."""

    def find(key: str) -> str | None:
        m = re.search(rf"(?m)^\s*{key}=(\S+)", text)
        return m.group(1) if m else None

    wake = find("mLastGlobalWakeReason") or find("mLastWakeReason")
    sleep = find("mLastGlobalSleepReason") or find("mLastSleepReason")
    locks = [
        {"kind": m.group(1).removesuffix("_WAKE_LOCK").lower(), "tag": m.group(2)} for m in _RE_WAKE_LOCK.finditer(text)
    ]
    return {"last_wake_reason": wake, "last_sleep_reason": sleep, "wake_locks": locks}


# Backward compatibility aliases
RE_WAKEFULNESS = _RE_WAKEFULNESS
RE_SCREEN_ON = _RE_SCREEN_ON
RE_FOCUS = _RE_FOCUS
RE_RESUMED_ACTIVITY = _RE_ACTIVITY
