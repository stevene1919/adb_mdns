"""Shell command builders (Layer 1).

All commands are stock Android shell / ``dumpsys`` / ``cmd`` / ``settings``
invocations: nothing is pushed to or installed on the TV.
"""

from __future__ import annotations

import shlex
from urllib.parse import quote_plus

from .parser import INPUT_SEPARATOR

YOUTUBE_PACKAGE = "com.google.android.youtube.tv"


def _section(name: str, command: str) -> str:
    return f"echo '##{name}'; {command}"


CMD_DEVICE_PROPERTIES = "; ".join(
    [
        "echo '##PROPS'",
        'echo "NAME=$(settings get global device_name)"',
        'echo "MFG=$(getprop ro.product.manufacturer)"',
        'echo "MODEL=$(getprop ro.product.model)"',
        'echo "VER=$(getprop ro.build.version.release)"',
        'echo "SDK=$(getprop ro.build.version.sdk)"',
        'echo "SERIAL=$(getprop ro.serialno)"',
        'echo "BUILD=$(getprop ro.build.display.id)"',
        'echo "HDMI_TYPE=$(getprop ro.hdmi.device_type)"',
        _section("LINK", "ip -o link show 2>/dev/null"),
        _section("ADDR", "ip -o -4 addr show 2>/dev/null"),
        _section("WIFI_MAC", "dumpsys wifi 2>/dev/null | grep -m2 -E 'wifi_sta_factory_mac_address=|mWifiInfo.*MAC:'"),
    ]
)

CMD_LIST_PACKAGES = "pm list packages -3 2>/dev/null"

def build_status_poll_command(is_tv: bool = True) -> str:
    """Build fast status poll command string."""
    parts = [
        _section("POWER", "dumpsys power | grep -E 'mWakefulness=|Display Power: state=|mScreenOn='"),
        _section(
            "ACT",
            "dumpsys activity activities | grep -m2 -E 'mResumedActivity|topResumedActivity'",
        ),
        _section("WIN", "dumpsys window | grep -m1 mCurrentFocus"),
        _section(
            "MEDIA",
            "dumpsys media_session | grep -E '^[[:space:]]+(package|active)=|state=PlaybackState|metadata:'",
        ),
        _section("AUDIO", "dumpsys audio | grep -A 12 -- '- STREAM_MUSIC:'"),
    ]
    if is_tv:
        parts.append(_section("TVIN", "dumpsys tv_input 2>/dev/null | grep -m1 ResourceClientProfile"))
    parts.extend(
        [
            _section("IME", "dumpsys input_method 2>/dev/null | grep -m1 -E 'mInputShown=true|inputType=.*fieldId='"),
            _section("UPTIME", "cat /proc/uptime"),
        ]
    )
    return "; ".join(parts)


# Fast status poll (every scan interval).
CMD_POLL_STATUS = build_status_poll_command(is_tv=True)

CMD_KEYBOARD_TEXT = "dumpsys input_method | grep -E 'mInputShown=|inputType=.*fieldId='"

SETTINGS_READ: tuple[tuple[str, str], ...] = (
    ("global", "window_animation_scale"),
    ("global", "transition_animation_scale"),
    ("global", "animator_duration_scale"),
    ("global", "hdmi_control_auto_device_off_enabled"),
    ("global", "private_dns_mode"),
    ("global", "private_dns_specifier"),
    ("secure", "screensaver_enabled"),
    ("secure", "sleep_timeout"),
)


def _settings_block() -> str:
    return "; ".join(f'echo "{key}=$(settings get {ns} {key})"' for ns, key in SETTINGS_READ)


def build_health_command(include_inputs: bool) -> str:
    """Slow-tier poll: health, settings, recents, Bluetooth and inputs."""
    parts = [
        _section("MEM", "grep -E '^(MemTotal|MemAvailable):' /proc/meminfo"),
        _section("DISK", "stat -f -c '%a %b %S' /data 2>/dev/null"),
        _section("CPU", "head -1 /proc/stat 2>/dev/null"),
        _section(
            "THERMAL",
            "dumpsys thermalservice 2>/dev/null | sed -n '/^Thermal Status/p;/^Current temperatures from HAL/,/^Current cooling/p'",
        ),
        _section(
            "ZONES",
            'for z in /sys/class/thermal/thermal_zone*; do echo "$(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null)"; done 2>/dev/null',
        ),
        _section(
            "PWR",
            "dumpsys power | grep -E 'mLast(Global)?(Wake|Sleep)Reason=|_WAKE_LOCK '",
        ),
        _section(
            "BT",
            "dumpsys bluetooth_manager 2>/dev/null | grep -m1 -E '^ *enabled:'; "
            "dumpsys bluetooth_manager 2>/dev/null | sed -n '/Bonded devices:/,/^ *$/p'; "
            "dumpsys bluetooth_manager 2>/dev/null | grep -E "
            "'last_active_time=.*profile connection policy|mActiveDevice:|=== A2dpStateMachine for|"
            "mConnectionState:|StateMachine: name=A2dpStateMachine|^    [0-9A-FX:]{17} : [0-9]+'",
        ),
        _section(
            "BTIN",
            'dumpsys input 2>/dev/null | awk \'/^    [0-9]+: /{sub(/^    [0-9]+: /,"");n=$0} '
            '/Identifier: bus=0x0005/{print n"|"$0}\'',
        ),
        _section(
            "RECENTS",
            "dumpsys activity recents 2>/dev/null | grep -E '\\* Recent #|realActivity=|mActivityComponent=|mRootProcess='",
        ),
        _section("SETTINGS", _settings_block()),
    ]
    if include_inputs:
        parts.append(
            _section(
                "INPUTS", f"dumpsys tv_input 2>/dev/null; echo '{INPUT_SEPARATOR}'; dumpsys hdmi_control 2>/dev/null"
            )
        )
    return "; ".join(parts)


