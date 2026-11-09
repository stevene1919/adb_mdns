"""Switch platform for Android TV ADB."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Android TV ADB switch entities."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities(
        [
            AndroidTvAdbUiAnimationsSwitch(coordinator, entry),
            AndroidTvAdbScreensaverSwitch(coordinator, entry),
            AndroidTvAdbHdmiCecAutoOffSwitch(coordinator, entry),
        ]
    )


class AndroidTvAdbUiAnimationsSwitch(AndroidTvAdbEntity, SwitchEntity):
    """Switch for disabling/enabling UI transitions and window animations."""

    _attr_has_entity_name = True
    _attr_translation_key = "ui_animations"
    _attr_icon = "mdi:animation-play-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_ui_animations"

    @property
    def is_on(self) -> bool:
        val = self.coordinator.settings.get("window_animation_scale", "1")
        try:
            return float(val) > 0
        except ValueError:
            return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("global", "window_animation_scale", 1)
        await self.coordinator.async_set_setting("global", "transition_animation_scale", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("global", "window_animation_scale", 0)
        await self.coordinator.async_set_setting("global", "transition_animation_scale", 0)


class AndroidTvAdbScreensaverSwitch(AndroidTvAdbEntity, SwitchEntity):
    """Switch for screensaver_enabled setting."""

    _attr_has_entity_name = True
    _attr_translation_key = "screensaver_enabled"
    _attr_icon = "mdi:monitor-shimmer"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_screensaver_enabled"

    @property
    def is_on(self) -> bool:
        val = self.coordinator.settings.get("screensaver_enabled", "1")
        return val in ("1", "true", "True")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("secure", "screensaver_enabled", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("secure", "screensaver_enabled", 0)


class AndroidTvAdbHdmiCecAutoOffSwitch(AndroidTvAdbEntity, SwitchEntity):
    """Switch for hdmi_control_auto_device_off_enabled setting."""

    _attr_has_entity_name = True
    _attr_translation_key = "hdmi_cec_auto_off"
    _attr_icon = "mdi:power-plug-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_hdmi_cec_auto_off"

    @property
    def is_on(self) -> bool:
        val = self.coordinator.settings.get("hdmi_control_auto_device_off_enabled", "1")
        return val in ("1", "true", "True")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("global", "hdmi_control_auto_device_off_enabled", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_setting("global", "hdmi_control_auto_device_off_enabled", 0)
