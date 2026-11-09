"""Hardware TV inputs and HDMI-CEC parsing for Android TV."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_RE_HDMI_PORT = re.compile(r"hdmi_port=(\d+)")


def parse_active_hdmi(tv_input: str) -> int | None:
    """Return the active HDMI port from the ``tv_input`` resource profile line."""
    if "ResourceClientProfile" not in tv_input:
        return None
    if m := _RE_HDMI_PORT.search(tv_input):
        return int(m.group(1))
    return None


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
