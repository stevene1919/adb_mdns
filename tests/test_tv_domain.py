"""Unit tests for the Layer 1 TV domain parsers and commands."""

import shlex

import pytest

from custom_components.adb_mdns.tv.apps import (
    app_icon,
    app_name,
    is_launcher,
    resolve_app,
)
from custom_components.adb_mdns.tv.commands import (
    CMD_POLL_STATUS,
    bluetooth_device_slice_cmd,
    build_health_command,
    input_text,
    q,
    search,
    settings_put,
    volume_adjust,
    volume_set,
)
from custom_components.adb_mdns.tv.keys import resolve_key
from custom_components.adb_mdns.tv.parser import (
    INPUT_SEPARATOR,
    cpu_percent,
    current_position,
    input_passthrough_uri,
    open_apps,
    parse_audio,
    parse_awake,
    parse_bluetooth,
    parse_cpu_times,
    parse_device_properties,
    parse_foreground,
    parse_keyboard_text,
    parse_kv,
    parse_media_sessions,
    parse_meminfo,
    parse_packages,
    parse_recents,
    parse_storage,
    parse_thermal,
    parse_tv_inputs,
    parse_volume_get,
    pick_media_session,
    split_sections,
    valid_input_id,
)


def test_resolve_key() -> None:
    """Test resolution of key names, aliases and numeric values."""
    assert resolve_key("HOME") == 3
    assert resolve_key("home") == 3
    assert resolve_key("Back") == 4
    assert resolve_key("POWER") == 26
    assert resolve_key("sleep") == 223
    assert resolve_key("wakeup") == 224
    assert resolve_key("SELECT") == 23
    assert resolve_key("center") == 23
    assert resolve_key("ok") == 23
    assert resolve_key("VOLUME_UP") == 24
    assert resolve_key("MUTE") == 164
    assert resolve_key("YOUTUBE") == 190
    assert resolve_key("NETFLIX") == 191
    assert resolve_key("PRIME") == 195
    assert resolve_key("ASSIST") == 219
    assert resolve_key("TV") == 170
    assert resolve_key("LIVE") == 170
    assert resolve_key("HDMI1") == 243
    assert resolve_key("hdmi_2") == 244
    assert resolve_key("KEYCODE_DPAD_CENTER") == 23
    assert resolve_key("5") == 5
    assert resolve_key(66) == 66
    assert resolve_key("unknown_key_xyz") is None
    assert resolve_key("") is None


def test_apps_catalogue() -> None:
    """Test app name mapping, icons, and launcher detection."""
    assert app_name("com.netflix.ninja") == "Netflix"
    assert app_name("com.google.android.youtube.tv") == "YouTube"
    assert app_name("unknown.app.package") == "unknown.app.package"

    assert app_icon("com.netflix.ninja") == "mdi:netflix"
    assert app_icon("com.google.android.youtube.tv") == "mdi:youtube"
    assert app_icon("com.google.android.tvlauncher") == "mdi:television-guide"
    assert app_icon("unknown.app") == "mdi:application"

    assert is_launcher("com.google.android.tvlauncher") is True
    assert is_launcher("com.google.android.apps.tv.launcherx") is True
    assert is_launcher("com.netflix.ninja") is False

    assert resolve_app("Netflix") == "com.netflix.ninja"
    assert resolve_app("youtube") == "com.google.android.youtube.tv"
    assert resolve_app("com.plexapp.android") == "com.plexapp.android"
    assert resolve_app("Plex", installed=["com.plexapp.android"]) == "com.plexapp.android"


def test_split_sections_and_kv() -> None:
    """Test section delimiter parsing."""
    sample = "##POWER\nmWakefulness=Awake\n##ACT\ntopResumedActivity=com.netflix.ninja/.MainActivity\n##EMPTY\n"
    sections = split_sections(sample)
    assert "POWER" in sections
    assert "ACT" in sections
    assert "EMPTY" in sections
    assert "mWakefulness=Awake" in sections["POWER"]

    kv = parse_kv("NAME=Living Room TV\nMFG=Sony\nMODEL=BRAVIA 4K\nBUILD=null\n")
    assert kv["NAME"] == "Living Room TV"
    assert kv["MFG"] == "Sony"
    assert kv["MODEL"] == "BRAVIA 4K"
    assert kv["BUILD"] == ""


