"""Pure parsers for ``dumpsys`` / shell output (Layer 1).

Every function here is side-effect free and never raises on unexpected input:
``dumpsys`` is not a stable format, so a parser takes what it can find and
returns ``None`` / empty results otherwise.

Several parsers are Python ports of the pure-shell readers in tv-remote
(``Foreground.kt``, ``TvKeyboard.kt``, ``Inputs.kt``, ``Recents.kt``,
``Sensors.kt``, ``Power.kt``; MIT licensed, Copyright (c) 2026 Hoang Tran).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SECTION_PREFIX = "##"


# --------------------------------------------------------------------------- sections


def split_sections(output: str) -> dict[str, str]:
    """Split output produced by ``echo '##NAME'; <cmd>`` blocks into a dict."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in output.splitlines():
        line = raw.rstrip("\r")
        stripped = line.strip()
        if stripped.startswith(SECTION_PREFIX) and re.fullmatch(r"##[A-Z_]+", stripped):
            current = stripped[len(SECTION_PREFIX) :]
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def parse_kv(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines. Empty / ``null`` values become ``""``."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or " " in key:
            continue
        value = value.strip()
        out[key] = "" if value.lower() == "null" else value
    return out


# --------------------------------------------------------------------------- device info


_RE_LINK = re.compile(r"^\d+:\s+([\w.@-]+?)(?:@\S+)?:\s.*?link/ether\s+([0-9a-fA-F:]{17})")
_RE_ADDR = re.compile(r"^\d+:\s+([\w.@-]+?)\s+inet\s+([\d.]+)/")


def parse_device_properties(output: str, host: str | None = None) -> dict[str, str]:
    """Parse the labelled device-info command output.

    Empty properties stay empty and never shift other fields (the old
    positional parser's bug).
    """
    sections = split_sections(output)
    kv = parse_kv(sections.get("PROPS", ""))
    macs: dict[str, str] = {}
    for line in sections.get("LINK", "").splitlines():
        if m := _RE_LINK.search(line.strip()):
            mac = m.group(2).lower()
            if mac != "00:00:00:00:00:00":
                macs[m.group(1)] = mac
    iface_for_host: str | None = None
    for line in sections.get("ADDR", "").splitlines():
        if (m := _RE_ADDR.search(line.strip())) and host and m.group(2) == host:
            iface_for_host = m.group(1)
            break
    mac = ""
    if iface_for_host and iface_for_host in macs:
        mac = macs[iface_for_host]
    else:
        for iface in ("eth0", "wlan0"):
            if iface in macs:
                mac = macs[iface]
                break
    return {
        "name": kv.get("NAME", ""),
        "manufacturer": kv.get("MFG", ""),
        "model": kv.get("MODEL", ""),
        "sw_version": kv.get("VER", ""),
        "sdk": kv.get("SDK", ""),
        "serialno": kv.get("SERIAL", ""),
        "build": kv.get("BUILD", ""),
        "mac": mac,
        "interface": iface_for_host or "",
    }


def parse_packages(output: str) -> list[str]:
    """Parse ``pm list packages`` output into a sorted package list."""
    pkgs = {
        line.strip()[len("package:") :].strip() for line in output.splitlines() if line.strip().startswith("package:")
    }
    return sorted(p for p in pkgs if p)


# --------------------------------------------------------------------------- power / foreground


_RE_WAKEFULNESS = re.compile(r"mWakefulness=([A-Za-z]+)")
_RE_SCREEN_ON = re.compile(r"(?:Display Power: state=ON|mScreenOn=true|mScreenState=ON)")
_RE_SCREEN_OFF = re.compile(r"(?:Display Power: state=OFF|mScreenOn=false|mScreenState=OFF)")
_RE_ACTIVITY = re.compile(r"(?:mResumedActivity|topResumedActivity|ResumedActivity)[:=].*?\bu\d+\s+([\w.]+)/")
_RE_FOCUS = re.compile(r"mCurrentFocus=Window\{[0-9a-fA-F]+\s+(?:u\d+\s+)?([\w.]+)/")
_RE_DREAMING = re.compile(r"(?:mWakefulness=Dreaming|isDreaming=true|mDreaming=true)")


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


# --------------------------------------------------------------------------- media session

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


# --------------------------------------------------------------------------- audio


_RE_MUSIC_MAX = re.compile(r"Max:\s*(\d+)")
_RE_MUSIC_MUTED = re.compile(r"Muted:\s*(true|false)", re.IGNORECASE)
_RE_MUSIC_DEVICES = re.compile(r"Devices:\s*([^\r\n]+)")
_RE_MUSIC_ANY_VOL = re.compile(r"\):\s*(\d+)")

AUDIO_OUTPUT_NAMES: dict[str, str] = {
    "speaker": "Speaker",
    "hdmi": "HDMI",
    "hdmi_arc": "HDMI ARC",
    "hdmi_earc": "HDMI eARC",
    "bt_a2dp": "Bluetooth",
    "bt_a2dp_hp": "Bluetooth",
    "bt_a2dp_spk": "Bluetooth",
    "bt_sco": "Bluetooth",
    "bt_hfp": "Bluetooth",
    "ble_headset": "Bluetooth LE",
    "ble_speaker": "Bluetooth LE",
    "ble_broadcast": "Bluetooth LE",
    "usb_device": "USB Audio",
    "usb_headset": "USB Audio",
    "usb_accessory": "USB Audio",
    "headset": "Headphones",
    "headphone": "Headphones",
    "line": "Line Out",
    "spdif": "Optical (S/PDIF)",
    "aux_line": "Line Out",
    "remote_submix": "Cast",
}


@dataclass
class AudioState:
    """Parsed ``STREAM_MUSIC`` state."""

    max_volume: int | None = None
    volume: int | None = None
    muted: bool | None = None
    device: str | None = None

    @property
    def output_name(self) -> str | None:
        if not self.device:
            return None
        first = self.device.split(",")[0].strip()
        key = first.lower()
        return AUDIO_OUTPUT_NAMES.get(key, first.replace("_", " ").title())


def parse_audio(text: str) -> AudioState:
    """Parse the ``dumpsys audio`` ``STREAM_MUSIC`` block."""
    state = AudioState()
    if m := _RE_MUSIC_MAX.search(text):
        state.max_volume = int(m.group(1))
    if m := _RE_MUSIC_MUTED.search(text):
        state.muted = m.group(1).lower() == "true"
    if m := _RE_MUSIC_DEVICES.search(text):
        state.device = m.group(1).strip()
    if state.device:
        first = state.device.split(",")[0].strip()
        vol_m = re.search(r"\(" + re.escape(first) + r"\)[^:\n]*:\s*(\d+)", text) or re.search(
            re.escape(first) + r"[^\n]*?:\s*(\d+)", text.split("Devices:", 1)[-1] if "Devices:" in text else text
        )
        if vol_m:
            state.volume = int(vol_m.group(1))
    if state.volume is None and (m := _RE_MUSIC_ANY_VOL.search(text)):
        state.volume = int(m.group(1))
    return state


_RE_VOLUME_GET = re.compile(r"volume is (\d+) in range \[(\d+)\.\.(\d+)\]")


def parse_volume_get(text: str) -> tuple[int, int, int] | None:
    """Parse ``cmd media_session volume --get`` → ``(volume, min, max)``."""
    if m := _RE_VOLUME_GET.search(text):
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


# --------------------------------------------------------------------------- HDMI input (active)


_RE_HDMI_PORT = re.compile(r"hdmi_port=(\d+)")


def parse_active_hdmi(tv_input: str) -> int | None:
    """Return the active HDMI port from the ``tv_input`` resource profile line."""
    if "ResourceClientProfile" not in tv_input:
        return None
    if m := _RE_HDMI_PORT.search(tv_input):
        return int(m.group(1))
    return None


# --------------------------------------------------------------------------- keyboard (TvKeyboard.kt)


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


_RE_IME_SHOWN = re.compile(r"\bmInputShown=true\b")
_RE_IME_FIELD = re.compile(r"\binputType=0x([0-9a-fA-F]+)\b.*\bfieldId=")


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


# --------------------------------------------------------------------------- inputs (Inputs.kt)

INPUT_SEPARATOR = "#--tvr-inputs--"
INPUT_TUNER = "tuner"

_INPUT_TYPES = {
    2: "tuner",
    3: "av",
    6: "component",
    7: "vga",
    8: "other",
    9: "hdmi",
    10: "other",
    1001: "av",
    1004: "component",
    1005: "vga",
    1006: "other",
    1007: "hdmi",
    1008: "other",
    0: "tuner",
}
_RE_INPUT_ID = re.compile(r"TvInputInfo\{id=([^,}\s]+)")
_RE_INPUT_HW = re.compile(r"(?:/|\bHW)(?:HW)?(\d+)$")
_RE_HW_INFO = re.compile(r"TvInputHardwareInfo\s*\{([^}]*)\}")
_RE_INFO_TYPE = re.compile(r"\btype=(\d+)")
_RE_INFO_ID = re.compile(r"\bid=(\d+)")
_RE_INFO_PORT = re.compile(r"hdmi_port(?:_id)?=(\d+)")
_RE_INFO_CABLE = re.compile(r"cable_connection_status=(\d+)")
_RE_CEC_NAME = re.compile(
    r"display_?name[:=]\s*(.*?)(?=\s+(?:power_?status|physical_?address|port_?id|device_?type|vendor_?id|"
    r"logical_?address|cec_?version|status|device_?power_?status|adopt)\b|\s*[,}]|\s*$)",
    re.IGNORECASE,
)
_RE_CEC_PHYS = re.compile(r"physical_?address[:=]\s*(?:0x)?([0-9a-fA-F]{4})", re.IGNORECASE)
_RE_CEC_PORT = re.compile(r"\bport_?id[:=]\s*(\d+)", re.IGNORECASE)
_RE_CEC_LOGICAL = re.compile(r"logical_?address[:=]\s*(?:0x)?([0-9a-fA-F]{1,2})", re.IGNORECASE)
_SAFE_INPUT_ID = re.compile(r"[A-Za-z0-9_.:/$-]{1,200}")


@dataclass
class TvInput:
    """A switchable hardware input."""

    id: str
    kind: str
    port: int
    device: str
    label: str
    connected: bool | None = None
    key: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "port": self.port,
            "device": self.device,
            "label": self.label,
            "connected": self.connected,
        }


