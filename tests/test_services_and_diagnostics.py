"""Tests for custom services, diagnostics, repairs, and options flow."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.adb_mdns.const import CONF_HOST, DOMAIN
from custom_components.adb_mdns.coordinator import AndroidTvAdbCoordinator
from custom_components.adb_mdns.diagnostics import async_get_config_entry_diagnostics
from custom_components.adb_mdns.options_flow import AndroidTvAdbOptionsFlowHandler
from custom_components.adb_mdns.repairs import async_create_fix_flow
from custom_components.adb_mdns.services_target import (
    _resolve_service_targets,
    parse_key_sequence,
)


def test_parse_key_sequence() -> None:
    """Test key sequence string / list splitting."""
    assert parse_key_sequence("HOME, DOWN, SELECT") == ["HOME", "DOWN", "SELECT"]
    assert parse_key_sequence(["HOME", "BACK"]) == ["HOME", "BACK"]
    assert parse_key_sequence("") == []


@pytest.mark.anyio
async def test_options_flow() -> None:
    """Test options flow handler displays form and returns user inputs."""
    entry = MagicMock()
    entry.options = {"scan_interval": 15, "enable_wol": True}
    flow = AndroidTvAdbOptionsFlowHandler(entry)

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    save_result = await flow.async_step_init({"scan_interval": 20, "enable_wol": False})
    assert save_result["type"] == "create_entry"
    assert save_result["data"]["scan_interval"] == 20
    assert save_result["data"]["enable_wol"] is False


@pytest.mark.anyio
async def test_repairs_flow() -> None:
    """Test repairs fix flow creation and confirmation step."""
    hass = MagicMock()
    flow = await async_create_fix_flow(hass, "pairing_revoked", {"host": "192.168.50.10"})
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    confirm_res = await flow.async_step_confirm({})
    assert confirm_res["type"] == "create_entry"


@pytest.mark.anyio
async def test_diagnostics_redaction() -> None:
    """Test diagnostics dump redacts private key and sensitive device identifiers."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_HOST: "192.168.50.10",
        "private_key": "-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----",
        "serialno": "SECRET_SERIAL",
        "mac": "11:22:33:44:55:66",
    }
    entry.options = {}

    client = MagicMock()
    client.is_connected = True
    client.port = 33617
    client.last_heard = 12345.0

    coord = AndroidTvAdbCoordinator(hass, entry, client)
    coord.device_properties = {
        "name": "Test TV",
        "serialno": "SECRET_SERIAL",
        "mac": "11:22:33:44:55:66",
    }
    coord.data = {
        "state": "playing",
        "screencap_bytes": b"LARGE_PNG_BLOB",
    }
    entry.runtime_data = coord

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["private_key"] == "**REDACTED**"
    assert diag["coordinator"]["device_properties"]["serialno"] == "**REDACTED**"
    assert diag["coordinator"]["device_properties"]["mac"] == "**REDACTED**"
    # Ensure raw screencap bytes are excluded from JSON diagnostics
    assert "screencap_bytes" not in diag["coordinator"]["data"]


@pytest.mark.anyio
async def test_service_targeting_and_ambiguity_guards() -> None:
    """Test target resolution by IP/entity and ambiguity guard when multiple TVs exist."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}

    entry1 = MagicMock()
    entry1.entry_id = "tv1"
    entry1.data = {CONF_HOST: "192.168.50.10"}
    client1 = MagicMock(is_connected=True, port=33617)
    coord1 = AndroidTvAdbCoordinator(hass, entry1, client1)
    coord1.host = "192.168.50.10"
    entry1.runtime_data = coord1

    entry2 = MagicMock()
    entry2.entry_id = "tv2"
    entry2.data = {CONF_HOST: "192.168.50.20"}
    client2 = MagicMock(is_connected=True, port=33618)
    coord2 = AndroidTvAdbCoordinator(hass, entry2, client2)
    coord2.host = "192.168.50.20"
    entry2.runtime_data = coord2

    hass.config_entries.async_loaded_entries = MagicMock(return_value=[entry1, entry2])

    # Ambiguous target without explicit selection
    call_ambiguous = MagicMock(data={})
    with pytest.raises(ServiceValidationError) as exc:
        _resolve_service_targets(hass, call_ambiguous)
    assert "Multiple Android TVs are configured" in str(exc.value)

    # Specific IP target
    call_ip = MagicMock(data={"ip_address": "192.168.50.10"})
    resolved = _resolve_service_targets(hass, call_ip)
    assert resolved == [coord1]

    # Broadcast 'all' target
    call_all = MagicMock(data={"target": "all"})
    resolved_all = _resolve_service_targets(hass, call_all)
    assert resolved_all == [coord1, coord2]