def test_parse_device_properties() -> None:
    """Test device property parsing without line-shift errors."""
    output = (
        "##PROPS\n"
        "NAME=Shield TV Pro\n"
        "MFG=NVIDIA\n"
        "MODEL=SHIELD Android TV\n"
        "VER=11\n"
        "SDK=30\n"
        "SERIAL=0420000000000000\n"
        "BUILD=P3431_9.1.1\n"
        "##LINK\n"
        "1: lo: <LOOPBACK> link/loopback 00:00:00:00:00:00\n"
        "2: eth0: <BROADCAST,MULTICAST> link/ether 00:04:4b:ea:01:23\n"
        "3: wlan0: <BROADCAST,MULTICAST> link/ether 00:04:4b:ea:01:24\n"
        "##ADDR\n"
        "2: eth0    inet 192.168.50.150/24\n"
    )
    props = parse_device_properties(output, host="192.168.50.150")
    assert props["name"] == "Shield TV Pro"
    assert props["manufacturer"] == "NVIDIA"
    assert props["model"] == "SHIELD Android TV"
    assert props["sw_version"] == "11"
    assert props["serialno"] == "0420000000000000"
    assert props["mac"] == "00:04:4b:ea:01:23"
    assert props["interface"] == "eth0"

    # Android 14 fallback via ##WIFI_MAC when ip link is restricted
    output_a14 = (
        "##PROPS\n"
        "NAME=Sabrina\n"
        "MFG=Google\n"
        "MODEL=Chromecast\n"
        "##LINK\n"
        "##ADDR\n"
        "##WIFI_MAC\n"
        "wifi_sta_factory_mac_address=30:fd:38:ad:29:e4\n"
    )
    props_a14 = parse_device_properties(output_a14, host="192.168.50.10")
    assert props_a14["mac"] == "30:fd:38:ad:29:e4"
    assert props_a14["interface"] == "wlan0"


def test_parse_packages() -> None:
    """Test pm list packages parser."""
    out = "package:com.netflix.ninja\npackage:com.google.android.youtube.tv\npackage:org.xbmc.kodi\n"
    pkgs = parse_packages(out)
    assert pkgs == ["com.google.android.youtube.tv", "com.netflix.ninja", "org.xbmc.kodi"]


def test_parse_awake_and_foreground() -> None:
    """Test power state and Android 12-14 topResumedActivity foreground detection."""
    assert parse_awake("mWakefulness=Awake\nDisplay Power: state=ON") is True
    assert parse_awake("mWakefulness=Asleep\nDisplay Power: state=OFF") is False
    assert parse_awake("Display Power: state=ON") is True
    assert parse_awake("Display Power: state=OFF") is False

    act_dump = "topResumedActivity: ActivityRecord{abcdef0 u0 com.disney.disneyplus/com.disney.MainActivity}"
    assert parse_foreground(act_dump) == "com.disney.disneyplus"

    resumed_dump = "mResumedActivity: ActivityRecord{12345 u0 com.plexapp.android/com.plexapp.plex.MainActivity}"
    assert parse_foreground(resumed_dump) == "com.plexapp.android"

    window_dump = "mCurrentFocus=Window{54321 u0 org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity}"
    assert parse_foreground("", window_dump) == "org.videolan.vlc"


