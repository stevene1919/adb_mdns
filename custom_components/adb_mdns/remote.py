"""Remote platform for Android TV ADB."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DOMAIN,
)
from .coordinator import AndroidTvAdbCoordinator
from .entity import AndroidTvAdbEntity
from .tv import resolve_key

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV ADB remote."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities([AndroidTvAdbRemote(coordinator, entry)])


class AndroidTvAdbRemote(AndroidTvAdbEntity, RemoteEntity):
    """Representation of an Android TV Remote."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_remote"

    @property
    def is_on(self) -> bool:
        """Return True if TV is powered on."""
        if self.coordinator.data:
            return bool(self.coordinator.data.get("is_on"))
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the TV."""
        await self.coordinator.async_power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the TV."""
        await self.coordinator.async_power_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands/keycodes to the TV."""
        opts = getattr(self.entry, "options", {}) or {}
        raw_rep = opts.get(CONF_KEY_REPEAT, DEFAULT_KEY_REPEAT) if isinstance(opts, dict) else DEFAULT_KEY_REPEAT
        raw_del = opts.get(CONF_KEY_DELAY, DEFAULT_KEY_DELAY) if isinstance(opts, dict) else DEFAULT_KEY_DELAY
        try:
            default_repeat = int(raw_rep)
        except (ValueError, TypeError):
            default_repeat = DEFAULT_KEY_REPEAT
        try:
            default_delay = float(raw_del)
        except (ValueError, TypeError):
            default_delay = DEFAULT_KEY_DELAY

        num_repeats = kwargs.get("num_repeats", default_repeat)
        delay_secs = kwargs.get("delay_secs", default_delay)
        try:
            num_repeats = int(num_repeats)
        except (ValueError, TypeError):
            num_repeats = 1
        try:
            delay_secs = float(delay_secs)
        except (ValueError, TypeError):
            delay_secs = 0.2

        for _ in range(num_repeats):
            for cmd in command:
                keycode = resolve_key(cmd)
                if keycode is None:
                    _LOGGER.warning("Unknown keycode or command: '%s'", cmd)
                    continue

                await self.coordinator.async_send_key(keycode)
                if delay_secs > 0:
                    await asyncio.sleep(delay_secs)