def q(value: str) -> str:
    """Shell-quote a value."""
    return shlex.quote(value)


def resolve_launch_activity(package: str) -> str:
    """Resolve an app's launcher component (Leanback first, then the phone launcher)."""
    p = q(package)
    return (
        "cmd package resolve-activity --brief -a android.intent.action.MAIN "
        f"-c android.intent.category.LEANBACK_LAUNCHER {p} 2>/dev/null | tail -n 1; "
        "cmd package resolve-activity --brief -a android.intent.action.MAIN "
        f"-c android.intent.category.LAUNCHER {p} 2>/dev/null | tail -n 1"
    )


def start_component(component: str) -> str:
    return f"am start -n {q(component)} 2>&1"


def monkey_launch(package: str) -> str:
    p = q(package)
    return (
        f"monkey -p {p} -c android.intent.category.LEANBACK_LAUNCHER 1 2>&1 || "
        f"monkey -p {p} -c android.intent.category.LAUNCHER 1 2>&1"
    )


def view_uri(uri: str, package: str | None = None) -> str:
    cmd = f"am start -a android.intent.action.VIEW -d {q(uri)}"
    if package:
        cmd += f" -p {q(package)}"
    return cmd + " 2>&1"


def search(query: str, target: str) -> str:
    """Global (Android TV) or YouTube search."""
    if target == "youtube":
        return view_uri(f"https://www.youtube.com/results?search_query={quote_plus(query)}", YOUTUBE_PACKAGE)
    return f"am start -a android.search.action.GLOBAL_SEARCH --es query {q(query)} 2>&1"


def input_text(text: str) -> str:
    """``input text`` with spaces encoded as ``%s`` (what ``input`` expects)."""
    return f"input text {q(text.replace('%', '\\%').replace(' ', '%s'))}"


def settings_put(namespace: str, key: str, value: str | int | float) -> str:
    return f"settings put {namespace} {key} {q(str(value))}"


CMD_VOLUME_GET = "cmd media_session volume --stream 3 --get 2>/dev/null"


def volume_set(level: int) -> str:
    return f"cmd media_session volume --stream 3 --set {int(level)} 2>/dev/null"


def volume_adjust(direction: str) -> str:
    """``direction`` is one of ``raise``, ``lower``, ``same``, ``mute``, ``unmute``, ``toggle_mute``."""
    return f"cmd media_session volume --stream 3 --adj {direction} 2>/dev/null"


CMD_TRIM_CACHES = (
    "a=$(stat -f -c '%a %S' /data); pm trim-caches 999G >/dev/null 2>&1; sleep 2; echo $a $(stat -f -c '%a %S' /data)"
)

CMD_START_SCREENSAVER = "cmd dreams start-dreaming 2>&1 || am start -n com.android.systemui/.Somnambulator 2>&1"

CMD_PAIR_BLUETOOTH = (
    "am start -a com.google.android.intent.action.CONNECT_INPUT 2>&1 || "
    "am start -a android.settings.BLUETOOTH_SETTINGS 2>&1"
)

CMD_BLUETOOTH_SETTINGS = (
    "am start -a android.settings.SLICE_SETTINGS "
    "--es slice_uri 'content://com.android.tv.settings.accessories.sliceprovider/general' "
    "--ez startup_verification_required false 2>&1 || "
    "am start -a android.settings.BLUETOOTH_SETTINGS 2>&1"
)


def bluetooth_device_slice_cmd(address: str, name: str = "") -> str:
    """Build command to open a specific paired Bluetooth device's slice page."""
    suffix = f"{address} {name}".strip()
    uri = f"content://com.android.tv.settings.accessories.sliceprovider/device/{suffix}"
    return (
        f"am start -a android.settings.SLICE_SETTINGS --es slice_uri {q(uri)} "
        "--ez startup_verification_required false 2>&1"
    )


def close_task(task_id: int) -> str:
    return f"am stack remove {int(task_id)} 2>/dev/null || cmd activity stack remove {int(task_id)} 2>/dev/null"


def force_stop(package: str) -> str:
    return f"am force-stop {q(package)}"
