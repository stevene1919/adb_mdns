"""Tests for Config Flow and Entities of adb_mdns."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.adb_mdns.config_flow import AndroidTvAdbConfigFlow
from custom_components.adb_mdns.coordinator import AndroidTvAdbCoordinator
from custom_components.adb_mdns.media_player import AndroidTvAdbMediaPlayer
from custom_components.adb_mdns.remote import AndroidTvAdbRemote


@pytest.mark.anyio
async def test_config_flow_user_step_initial() -> None:
    """Test user step shows the form."""
    flow = AndroidTvAdbConfigFlow()
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.anyio
async def test_config_flow_pair_step_invalid_pin() -> None:
    """Test pair step validates PIN length."""
    flow = AndroidTvAdbConfigFlow()
    flow.host = "192.168.50.10"
    flow.pairing_port = 42181
    flow.connect_port = 33617

    result = await flow.async_step_pair({"pin": "123", "pairing_port": 42181, "port": 33617})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "invalid_pin"}


@pytest.mark.anyio
async def test_coordinator_state_parsing() -> None:
    """Test dumpsys parsing for power, app, playback state, and volume."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.50.10", CONF_PORT: 33617}

    client = MagicMock()
    client.is_connected = True
    client.port = 33617

    # Mock comprehensive dumpsys output:
    # awake, Netflix active, MediaSession state=PlaybackState {state=3}, STREAM_MUSIC volume
    dumpsys_output = (
        "mWakefulness=Awake\n"
        "mCurrentFocus=Window{12345 u0 com.netflix.ninja/com.netflix.ninja.MainActivity}\n"
        "state=PlaybackState {state=3, position=0}\n"
        "- STREAM_MUSIC:\n"
        "   Muted: false\n"
        "   Max: 15\n"
        "   Devices: speaker\n"
        "   speaker (muted:false): 9\n"
    )
    client.shell = AsyncMock(
        side_effect=lambda cmd, **kw: (
            "package:com.netflix.ninja\npackage:com.google.android.youtube.tv\n" if "pm list" in cmd else dumpsys_output
        )
    )

    coord = AndroidTvAdbCoordinator(hass, entry, client)
    data = await coord._async_update_data()
    coord.data = data

    assert data["state"] == MediaPlayerState.PLAYING
    assert data["current_app"] == "com.netflix.ninja"
    assert data["app_name"] == "Netflix"
    assert data["is_volume_muted"] is False
    assert data["volume_level"] == 9 / 15.0

    # Test media player entity attributes
    mp = AndroidTvAdbMediaPlayer(coord, entry)
    assert mp.state == MediaPlayerState.PLAYING
    assert mp.app_id == "com.netflix.ninja"
    assert mp.source == "Netflix"
    assert "Netflix" in mp.source_list
    assert mp.volume_level == 9 / 15.0
    assert mp.is_volume_muted is False

    # Test remote entity
    remote = AndroidTvAdbRemote(coord, entry)
    assert remote.is_on is True


@pytest.mark.anyio
async def test_remote_send_command() -> None:
    """Test sending command via Remote entity."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.50.10"}

    client = MagicMock()
    client.is_connected = True
    client.shell = AsyncMock(return_value="")

    coord = AndroidTvAdbCoordinator(hass, entry, client)
    remote = AndroidTvAdbRemote(coord, entry)

    await remote.async_send_command(["home", "volume_up", "26"])
    assert client.shell.call_count == 3


@pytest.mark.anyio
async def test_zeroconf_pairing_does_not_overwrite_connect_port() -> None:
    """Test that zeroconf discovery of pairing port does not overwrite connect port with 0."""
    flow = AndroidTvAdbConfigFlow()
    flow.hass = MagicMock()

    discovery_info = MagicMock()
    discovery_info.host = "192.168.50.10"
    discovery_info.port = 42181
    discovery_info.type = "_adb-tls-pairing._tcp.local."

    with (
        patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
        patch.object(flow, "_abort_if_unique_id_configured") as mock_abort,
    ):
        await flow.async_step_zeroconf(discovery_info)
        # Should NOT contain port: 0 in updates
        mock_abort.assert_called_once_with(updates={"host": "192.168.50.10"})
        assert flow.pairing_port == 42181
        assert flow.connect_port == 0