def test_parse_media_sessions_and_position() -> None:
    """Test dumpsys media_session metadata, action flags, and extrapolation."""
    sample = (
        "  package=com.spotify.tv.android\n"
        "  active=true\n"
        "  state=PlaybackState {state=3, position=45000, speed=1.0, updated=100000, actions=517}\n"
        "  metadata: size=3, description=Bohemian Rhapsody, Queen, A Night at the Opera\n"
    )
    sessions = parse_media_sessions(sample)
    assert len(sessions) == 1
    session = sessions[0]
    assert session.package == "com.spotify.tv.android"
    assert session.active is True
    assert session.state == 3
    assert session.title == "Bohemian Rhapsody"
    assert session.artist == "Queen"
    assert session.album == "A Night at the Opera"

    # Extrapolate current position when device uptime is 105000 ms (5s later)
    pos = current_position(session, uptime_ms=105000)
    assert pos == pytest.approx(50.0, 0.1)

    picked = pick_media_session(sessions, "com.spotify.tv.android")
    assert picked == session

    # Android 14 format: state=STOPPED(1) and state=PLAYING(3) with negative actions=-1
    sample_a14 = (
        "  package=org.xbmc.kodi\n"
        "  active=false\n"
        "  state=PlaybackState {state=STOPPED(1), position=0, buffered position=0, speed=0.0, updated=2567275, actions=-1}\n"
        "  metadata: size=4, description=Stale Title, null, null\n"
    )
    sessions_a14 = parse_media_sessions(sample_a14)
    assert len(sessions_a14) == 1
    assert sessions_a14[0].state == 1
    assert sessions_a14[0].actions == -1
    # Inactive stopped session should not be picked as active playing/paused media session
    assert pick_media_session(sessions_a14, "org.xbmc.kodi") is None


def test_parse_audio() -> None:
    """Test dumpsys audio STREAM_MUSIC parsing and friendly device names."""
    sample = "- STREAM_MUSIC:\n   Muted: false\n   Max: 25\n   Devices: hdmi_arc,speaker\n   (hdmi_arc): 18\n"
    audio = parse_audio(sample)
    assert audio.max_volume == 25
    assert audio.muted is False
    assert audio.volume == 18
    assert audio.output_name == "HDMI ARC"

    # Android hex bitmask device strings e.g. hdmi(400) on Chromecast with multiple Current entries
    sample_hdmi = (
        "- STREAM_MUSIC:\n"
        "   Muted: false\n"
        "   Min: 0\n"
        "   Max: 25\n"
        "   streamVolume:14\n"
        "   Current: 2 (speaker): 25, 80 (bt_a2dp): 17, 400 (hdmi): 14, 80000000 (default): 15\n"
        "   Devices: hdmi(400)\n"
    )
    audio_hdmi = parse_audio(sample_hdmi)
    assert audio_hdmi.output_name == "HDMI"
    assert audio_hdmi.volume == 14

    sample_speaker = "- STREAM_MUSIC:\n   Devices: speaker(2)\n"
    assert parse_audio(sample_speaker).output_name == "TV Speaker"

    sample_bt = "- STREAM_MUSIC:\n   Devices: bt_a2dp(80)\n"
    assert parse_audio(sample_bt).output_name == "Bluetooth"


def test_parse_volume_get() -> None:
    """Test cmd media_session volume --get."""
    out = "volume is 12 in range [0..25]"
    res = parse_volume_get(out)
    assert res == (12, 0, 25)


def test_parse_keyboard_and_inputs() -> None:
    """Test keyboard detection and HDMI/CEC inputs parsing."""
    assert parse_keyboard_text("mInputShown=true\ninputType=0x11 fieldId=123") is True
    assert parse_keyboard_text("mInputShown=false\ninputType=0x0 fieldId=0") is False

    # Tv inputs with CEC devices
    inputs_dump = (
        "TvInputInfo{id=com.mediatek.tvinput/.hdmi.HdmiInputService/HW5}\n"
        "TvInputHardwareInfo {id=5, type=9, hdmi_port_id=1, cable_connection_status=1}\n"
        f"{INPUT_SEPARATOR}\n"
        "port_id: 1, display_name: 'PlayStation 5', physical_address: 0x1000\n"
    )
    inputs = parse_tv_inputs(inputs_dump)
    assert len(inputs) == 1
    inp = inputs[0]
    assert inp.kind == "hdmi"
    assert inp.port == 1
    assert inp.device == "PlayStation 5"
    assert inp.label == "HDMI 1 · PlayStation 5"
    assert inp.connected is True
    assert valid_input_id(inp.id) is True
    assert (
        input_passthrough_uri(inp.id)
        == "content://android.media.tv/passthrough/com.mediatek.tvinput%2F.hdmi.HdmiInputService%2FHW5"
    )