def input_fallback_key(kind: str, n: int) -> int:
    """KEYCODE_TV_INPUT_* for an input kind / number (0 if none)."""
    if kind == "hdmi":
        return 242 + n if 1 <= n <= 4 else 0
    if kind == "av":
        return 246 + n if 1 <= n <= 2 else 0
    if kind == "component":
        return 248 + n if 1 <= n <= 2 else 0
    if kind == "vga":
        return 251
    return 0


def _cec_devices(text: str) -> list[tuple[str, int, int]]:
    devices: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        lowered = line.lower()
        if "display_name" not in lowered and "displayname" not in lowered:
            continue
        m = _RE_CEC_NAME.search(line)
        if not m:
            continue
        name = m.group(1).strip().strip("\"'")
        if not name or name.lower() == "null":
            continue
        logical_m = _RE_CEC_LOGICAL.search(line)
        logical = int(logical_m.group(1), 16) if logical_m else None
        if logical in (0, 15):
            continue
        phys_m = _RE_CEC_PHYS.search(line)
        phys = int(phys_m.group(1), 16) if phys_m else 0
        port_m = _RE_CEC_PORT.search(line)
        port = int(port_m.group(1)) if port_m else 0
        if port == 0 and phys == 0:
            continue
        key = f"{name}/{phys}/{port}"
        if key not in seen:
            seen.add(key)
            devices.append((name, port, phys))
    return devices


