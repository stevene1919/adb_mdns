"""The Android TV ADB integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PRIVATE_KEY, DOMAIN
from .coordinator import AndroidTvAdbCoordinator
from .core import AndroidTvAdbClient, load_private_key
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]

type AndroidTvAdbConfigEntry = ConfigEntry[AndroidTvAdbCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AndroidTvAdbConfigEntry) -> bool:
    """Set up Android TV ADB from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 0)
    pem = entry.data[CONF_PRIVATE_KEY]

    # Offload crypto key load from event loop
    loop = asyncio.get_running_loop()
    key = await loop.run_in_executor(None, load_private_key, pem)

    client = AndroidTvAdbClient(host=host, port=port, key=key)
    coordinator = AndroidTvAdbCoordinator(hass=hass, entry=entry, client=client)

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to all entity platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Perform live device registry enrichment after entity platforms are registered
    coordinator.async_update_device_registry()

    # Register custom services
    async_setup_services(hass)

    # Attach update listener for options flow
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: AndroidTvAdbConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AndroidTvAdbConfigEntry) -> bool:
    """Unload an Android TV ADB config entry."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN].get(entry.entry_id)
    )
    if coordinator is not None:
        await coordinator.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data[DOMAIN]:
        async_unload_services(hass)

    return unload_ok