def test_recents_and_health() -> None:
    """Test recents open tasks and system health parsers."""
    recents_dump = (
        "* Recent #1: Task{123 #1 type=standard A=com.netflix.ninja}\n"
        "   mActivityComponent=com.netflix.ninja/.MainActivity\n"
        "   mRootProcess=ProcessRecord{789}\n"
        "* Recent #2: Task{124 #2 type=home A=com.google.android.tvlauncher}\n"
    )
    tasks = parse_recents(recents_dump)
    assert len(tasks) == 2
    assert open_apps(tasks) == ["com.netflix.ninja"]

    mem = parse_meminfo("MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\n")
    assert mem == (2048000, 1024000)

    disk = parse_storage("500000 1000000 4096")
    assert disk == (500000 * 4096, 1000000 * 4096)

    cpu1 = parse_cpu_times("cpu 100 20 50 830 0 0 0 0")
    cpu2 = parse_cpu_times("cpu 150 25 75 850 0 0 0 0")
    assert cpu_percent(cpu1, cpu2) == pytest.approx(80.0, 0.5)

    hal_thermal = "Thermal Status: 0\nTemperature{mValue=48.5, mType=13, mName=SoC}\n"
    therm = parse_thermal(hal_thermal, "")
    assert therm is not None
    assert therm.status == 0
    assert therm.max_temperature == 48.5

    bt_dump = (
        "enabled: true\n"
        "Bonded devices:\n"
        "  11:22:33:44:55:66 [BR/EDR] SHIELD Remote\n"
        "  04:00:6E:D1:CF:17 [DUAL] Steven's Pixel Buds Pro 2\n"
        "\n"
        "A2dpStateMachine for XX:XX:XX:XX:CF:17 (Steven's Pixel Buds Pro 2):\n"
        "  mConnectionState: CONNECTED\n"
        "[04:00:6E:D1:CF:17]\n"
        "  A2DP=100\n"
        "  HEADSET=100\n"
        "[11:22:33:44:55:66]\n"
        "  HID_HOST=100\n"
    )
    bt_input = "SHIELD Remote|Identifier: bus=0x0005 bluetoothAddress=11:22:33:44:55:66\n"
    bt = parse_bluetooth(bt_dump, bt_input)
    assert bt is not None
    assert bt["enabled"] is True
    assert len(bt["devices"]) == 2
    assert bt["devices"][0]["connected"] is True
    assert bt["devices"][0]["type"] == "input"
    assert bt["devices"][1]["name"] == "Steven's Pixel Buds Pro 2"
    assert bt["devices"][1]["type"] == "audio"
    assert bt["devices"][1]["connected"] is True
    assert "content://com.android.tv.settings.accessories.sliceprovider/device/04:00:6E:D1:CF:17" in bluetooth_device_slice_cmd(
        "04:00:6E:D1:CF:17", "Steven's Pixel Buds Pro 2"
    )


def test_shell_commands_generation() -> None:
    """Test safe shell quoting and command generation."""
    assert q("netflix's") == shlex.quote("netflix's")
    assert search("Stranger Things", "youtube") == (
        "am start -a android.intent.action.VIEW -d 'https://www.youtube.com/results?search_query=Stranger+Things' -p com.google.android.youtube.tv 2>&1"
    )
    assert search("weather", "global") == ("am start -a android.search.action.GLOBAL_SEARCH --es query weather 2>&1")
    assert input_text("Hello World!") == "input text 'Hello%sWorld!'"
    assert settings_put("global", "window_animation_scale", 0) == "settings put global window_animation_scale 0"
    assert volume_set(15) == "cmd media_session volume --stream 3 --set 15 2>/dev/null"
    assert volume_adjust("mute") == "cmd media_session volume --stream 3 --adj mute 2>/dev/null"
    assert "dumpsys power" in CMD_POLL_STATUS
    assert "stat -f -c '%a %b %S' /data" in build_health_command(include_inputs=True)
