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
async def test_config_flow_user_step_transitions_to_pair() -> None:
    """Test user step transitions to pair step and triggers mDNS discovery."""
    flow = AndroidTvAdbConfigFlow()
    flow.hass = MagicMock()

    with (
        patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_async_discover_mdns_ports", new_callable=AsyncMock) as mock_discover,
    ):
        result = await flow.async_step_user({"host": "192.168.50.10"})
        assert result["type"] == "form"
        assert result["step_id"] == "pair"
        assert flow.host == "192.168.50.10"
        mock_discover.assert_called_once()


@pytest.mark.anyio
async def test_config_flow_user_step_ip_and_port_parsing() -> None:
    """Test user step parses pasted IP:PORT string and sets pairing port."""
    flow = AndroidTvAdbConfigFlow()
    flow.hass = MagicMock()

    with (
        patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_async_discover_mdns_ports", new_callable=AsyncMock),
    ):
        result = await flow.async_step_user({"host": "192.168.50.10:42181"})
        assert result["type"] == "form"
        assert result["step_id"] == "pair"
        assert flow.host == "192.168.50.10"
        assert flow.pairing_port == 42181


@pytest.mark.anyio
async def test_config_flow_user_step_empty_host() -> None:
    """Test user step rejects empty host string."""
    flow = AndroidTvAdbConfigFlow()
    result = await flow.async_step_user({"host": "  "})
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "invalid_host"}


@pytest.mark.anyio
async def test_is_tv_panel_and_hdmi_sensor_gating() -> None:
    """Test is_tv_panel distinction and HDMI sensor gating between TVs and Chromecast."""
    from custom_components.adb_mdns.sensor import (
        AndroidTvAdbHdmiInputSensor,
        async_setup_entry as async_setup_sensor_entry,
    )
    from custom_components.adb_mdns.tv import TvInput

    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.50.10"}
    client = MagicMock()

    # 1. Test Chromecast (should NOT be a TV panel, HDMI sensor should NOT be added)
    coord_chromecast = AndroidTvAdbCoordinator(hass, entry, client)
    entry.runtime_data = coord_chromecast
    coord_chromecast.device_properties = {
        "model": "Chromecast",
        "manufacturer": "Google",
        "hdmi_device_type": "4",
    }
    assert coord_chromecast.is_tv_panel is False

    added_chromecast_entities: list = []
    await async_setup_sensor_entry(
        hass,
        entry,
        lambda entities: added_chromecast_entities.extend(entities),
    )
    assert not any(isinstance(e, AndroidTvAdbHdmiInputSensor) for e in added_chromecast_entities)

    # 2. Test Real Android TV (e.g. Sony Bravia or with HDMI inputs)
    coord_tv = AndroidTvAdbCoordinator(hass, entry, client)
    entry.runtime_data = coord_tv
    coord_tv.device_properties = {
        "model": "BRAVIA 4K VH2",
        "manufacturer": "Sony",
        "hdmi_device_type": "0",
    }
    coord_tv.inputs = [TvInput(id="HW1", kind="hdmi", port=1, device="", label="HDMI 1", key=243)]
    assert coord_tv.is_tv_panel is True

    added_tv_entities: list = []
    await async_setup_sensor_entry(
        hass,
        entry,
        lambda entities: added_tv_entities.extend(entities),
    )
    assert any(isinstance(e, AndroidTvAdbHdmiInputSensor) for e in added_tv_entities)


@pytest.mark.anyio
async def test_debug_logging_switch() -> None:
    """Test dynamic debug logging switch toggles log level."""
    from custom_components.adb_mdns.switch import (
        AndroidTvAdbDebugLoggingSwitch,
        async_setup_entry as async_setup_switch_entry,
    )

    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_HOST: "192.168.1.50", CONF_PORT: 5555}
    entry.entry_id = "switch_test_123"
    client = MagicMock()
    coord = AndroidTvAdbCoordinator(hass, entry, client)
    entry.runtime_data = coord

    added_switches: list = []
    await async_setup_switch_entry(
        hass,
        entry,
        lambda entities: added_switches.extend(entities),
    )
    debug_sw = next(e for e in added_switches if isinstance(e, AndroidTvAdbDebugLoggingSwitch))
    assert debug_sw.entity_registry_enabled_default is False

    # Turn on debug logging
    await debug_sw.async_turn_on()
    assert debug_sw.is_on is True

    # Turn off debug logging
    await debug_sw.async_turn_off()
    assert debug_sw.is_on is False