def _cec_for_port(devices: list[tuple[str, int, int]], port: int) -> str:
    on_port = [d for d in devices if d[1] == port or (d[2] > 0 and d[2] >> 12 == port)]
    direct = [d for d in on_port if d[2] & 0x0FFF == 0]
    chosen = (direct or on_port or [None])[0]
    return chosen[0] if chosen else ""


def parse_tv_inputs(output: str, with_cec: bool = True) -> list[TvInput]:
    """Parse ``dumpsys tv_input; echo SEP; dumpsys hdmi_control`` into inputs."""
    try:
        return _parse_tv_inputs(output, with_cec)
    except Exception:
        return []


def _parse_tv_inputs(output: str, with_cec: bool) -> list[TvInput]:
    at = output.find(INPUT_SEPARATOR)
    tv_input = output if at < 0 else output[:at]
    cec_text = "" if at < 0 else output[at + len(INPUT_SEPARATOR) :]

    hw: dict[int, tuple[str, int, bool | None]] = {}
    for m in _RE_HW_INFO.finditer(tv_input):
        body = m.group(1)
        id_m = _RE_INFO_ID.search(body)
        type_m = _RE_INFO_TYPE.search(body)
        if not id_m or not type_m:
            continue
        kind = _INPUT_TYPES.get(int(type_m.group(1)), "other")
        port_m = _RE_INFO_PORT.search(body)
        cable_m = _RE_INFO_CABLE.search(body)
        cable = int(cable_m.group(1)) if cable_m else None
        hw[int(id_m.group(1))] = (
            kind,
            int(port_m.group(1)) if port_m else 0,
            True if cable == 1 else False if cable == 2 else None,
        )
    cec = _cec_devices(cec_text) if with_cec else []

    ids: list[str] = []
    for m in _RE_INPUT_ID.finditer(tv_input):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    for line in tv_input.splitlines():
        key = line.strip().split(":", 1)[0].strip()
        if "/" in key and " " not in key and _RE_INPUT_HW.search(key) and key not in ids:
            ids.append(key)

    raw: list[tuple[str, str, int, bool | None]] = []
    tuner = False
    for input_id in ids:
        hw_m = _RE_INPUT_HW.search(input_id)
        n = int(hw_m.group(1)) if hw_m else None
        info = hw.get(n) if n is not None else None
        lower = input_id.lower()
        kind: str | None
        if info:
            kind = info[0]
        elif "hdmi" in lower:
            kind = "hdmi"
        elif "composite" in lower or lower.endswith("av") or "/av" in lower:
            kind = "av"
        elif "component" in lower:
            kind = "component"
        elif "vga" in lower:
            kind = "vga"
        elif n is not None:
            kind = "other"
        else:
            kind = None
        if kind is None:
            if any(t in lower for t in ("tuner", "dtv", "atsc", "dvb")):
                tuner = True
            continue
        if kind == "tuner":
            tuner = True
            continue
        port = info[1] if info and info[1] > 0 else 0
        if not port and (pm := re.search(r"hdmi_?(\d)", lower)):
            port = int(pm.group(1))
        raw.append((input_id, kind, port, info[2] if info else None))

    if not raw:
        return []

    seen: dict[str, int] = {}
    used = {r[2] for r in raw if r[1] == "hdmi" and r[2] > 0}
    result: list[TvInput] = []
    counts: dict[str, int] = {}
    for r in raw:
        counts[r[1]] = counts.get(r[1], 0) + 1
    for input_id, kind, port, connected in sorted(raw, key=lambda r: (r[1] != "hdmi", r[2] == 0, r[2])):
        nth = seen.get(kind, 0) + 1
        seen[kind] = nth
        if kind == "hdmi" and port == 0:
            port = nth
            while port in used:
                port += 1
            used.add(port)
        device = _cec_for_port(cec, port) if kind == "hdmi" else ""
        if kind == "hdmi":
            base = f"HDMI {port}"
        elif kind == "av":
            base = f"AV {nth}" if counts["av"] > 1 else "AV"
        elif kind == "component":
            base = f"Component {nth}" if counts["component"] > 1 else "Component"
        elif kind == "vga":
            base = "VGA"
        else:
            base = f"Input {nth}"
        label = f"{base} · {device}" if device else base
        result.append(
            TvInput(
                id=input_id,
                kind=kind,
                port=port if kind == "hdmi" else 0,
                device=device,
                label=label,
                connected=connected,
                key=input_fallback_key(kind, port if kind == "hdmi" else nth),
            )
        )
    if tuner:
        result.append(TvInput(id=INPUT_TUNER, kind="tuner", port=0, device="", label="TV", key=170))
    return result


