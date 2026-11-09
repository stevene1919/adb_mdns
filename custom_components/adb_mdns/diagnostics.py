"""Diagnostics support for Android TV ADB."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PIN, CONF_PRIVATE_KEY
from .coordinator import AndroidTvAdbCoordinator

TO_REDACT = {
    CONF_PRIVATE_KEY,
    CONF_PIN,
    "serialno",
    "serial_number",
    "mac",
    "address",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    coord: AndroidTvAdbCoordinator | None = None
    if isinstance(runtime_data, AndroidTvAdbCoordinator):
        coord = runtime_data
    elif isinstance(runtime_data, dict):
        coord = runtime_data.get("coordinator")
    elif hasattr(runtime_data, "coordinator"):
        coord = getattr(runtime_data, "coordinator")

    diag: dict[str, Any] = {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
    }

    if coord:
        diag["coordinator"] = {
            "is_connected": coord.is_connected,
            "port": coord.client.port,
            "device_properties": async_redact_data(coord.device_properties, TO_REDACT),
            "installed_apps_count": len(coord.installed_apps),
            "running_apps": coord.running_apps,
            "keyboard_active": coord.keyboard_active,
            "inputs_count": len(coord.inputs),
            "settings": coord.settings,
            "data": async_redact_data(
                {k: v for k, v in (coord.data or {}).items() if k != "screencap_bytes"},
                TO_REDACT,
            ),
        }

    return diag
