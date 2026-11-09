"""Button platform for Android TV ADB."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AndroidTvAdbCoordinator
from .entity import AndroidTvAdbEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV ADB button entities."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities(
        [
            AndroidTvAdbRestartButton(coordinator, entry),
            AndroidTvAdbTrimCachesButton(coordinator, entry),
            AndroidTvAdbScreensaverButton(coordinator, entry),
        ]
    )


class AndroidTvAdbRestartButton(AndroidTvAdbEntity, ButtonEntity):
    """Button entity to restart Android TV."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_has_entity_name = True
    _attr_translation_key = "restart"

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_restart_button"

    async def async_press(self) -> None:
        await self.coordinator.async_reboot()


class AndroidTvAdbTrimCachesButton(AndroidTvAdbEntity, ButtonEntity):
    """Button entity to trim application caches."""

    _attr_has_entity_name = True
    _attr_translation_key = "trim_caches"
    _attr_icon = "mdi:broom"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_trim_caches_button"

    async def async_press(self) -> None:
        await self.coordinator.async_trim_caches()


class AndroidTvAdbScreensaverButton(AndroidTvAdbEntity, ButtonEntity):
    """Button entity to immediately start the screensaver."""

    _attr_has_entity_name = True
    _attr_translation_key = "start_screensaver"
    _attr_icon = "mdi:image-outline"

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_start_screensaver_button"

    async def async_press(self) -> None:
        await self.coordinator.async_start_screensaver()
