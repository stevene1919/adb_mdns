"""Audio state and volume parsing for Android TV."""

from __future__ import annotations

import re
from dataclasses import dataclass

_RE_MUSIC_MAX = re.compile(r"Max:\s*(\d+)")
_RE_MUSIC_MUTED = re.compile(r"Muted:\s*(true|false)", re.IGNORECASE)
_RE_MUSIC_DEVICES = re.compile(r"Devices:\s*([^\r\n]+)")
_RE_MUSIC_STREAM_VOL = re.compile(r"streamVolume:\s*(\d+)")
_RE_MUSIC_ANY_VOL = re.compile(r"\):\s*(\d+)")
_RE_VOLUME_GET = re.compile(r"volume is (\d+) in range \[(\d+)\.\.(\d+)\]")

AUDIO_OUTPUT_NAMES: dict[str, str] = {
    "speaker": "TV Speaker",
    "builtin_speaker": "TV Speaker",
    "hdmi": "HDMI",
    "hdmi_arc": "HDMI ARC",
    "hdmi_earc": "HDMI eARC",
    "bt_a2dp": "Bluetooth",
    "bluetooth_a2dp": "Bluetooth",
    "a2dp": "Bluetooth",
    "bt_a2dp_hp": "Bluetooth Headphones",
    "bt_a2dp_spk": "Bluetooth Speaker",
    "bt_sco": "Bluetooth",
    "bluetooth_sco": "Bluetooth",
    "bt_hfp": "Bluetooth",
    "ble_headset": "Bluetooth LE Headset",
    "ble_speaker": "Bluetooth LE Speaker",
    "ble_broadcast": "Bluetooth LE Broadcast",
    "usb_device": "USB Audio",
    "usb_headset": "USB Headset",
    "usb_accessory": "USB Audio",
    "headset": "Headset",
    "wired_headset": "Headset",
    "headphone": "Headphones",
    "wired_headphone": "Headphones",
    "wired_headphones": "Headphones",
    "line": "Line Out",
    "line_out": "Line Out",
    "spdif": "Optical (S/PDIF)",
    "spdif_out": "Optical (S/PDIF)",
    "aux": "AUX",
    "aux_line": "AUX",
    "aux_digital": "AUX Digital",
    "remote_submix": "Cast",
    "submix": "Cast",
    "earpiece": "Earpiece",
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
        """Return human-friendly name of the current active audio output device."""
        if not self.device:
            return None
        first = self.device.split(",")[0].strip()
        # Strip parenthesized device flags / hex bitmasks e.g. "hdmi(400)" -> "hdmi"
        clean = re.sub(r"\(.*?\)", "", first).strip()
        key = clean.lower().replace("-", "_").replace(" ", "_")
        if not key:
            return None
        return AUDIO_OUTPUT_NAMES.get(key, clean.replace("_", " ").title())


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
        clean_first = re.sub(r"\(.*?\)", "", first).strip()
        vol_m = None
        if clean_first:
            vol_m = re.search(r"\(" + re.escape(clean_first) + r"\)[^:\n]*:\s*(\d+)", text) or re.search(
                r"\b" + re.escape(clean_first) + r"\b[^:\n]*:\s*(\d+)",
                text.split("Devices:", 1)[0] if "Devices:" in text else text,
            )
        if vol_m:
            state.volume = int(vol_m.group(1))
    if state.volume is None and (m := _RE_MUSIC_STREAM_VOL.search(text)):
        state.volume = int(m.group(1))
    if state.volume is None and (m := _RE_MUSIC_ANY_VOL.search(text)):
        state.volume = int(m.group(1))
    return state


def parse_volume_get(text: str) -> tuple[int, int, int] | None:
    """Parse ``cmd media_session volume --get`` → ``(volume, min, max)``."""
    if m := _RE_VOLUME_GET.search(text):
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


# Backward compatibility aliases
RE_STREAM_MUSIC_MAX = _RE_MUSIC_MAX
RE_STREAM_MUSIC_MUTED = _RE_MUSIC_MUTED
RE_STREAM_MUSIC_DEV = _RE_MUSIC_DEVICES
RE_STREAM_MUSIC_VOL = _RE_MUSIC_ANY_VOL
