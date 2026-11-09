"""MediaSession and playback parsing for Android TV."""

from __future__ import annotations

import re
from dataclasses import dataclass

PLAYBACK_NONE = 0
PLAYBACK_STOPPED = 1
PLAYBACK_PAUSED = 2
PLAYBACK_PLAYING = 3
PLAYBACK_FAST_FORWARDING = 4
PLAYBACK_REWINDING = 5
PLAYBACK_BUFFERING = 6
PLAYBACK_ERROR = 7

ACTION_STOP = 1 << 0
ACTION_PAUSE = 1 << 1
ACTION_PLAY = 1 << 2
ACTION_REWIND = 1 << 3
ACTION_SKIP_TO_PREVIOUS = 1 << 4
ACTION_SKIP_TO_NEXT = 1 << 5
ACTION_FAST_FORWARD = 1 << 6
ACTION_SEEK_TO = 1 << 8
ACTION_PLAY_PAUSE = 1 << 9

_RE_SESSION_PKG = re.compile(r"^\s*package=([\w.]+)")
_RE_SESSION_ACTIVE = re.compile(r"^\s*active=(true|false)")
_RE_PB_STATE = re.compile(r"state=PlaybackState\s*\{(.*)\}")
_RE_PB_FIELD = {
    "state": re.compile(r"(?:^|[\s,{])state=(-?\d+)"),
    "position": re.compile(r"position=(-?\d+)"),
    "speed": re.compile(r"speed=(-?[\d.]+)"),
    "updated": re.compile(r"updated=(-?\d+)"),
    "actions": re.compile(r"actions=(\d+)"),
}
_RE_METADATA = re.compile(r"metadata:\s*(?:size=\d+,\s*)?description=(.*)$")


@dataclass
class MediaSession:
    """A media session from ``dumpsys media_session``."""

    package: str
    active: bool = False
    state: int | None = None
    position_ms: int | None = None
    speed: float = 0.0
    updated_ms: int | None = None
    actions: int = 0
    title: str | None = None
    artist: str | None = None
    album: str | None = None

    @property
    def is_playing(self) -> bool:
        return self.state in (PLAYBACK_PLAYING, PLAYBACK_FAST_FORWARDING, PLAYBACK_REWINDING, PLAYBACK_BUFFERING)


def _clean_meta(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() == "null":
        return None
    return value


def _split_description(desc: str) -> tuple[str | None, str | None, str | None]:
    """Split ``MediaDescription.toString()`` (``title, subtitle, description``).

    Titles may contain ``", "``: the last two parts are taken as subtitle and
    description, the rest is the title.
    """
    parts = desc.split(", ")
    if len(parts) >= 3:
        title = ", ".join(parts[:-2])
        return _clean_meta(title), _clean_meta(parts[-2]), _clean_meta(parts[-1])
    if len(parts) == 2:
        return _clean_meta(parts[0]), _clean_meta(parts[1]), None
    return _clean_meta(parts[0]), None, None


def parse_media_sessions(text: str) -> list[MediaSession]:
    """Parse the (grep-filtered) ``dumpsys media_session`` output."""
    sessions: list[MediaSession] = []
    current: MediaSession | None = None
    for line in text.splitlines():
        if m := _RE_SESSION_PKG.match(line):
            current = MediaSession(package=m.group(1))
            sessions.append(current)
            continue
        if current is None and _RE_PB_STATE.search(line):
            current = MediaSession(package="")
            sessions.append(current)
        if current is None:
            continue
        if m := _RE_SESSION_ACTIVE.match(line):
            current.active = m.group(1) == "true"
        elif m := _RE_PB_STATE.search(line):
            body = "{" + m.group(1)
            if s := _RE_PB_FIELD["state"].search(body):
                current.state = int(s.group(1))
            if s := _RE_PB_FIELD["position"].search(body):
                current.position_ms = int(s.group(1))
            if s := _RE_PB_FIELD["speed"].search(body):
                try:
                    current.speed = float(s.group(1))
                except ValueError:
                    current.speed = 0.0
            if s := _RE_PB_FIELD["updated"].search(body):
                current.updated_ms = int(s.group(1))
            if s := _RE_PB_FIELD["actions"].search(body):
                current.actions = int(s.group(1))
        elif m := _RE_METADATA.search(line):
            current.title, current.artist, current.album = _split_description(m.group(1))
    return sessions


def pick_media_session(sessions: list[MediaSession], foreground: str | None) -> MediaSession | None:
    """Pick the session that best describes what's on screen."""
    if not sessions:
        return None
    if foreground:
        for session in sessions:
            if session.package == foreground and session.active:
                return session
        for session in sessions:
            if session.package == foreground and session.state is not None:
                return session
    for session in sessions:
        if session.active and session.is_playing:
            return session
    # Background audio (e.g. Spotify playing behind the launcher).
    for session in sessions:
        if session.is_playing:
            return session
    return None


def current_position(session: MediaSession, uptime_ms: int | None) -> float | None:
    """Extrapolate the playback position (seconds) to the device's ``uptime_ms``."""
    if session.position_ms is None or session.position_ms < 0:
        return None
    position = float(session.position_ms)
    if (
        uptime_ms is not None
        and session.updated_ms
        and session.state == PLAYBACK_PLAYING
        and session.speed
        and uptime_ms >= session.updated_ms
    ):
        position += (uptime_ms - session.updated_ms) * session.speed
    return max(0.0, position / 1000.0)


def parse_uptime_ms(text: str) -> int | None:
    """Parse ``/proc/uptime`` (seconds since boot) into milliseconds."""
    m = re.search(r"^\s*([\d.]+)", text)
    if not m:
        return None
    try:
        return int(float(m.group(1)) * 1000)
    except ValueError:
        return None


# Backward compatibility aliases
RE_MEDIA_SESSION_STATE = _RE_PB_STATE