def valid_input_id(input_id: str) -> bool:
    """Return True if an input id is safe to pass to the shell."""
    return bool(_SAFE_INPUT_ID.fullmatch(input_id))


def input_passthrough_uri(input_id: str) -> str:
    """Live TV passthrough URI for a hardware input id."""
    encoded = input_id.replace("%", "%25").replace("/", "%2F").replace("$", "%24")
    return f"content://android.media.tv/passthrough/{encoded}"


def am_start_failed(output: str) -> bool:
    """Return True if ``am start`` output reports a failure."""
    lowered = output.lower()
    return any(s in lowered for s in ("error", "exception", "unable to resolve", "no activity found"))


# --------------------------------------------------------------------------- recents (Recents.kt)

_RE_RECENT_HEAD = re.compile(r"\* Recent #\d+: Task(?:Record)?\{\S+ #(\d+)([^}]*)\}")
_RE_RECENT_TYPE = re.compile(r"\btype=(\w+)")
_RE_RECENT_AFF = re.compile(r"\b[AI]=(?:\d+:)?([A-Za-z][\w.]*)")
_RE_RECENT_COMP = re.compile(r"^\s*(?:mActivityComponent|realActivity)=([A-Za-z][\w.]*)/", re.MULTILINE)
_RE_RECENT_EMPTY = re.compile(r"\bStackId=-1 sz=0\b")


