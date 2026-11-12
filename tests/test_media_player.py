"""Tests for Media Player platform, source list, browse media, and app controls."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest
from homeassistant.components.media_player import MediaType
from homeassistant.const import CONF_HOST

from custom_components.adb_mdns.const import (
    CONF_APPS,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    KEY_SLEEP,
    KEY_WAKEUP,
)
from custom_components.adb_mdns.coordinator import AndroidTvAdbCoordinator
from custom_components.adb_mdns.media_player import (
    PARALLEL_UPDATES as MP_PARALLEL_UPDATES,
    AndroidTvAdbMediaPlayer,
)
from custom_components.adb_mdns.remote import (
    PARALLEL_UPDATES as REMOTE_PARALLEL_UPDATES,
)
from custom_components.adb_mdns.tv import (
    TvInput,
    app_thumbnail,
    build_status_poll_command,
)


@pytest.mark.anyio
async def test_media_player_sources_and_browse_media() -> None:
    """Test media player source list filtering and browse media."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50"}
    entry.options = {CONF_INCLUDE_APPS_IN_SOURCES: False}
    client = MagicMock()
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.inputs = [TvInput(id="HW1", kind="hdmi", port=1, device="", label="HDMI 1")]
    coord.installed_apps = ["com.netflix.ninja", "com.unknown.foo"]

    mp = AndroidTvAdbMediaPlayer(coord, entry)
    # When apps disabled in sources, only hardware inputs are returned
    assert mp.source_list == ["HDMI 1"]

    # When apps enabled
    entry.options = {CONF_INCLUDE_APPS_IN_SOURCES: True}
    assert "HDMI 1" in mp.source_list
    assert "Netflix" in mp.source_list

    # Browse media returns friendly titles and filters unnamed
    browse = await mp.async_browse_media()
    assert browse.children is not None
    assert len(browse.children) == 1
    assert browse.children[0].title == "Netflix"
    assert browse.children[0].media_content_id == "com.netflix.ninja"
    assert browse.children[0].thumbnail is not None
    assert "brands.home-assistant.io" in browse.children[0].thumbnail


@pytest.mark.anyio
async def test_custom_app_overrides_and_source_selection() -> None:
    """Test custom package overrides in options flow reflect in sources and browse media."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50"}
    entry.options = {
        CONF_INCLUDE_APPS_IN_SOURCES: True,
        CONF_APPS: {"com.unknown.foo": "My Custom Player"},
    }
    client = MagicMock()
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.inputs = []
    coord.installed_apps = ["com.unknown.foo"]
    coord.data = {"state": "idle", "is_on": True, "current_app": "com.unknown.foo"}

    mp = AndroidTvAdbMediaPlayer(coord, entry)
    assert mp.source_list == ["My Custom Player"]
    assert mp.source == "My Custom Player"

    browse = await mp.async_browse_media()
    assert browse.children is not None
    assert len(browse.children) == 1
    assert browse.children[0].title == "My Custom Player"
    assert browse.children[0].media_content_id == "com.unknown.foo"


def test_app_thumbnails() -> None:
    """Test official CDN logo resolution for known and unknown apps."""
    assert app_thumbnail("com.netflix.ninja") == "https://brands.home-assistant.io/_/netflix/logo.png"
    assert app_thumbnail("com.google.android.youtube.tv") == "https://brands.home-assistant.io/_/youtube/logo.png"
    assert app_thumbnail("org.xbmc.kodi") == "https://brands.home-assistant.io/_/kodi/logo.png"
    assert app_thumbnail("com.unknown.random") is None
    assert app_thumbnail(None) is None


@pytest.mark.anyio
async def test_channel_tuning_numeric_and_stream() -> None:
    """Test channel tuning key sequence dispatch and stream URL fallback."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50"}
    entry.options = {}
    client = MagicMock()
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.async_send_key = AsyncMock()
    coord.async_launch_app = AsyncMock()

    mp = AndroidTvAdbMediaPlayer(coord, entry)

    # Tuning to channel 102 sends keycodes 8 ('1'), 7 ('0'), 9 ('2')
    await mp.async_play_media(MediaType.CHANNEL, "102")
    assert coord.async_send_key.call_args_list == [call(8), call(7), call(9)]

    # Tuning with single digit
    coord.async_send_key.reset_mock()
    await mp.async_play_media("channel", "5")
    assert coord.async_send_key.call_args_list == [call(12)]

    # Non-numeric channel URL launches as stream URL
    coord.async_send_key.reset_mock()
    await mp.async_play_media(MediaType.CHANNEL, "https://live.stream/test.m3u8")
    assert not coord.async_send_key.called
    coord.async_launch_app.assert_awaited_once_with("", url="https://live.stream/test.m3u8")


