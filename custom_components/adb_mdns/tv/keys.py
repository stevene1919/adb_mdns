"""Android keycodes and case-insensitive key name resolution.

Keycodes follow ``android.view.KeyEvent``. The named set extends the original
integration's list with the Android TV / Google TV remote keys used by
tv-remote (``Scenes.KEYS``, MIT licensed).
"""

from __future__ import annotations

KEY_POWER = 26
KEY_SLEEP = 223
KEY_WAKEUP = 224
KEY_HOME = 3
KEY_BACK = 4
KEY_MENU = 82
KEY_DPAD_UP = 19
KEY_DPAD_DOWN = 20
KEY_DPAD_LEFT = 21
KEY_DPAD_RIGHT = 22
KEY_DPAD_CENTER = 23
KEY_ENTER = 66
KEY_VOLUME_UP = 24
KEY_VOLUME_DOWN = 25
KEY_VOLUME_MUTE = 164
KEY_MEDIA_PLAY_PAUSE = 85
KEY_MEDIA_STOP = 86
KEY_MEDIA_NEXT = 87
KEY_MEDIA_PREVIOUS = 88
KEY_MEDIA_REWIND = 89
KEY_MEDIA_FAST_FORWARD = 90
KEY_PLAY = 126
KEY_PAUSE = 127
KEY_TV = 170

# Canonical names (lower-case). Aliases point at the same codes.
_KEYS: dict[str, int] = {
    # Power
    "power": KEY_POWER,
    "sleep": KEY_SLEEP,
    "wakeup": KEY_WAKEUP,
    # Navigation
    "home": KEY_HOME,
    "back": KEY_BACK,
    "menu": KEY_MENU,
    "up": KEY_DPAD_UP,
    "down": KEY_DPAD_DOWN,
    "left": KEY_DPAD_LEFT,
    "right": KEY_DPAD_RIGHT,
    "center": KEY_DPAD_CENTER,
    "enter": KEY_ENTER,
    "del": 67,
    "tab": 61,
    "escape": 111,
    "settings": 176,
    "search": 84,
    "assist": 219,
    "all_apps": 284,
    "app_switch": 187,
    "notification": 83,
    # Volume
    "volume_up": KEY_VOLUME_UP,
    "volume_down": KEY_VOLUME_DOWN,
    "mute": KEY_VOLUME_MUTE,
    # Media
    "play_pause": KEY_MEDIA_PLAY_PAUSE,
    "play": KEY_PLAY,
    "pause": KEY_PAUSE,
    "stop": KEY_MEDIA_STOP,
    "next": KEY_MEDIA_NEXT,
    "previous": KEY_MEDIA_PREVIOUS,
    "rewind": KEY_MEDIA_REWIND,
    "fast_forward": KEY_MEDIA_FAST_FORWARD,
    "record": 130,
    "captions": 175,
    "audio_track": 222,
    # TV
    "tv": KEY_TV,
    "info": 165,
    "guide": 172,
    "channel_up": 166,
    "channel_down": 167,
    "last_channel": 229,
    "input": 178,
    "hdmi1": 243,
    "hdmi2": 244,
    "hdmi3": 245,
    "hdmi4": 246,
    "composite1": 247,
    "composite2": 248,
    "component1": 249,
    "component2": 250,
    "vga": 251,
    # Colour buttons
    "red": 183,
    "green": 184,
    "yellow": 185,
    "blue": 186,
    # App buttons
    "youtube": 190,
    "netflix": 191,
    "prime": 195,
    "bookmark": 174,
    # Gamepad
    "pad_a": 96,
    "pad_b": 97,
    "pad_x": 99,
    "pad_y": 100,
    "pad_l1": 102,
    "pad_r1": 103,
    "pad_start": 108,
    "pad_select": 109,
    "pad_mode": 110,
}

# Digits 0-9 -> KEYCODE_0..9 (7..16)
for _n in range(10):
    _KEYS[str(_n)] = 7 + _n

_ALIASES: dict[str, str] = {
    "select": "center",
    "ok": "center",
    "dpad_center": "center",
    "dpad_up": "up",
    "dpad_down": "down",
    "dpad_left": "left",
    "dpad_right": "right",
    "return": "back",
    "vol_up": "volume_up",
    "vol_down": "volume_down",
    "volume_mute": "mute",
    "media_play_pause": "play_pause",
    "media_play": "play",
    "media_pause": "pause",
    "media_stop": "stop",
    "media_next": "next",
    "media_previous": "previous",
    "prev": "previous",
    "ff": "fast_forward",
    "rew": "rewind",
    "live": "tv",
    "subtitle": "captions",
    "subtitles": "captions",
    "ch_up": "channel_up",
    "ch_down": "channel_down",
    "source": "input",
    "hdmi_1": "hdmi1",
    "hdmi_2": "hdmi2",
    "hdmi_3": "hdmi3",
    "hdmi_4": "hdmi4",
    "apps": "all_apps",
    "recents": "app_switch",
    "backspace": "del",
    "delete": "del",
    "google_assistant": "assist",
    "assistant": "assist",
    "prime_video": "prime",
    "wake": "wakeup",
    "power_off": "sleep",
}

KEY_NAMES: dict[str, int] = {**_KEYS, **{alias: _KEYS[target] for alias, target in _ALIASES.items()}}


def resolve_key(name: str | int) -> int | None:
    """Resolve a key name, alias, ``KEYCODE_*`` constant or numeric string to a keycode.

    Case-insensitive; returns ``None`` when the input is not recognised.
    """
    if isinstance(name, bool):
        return None
    if isinstance(name, int):
        return name if 0 <= name <= 400 else None
    cleaned = str(name).strip()
    if not cleaned:
        return None
    if cleaned.isdigit():
        code = int(cleaned)
        return code if 0 <= code <= 400 else None
    lowered = cleaned.lower().replace("-", "_").replace(" ", "_")
    if lowered.startswith("keycode_"):
        lowered = lowered[len("keycode_") :]
    return KEY_NAMES.get(lowered)