@dataclass
class RecentTask:
    """An open app task."""

    task_id: int
    package: str
    running: bool | None = None
    home: bool = False


def parse_recents(output: str) -> list[RecentTask]:
    """Parse ``dumpsys activity recents`` into open (non-system) app tasks."""
    tasks: list[RecentTask] = []
    for block in re.split(r"(?=\n\s*\* Recent #)", "\n" + output):
        head = _RE_RECENT_HEAD.search(block)
        if not head:
            continue
        task_id = int(head.group(1))
        rest = head.group(2)
        type_m = _RE_RECENT_TYPE.search(rest)
        task_type = type_m.group(1) if type_m else None
        comp = _RE_RECENT_COMP.search(block)
        aff = _RE_RECENT_AFF.search(rest)
        pkg = comp.group(1) if comp else (aff.group(1) if aff else None)
        if not pkg:
            continue
        home = task_type == "home" or "android.intent.category.HOME" in block
        system = task_type is not None and task_type not in ("standard", "undefined", "home")
        if system or _RE_RECENT_EMPTY.search(rest):
            continue
        running: bool | None = None
        if "mRootProcess=null" in block:
            running = False
        elif "mRootProcess=ProcessRecord" in block:
            running = True
        tasks.append(RecentTask(task_id=task_id, package=pkg, running=running, home=home))
    return tasks


def open_apps(tasks: list[RecentTask]) -> list[str]:
    """Return de-duplicated open app packages (no home screens)."""
    seen: list[str] = []
    for task in tasks:
        if task.home or task.package in seen:
            continue
        seen.append(task.package)
    return seen


# --------------------------------------------------------------------------- health (Sensors.kt / Meminfo.kt / Power.kt)

_HAL_TYPES = {
    0: "CPU",
    1: "GPU",
    2: "battery",
    3: "skin",
    4: "USB",
    5: "amplifier",
    9: "NPU",
    10: "TPU",
    11: "display",
    12: "modem",
    13: "SoC",
    14: "Wi-Fi",
    18: "ambient",
}
_RE_HAL_TEMP = re.compile(r"Temperature\{mValue=(-?[\d.]+), mType=(-?\d+), mName=([^,}]*)")
_RE_THERMAL_STATUS = re.compile(r"Thermal Status: (\d)")


@dataclass
class ThermalState:
    """Thermal readings."""

    status: int | None = None
    temperatures: dict[str, float] = field(default_factory=dict)

    @property
    def max_temperature(self) -> float | None:
        return max(self.temperatures.values()) if self.temperatures else None


def parse_thermal(hal: str, zones: str) -> ThermalState | None:
    """Parse ``dumpsys thermalservice`` HAL temps, falling back to thermal zones."""
    state = ThermalState()
    if m := _RE_THERMAL_STATUS.search(hal):
        state.status = int(m.group(1))
    for m in _RE_HAL_TEMP.finditer(hal):
        try:
            celsius = float(m.group(1))
        except ValueError:
            continue
        type_name = _HAL_TYPES.get(int(m.group(2)))
        if type_name is None or type_name == "battery":
            continue
        name = m.group(3).strip() or type_name
        if -30 < celsius < 150:
            state.temperatures.setdefault(name, round(celsius, 1))
    if not state.temperatures:
        for line in zones.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            try:
                value = int(parts[1])
            except ValueError:
                continue
            celsius = value / 1000.0 if abs(value) > 1000 else float(value)
            if -30 < celsius < 150 and celsius != 0.0:
                state.temperatures.setdefault(parts[0], round(celsius, 1))
    if state.status is None and not state.temperatures:
        return None
    return state


