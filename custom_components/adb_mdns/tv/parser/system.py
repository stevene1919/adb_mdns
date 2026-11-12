"""System properties, recents, thermal, meminfo, and storage parsing for Android TV."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SECTION_PREFIX = "##"


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


_RE_LINK = re.compile(r"^\d+:\s+([\w.@-]+?)(?:@\S+)?:\s.*?link/ether\s+([0-9a-fA-F:]{17})")
_RE_ADDR = re.compile(r"^\d+:\s+([\w.@-]+?)\s+inet\s+([\d.]+)/")
_RE_WIFI_MAC = re.compile(r"(?:wifi_sta_factory_mac_address=|MAC:\s*)([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})")


def parse_device_properties(output: str, host: str | None = None) -> dict[str, str]:
    """Parse the labelled device-info command output."""
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
    if not mac:
        for line in sections.get("WIFI_MAC", "").splitlines():
            if m := _RE_WIFI_MAC.search(line):
                candidate = m.group(1).lower()
                if candidate not in ("00:00:00:00:00:00", "02:00:00:00:00:00"):
                    mac = candidate
                    if not iface_for_host:
                        iface_for_host = "wlan0"
                    break
    return {
        "name": kv.get("NAME", ""),
        "manufacturer": kv.get("MFG", ""),
        "model": kv.get("MODEL", ""),
        "sw_version": kv.get("VER", ""),
        "sdk": kv.get("SDK", ""),
        "serialno": kv.get("SERIAL", ""),
        "build": kv.get("BUILD", ""),
        "hdmi_device_type": kv.get("HDMI_TYPE", ""),
        "mac": mac,
        "interface": iface_for_host or "",
    }


def parse_packages(output: str) -> list[str]:
    """Parse ``pm list packages`` output into a sorted package list."""
    pkgs = {
        line.strip()[len("package:") :].strip() for line in output.splitlines() if line.strip().startswith("package:")
    }
    return sorted(p for p in pkgs if p)


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


_RE_BT_ADDR = re.compile(r"([0-9A-FX]{2}(?::[0-9A-FX]{2}){5})", re.IGNORECASE)
_RE_BT_A2DP_SM = re.compile(r"(?:===\s*)?A2dpStateMachine for ([0-9A-FX:]{17})", re.IGNORECASE)
_RE_BT_HID_STATE = re.compile(r"^\s*([0-9A-FX:]{17})\s*:\s*(\d+)\s*$", re.IGNORECASE)


def _match_bt_device(devices: dict[str, dict[str, Any]], addr_or_masked: str) -> dict[str, Any] | None:
    """Match a full or XX-redacted Bluetooth address against bonded devices."""
    upper = addr_or_masked.upper()
    if upper in devices:
        return devices[upper]
    suffix = upper[-5:]
    if len(suffix) == 5 and "X" not in suffix:
        matches = [d for a, d in devices.items() if a.endswith(suffix)]
        if len(matches) == 1:
            return matches[0]
    return None


def parse_bluetooth(bt: str, inputs: str) -> dict[str, Any] | None:
    """Parse ``bluetooth_manager`` bonded devices, profile types, and connection states."""
    on_m = re.search(r"enabled:\s*(\w+)", bt)
    if not on_m:
        return None
    devices: dict[str, dict[str, Any]] = {}
    bonded_block = bt.split("Bonded devices:", 1)[1] if "Bonded devices:" in bt else ""
    for line in bonded_block.splitlines():
        if line and not line.startswith(" ") and not line.startswith("\t"):
            break
        m = _RE_BT_ADDR.search(line)
        if not m:
            continue
        addr = m.group(1).upper()
        if "X" in addr:
            continue
        name = re.sub(r"\[[^\]]*\]", "", line[m.end() :]).strip()
        devices[addr] = {"name": name or addr, "address": addr, "connected": False, "type": "other"}

    # Parse profile policies, A2dpStateMachine, mActiveDevice, and HidHostService states
    current_a2dp_dev: dict[str, Any] | None = None
    for line in bt.splitlines():
        if "profile connection policy(" in line and (m := _RE_BT_ADDR.search(line)):
            dev = _match_bt_device(devices, m.group(1))
            if dev is not None:
                if any(p in line for p in ("A2DP=100", "HEADSET=100", "LE_AUDIO=100", "HEARING_AID=100")):
                    dev["type"] = "audio"
                elif "HID_HOST=100" in line and dev.get("type") == "other":
                    dev["type"] = "input"
        elif m := _RE_BT_A2DP_SM.search(line):
            current_a2dp_dev = _match_bt_device(devices, m.group(1))
            if current_a2dp_dev is not None and current_a2dp_dev.get("type") == "other":
                current_a2dp_dev["type"] = "audio"
        elif current_a2dp_dev is not None and (
            "mConnectionState: CONNECTED" in line or "StateMachine: name=A2dpStateMachine state=Connected" in line
        ):
            current_a2dp_dev["connected"] = True
        elif "mActiveDevice:" in line and (m := _RE_BT_ADDR.search(line)):
            dev = _match_bt_device(devices, m.group(1))
            if dev is not None:
                dev["connected"] = True
                if dev.get("type") == "other":
                    dev["type"] = "audio"
        elif m := _RE_BT_HID_STATE.match(line):
            dev = _match_bt_device(devices, m.group(1))
            if dev is not None:
                if int(m.group(2)) == 2:
                    dev["connected"] = True
                if dev.get("type") == "other":
                    dev["type"] = "input"

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
            if known.get("type") == "other":
                known["type"] = "input"
        else:
            devices[addr or name] = {"name": name, "address": addr or "", "connected": True, "type": "input"}
    return {"enabled": on_m.group(1).lower() == "true", "devices": list(devices.values())}


def parse_float_setting(value: str | None, default: float | None = None) -> float | None:
    """Parse a ``settings get`` float/int value (``null`` → default)."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default