@pytest.mark.anyio
async def test_custom_power_commands_and_fallback() -> None:
    """Test custom turn on and turn off commands override default keycodes."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50"}
    entry.options = {
        CONF_TURN_ON_COMMAND: "input keyevent 3",
        CONF_TURN_OFF_COMMAND: "input keyevent 26",
    }
    client = MagicMock()
    client.shell = AsyncMock(return_value="")
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.async_request_refresh = AsyncMock()

    # Custom power on executes configured shell command
    await coord.async_power_on()
    client.shell.assert_awaited_with("input keyevent 3", timeout=5.0)

    # Custom power off executes configured shell command
    client.shell.reset_mock()
    await coord.async_power_off()
    client.shell.assert_awaited_with("input keyevent 26", timeout=5.0)

    # Fallback to default keycodes when no custom commands configured
    entry.options = {}
    coord.async_send_key = AsyncMock()
    await coord.async_power_on()
    coord.async_send_key.assert_awaited_with(KEY_WAKEUP)

    coord.async_send_key.reset_mock()
    await coord.async_power_off()
    coord.async_send_key.assert_awaited_with(KEY_SLEEP)


def test_concurrency_parallel_updates_guard() -> None:
    """Test PARALLEL_UPDATES is set to 1 on media player and remote to prevent socket collisions."""
    assert MP_PARALLEL_UPDATES == 1
    assert REMOTE_PARALLEL_UPDATES == 1


@pytest.mark.anyio
async def test_launch_app_caching_and_optimistic_update() -> None:
    """Test async_launch_app caches resolved activity and updates state optimistically."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50"}
    entry.options = {}
    client = MagicMock()
    client.shell = AsyncMock(
        side_effect=[
            "com.netflix.ninja/com.netflix.ninja.MainActivity\n",
            "Starting: Intent { act=android.intent.action.MAIN ... }\n",
            "Starting: Intent { act=android.intent.action.MAIN ... }\n",
        ]
    )
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.data = {"state": "off", "is_on": True, "current_app": None}
    coord.async_set_updated_data = MagicMock()
    coord.async_request_refresh = AsyncMock()

    # First launch resolves activity
    await coord.async_launch_app("netflix")
    assert coord.data["current_app"] == "com.netflix.ninja"
    assert coord.data["app_name"] == "Netflix"
    assert (
        coord._launch_component_cache.get("com.netflix.ninja")
        == "com.netflix.ninja/com.netflix.ninja.MainActivity"
    )
    assert coord.async_set_updated_data.called

    # Second launch uses cached component directly (no resolve-activity shell command)
    coord.async_set_updated_data.reset_mock()
    await coord.async_launch_app("netflix")
    assert client.shell.call_count == 3


def test_build_status_poll_command() -> None:
    """Test dynamic status poll command generation based on is_tv flag."""
    tv_cmd = build_status_poll_command(is_tv=True)
    box_cmd = build_status_poll_command(is_tv=False)

    assert "dumpsys power" in tv_cmd
    assert "dumpsys tv_input" in tv_cmd
    assert "dumpsys input_method" in tv_cmd

    assert "dumpsys power" in box_cmd
    assert "dumpsys tv_input" not in box_cmd
    assert "dumpsys input_method" in box_cmd


@pytest.mark.anyio
async def test_bluetooth_sound_mode_and_controls() -> None:
    """Test Bluetooth headphone sound_mode_list, sound_mode, and async_select_sound_mode."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.50.10"}
    entry.options = {}
    client = MagicMock()
    client.shell = AsyncMock(return_value="")
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.device_properties = {"model": "Chromecast", "manufacturer": "Google", "hdmi_device_type": "4"}
    coord.data = {
        "state": "idle",
        "is_on": True,
        "current_app": "com.netflix.ninja",
        "app_name": "Netflix",
        "audio_output": "HDMI",
        "screencap_hash": "abcd1234",
        "bluetooth_devices": [
            {"address": "DC:2C:26:07:19:0D", "name": "Sofabaton 3B91", "connected": True, "type": "input"},
            {"address": "AC:3E:B1:95:BD:A5", "name": "Steven's Pixel Buds Pro 2", "connected": False, "type": "audio"},
            {"address": "04:00:6E:D1:CF:17", "name": "Steven's Pixel Buds Pro 2", "connected": False, "type": "audio"},
        ],
    }

    mp = AndroidTvAdbMediaPlayer(coord, entry)
    assert mp.app_name == "Netflix"
    assert mp.sound_mode == "HDMI"
    assert mp.sound_mode_list == [
        "HDMI",
        "Steven's Pixel Buds Pro 2 (BD:A5)",
        "Steven's Pixel Buds Pro 2 (CF:17)",
    ]
    assert "app_id" not in mp.extra_state_attributes
    assert len(mp.extra_state_attributes["bluetooth_audio_devices"]) == 2

    # When headphone connects, sound_mode updates to the connected headphone
    coord.data["bluetooth_devices"][2]["connected"] = True
    assert mp.sound_mode == "Steven's Pixel Buds Pro 2 (CF:17)"

    # Selecting HDMI disconnects the connected headphone
    coord.async_disconnect_bluetooth = AsyncMock()
    coord.async_connect_bluetooth = AsyncMock()
    await mp.async_select_sound_mode("HDMI")
    coord.async_disconnect_bluetooth.assert_awaited_once_with("04:00:6E:D1:CF:17")

    # Selecting a headphone calls async_connect_bluetooth
    await mp.async_select_sound_mode("Steven's Pixel Buds Pro 2 (CF:17)")
    coord.async_connect_bluetooth.assert_awaited_once_with("Steven's Pixel Buds Pro 2 (CF:17)")

    # When state is OFF, media_image_hash is None
    coord.data["state"] = "off"
    assert mp.media_image_hash is None