def parse_meminfo(text: str) -> tuple[int, int] | None:
    """Return ``(total_kb, available_kb)`` from ``/proc/meminfo``."""
    total = avail = None
    for line in text.splitlines():
        if m := re.match(r"\s*MemTotal:\s*(\d+)", line):
            total = int(m.group(1))
        elif m := re.match(r"\s*MemAvailable:\s*(\d+)", line):
            avail = int(m.group(1))
    if total and avail is not None:
        return total, avail
    return None


def parse_storage(text: str) -> tuple[int, int] | None:
    """Parse ``stat -f -c '%a %b %S' /data`` → ``(available_bytes, total_bytes)``."""
    nums = re.findall(r"\d+", text)
    if len(nums) < 3:
        return None
    avail_blocks, total_blocks, block_size = (int(n) for n in nums[:3])
    return avail_blocks * block_size, total_blocks * block_size


def parse_cpu_times(text: str) -> tuple[int, int] | None:
    """Parse the first ``/proc/stat`` line → ``(busy_jiffies, total_jiffies)``."""
    for line in text.splitlines():
        if line.startswith("cpu "):
            values = [int(v) for v in line.split()[1:] if v.isdigit()]
            if len(values) < 4:
                return None
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values[:8])
            return total - idle, total
    return None


def cpu_percent(prev: tuple[int, int] | None, cur: tuple[int, int] | None) -> float | None:
    """CPU load between two ``/proc/stat`` samples."""
    if not prev or not cur:
        return None
    d_busy = cur[0] - prev[0]
    d_total = cur[1] - prev[1]
    if d_total <= 0 or d_busy < 0:
        return None
    return round(100.0 * d_busy / d_total, 1)


_RE_WAKE_LOCK = re.compile(
    r"^\s*(PARTIAL_WAKE_LOCK|FULL_WAKE_LOCK|SCREEN_\w+_WAKE_LOCK|DOZE_WAKE_LOCK|DRAW_WAKE_LOCK)\s+'([^']*)'",
    re.MULTILINE,
)


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


_RE_BT_ADDR = re.compile(r"([0-9A-FX]{2}(?::[0-9A-FX]{2}){5})", re.IGNORECASE)


def parse_bluetooth(bt: str, inputs: str) -> dict[str, Any] | None:
    """Parse ``bluetooth_manager`` bonded devices and Bluetooth input devices."""
    on_m = re.search(r"enabled:\s*(\w+)", bt)
    if not on_m:
        return None
    devices: dict[str, dict[str, Any]] = {}
    bonded = bt.split("Bonded devices:", 1)[1] if "Bonded devices:" in bt else ""
    for line in bonded.splitlines():
        m = _RE_BT_ADDR.search(line)
        if not m:
            continue
        name = re.sub(r"\[[^\]]*\]", "", line[m.end() :]).strip()
        addr = m.group(1).upper()
        devices[addr] = {"name": name or addr, "address": addr, "connected": False}
    for line in inputs.splitlines():
        if "|" not in line:
            continue
        name = re.sub(r"\s*\(aka .*\)$", "", line.split("|", 1)[0]).strip()
        addr_m = re.search(r"bluetoothAddress=([0-9A-Fa-f:]{17})", line)
        addr = addr_m.group(1).upper() if addr_m else None
        known = devices.get(addr) if addr else None
        if known is None:
            known = next((d for d in devices.values() if d["name"] == name), None)
        if known is not None:
            known["connected"] = True
        else:
            devices[addr or name] = {"name": name, "address": addr or "", "connected": True}
    return {"enabled": on_m.group(1).lower() == "true", "devices": list(devices.values())}


# --------------------------------------------------------------------------- settings


def parse_float_setting(value: str | None, default: float | None = None) -> float | None:
    """Parse a ``settings get`` float/int value (``null`` → default)."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


# Backward compatibility aliases
RE_WAKEFULNESS = _RE_WAKEFULNESS
RE_SCREEN_ON = _RE_SCREEN_ON
RE_FOCUS = _RE_FOCUS
RE_RESUMED_ACTIVITY = _RE_ACTIVITY
RE_MEDIA_SESSION_STATE = _RE_PB_STATE
RE_STREAM_MUSIC_MAX = _RE_MUSIC_MAX
RE_STREAM_MUSIC_MUTED = _RE_MUSIC_MUTED
RE_STREAM_MUSIC_DEV = _RE_MUSIC_DEVICES
RE_STREAM_MUSIC_VOL = _RE_MUSIC_ANY_VOL
