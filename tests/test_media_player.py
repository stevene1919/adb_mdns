"""Tests for Media Player platform, source list, browse media, and app controls."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_HOST

from custom_components.adb_mdns.const import CONF_INCLUDE_APPS_IN_SOURCES
from custom_components.adb_mdns.coordinator import AndroidTvAdbCoordinator
from custom_components.adb_mdns.media_player import AndroidTvAdbMediaPlayer
from custom_components.adb_mdns.tv import TvInput, build_status_poll_command


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
