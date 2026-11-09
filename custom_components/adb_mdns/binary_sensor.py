"""Binary sensor platform for Android TV ADB."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the Android TV ADB binary sensor entities."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities(
        [
            AndroidTvAdbConnectedBinarySensor(coordinator, entry),
            AndroidTvAdbInUseBinarySensor(coordinator, entry),
            AndroidTvAdbKeyboardBinarySensor(coordinator, entry),
        ]
    )


class AndroidTvAdbConnectedBinarySensor(AndroidTvAdbEntity, BinarySensorEntity):
    """Binary sensor for ADB TLS 1.3 socket connectivity."""

    _attr_has_entity_name = True
    _attr_translation_key = "adb_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_adb_connected"

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "host": self.coordinator.host,
            "port": self.coordinator.client.port,
            "max_payload": getattr(self.coordinator.client, "_max_payload", 4096),
        }


class AndroidTvAdbInUseBinarySensor(AndroidTvAdbEntity, BinarySensorEntity):
    """Binary sensor indicating if the TV is in use (powered on & awake)."""

    _attr_has_entity_name = True
    _attr_translation_key = "in_use"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_in_use"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data:
            return bool(self.coordinator.data.get("is_on"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.data:
            attrs["current_app"] = self.coordinator.data.get("current_app")
            attrs["app_name"] = self.coordinator.data.get("app_name")
            attrs["hdmi_input"] = self.coordinator.data.get("hdmi_input")
        return attrs


class AndroidTvAdbKeyboardBinarySensor(AndroidTvAdbEntity, BinarySensorEntity):
    """Binary sensor indicating if the TV on-screen keyboard / text field is active."""

    _attr_has_entity_name = True
    _attr_translation_key = "keyboard_active"
    _attr_icon = "mdi:keyboard"

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_keyboard_active"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data:
            return bool(self.coordinator.data.get("keyboard_active", False))
        return False
