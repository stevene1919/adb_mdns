"""Sensor platform for Android TV ADB."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..coordinator import AndroidTvAdbCoordinator
from ..entity import AndroidTvAdbEntity
from ..tv import app_icon
from .diagnostic import (
    AndroidTvAdbBluetoothDevicesSensor,
    AndroidTvAdbCpuLoadSensor,
    AndroidTvAdbLastSleepReasonSensor,
    AndroidTvAdbLastWakeReasonSensor,
    AndroidTvAdbMemoryAvailableSensor,
    AndroidTvAdbMemoryUsageSensor,
    AndroidTvAdbOpenAppsSensor,
    AndroidTvAdbStorageAvailableSensor,
    AndroidTvAdbTemperatureSensor,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV ADB sensor entities."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    entities: list[SensorEntity] = [
        AndroidTvAdbCurrentAppSensor(coordinator, entry),
        AndroidTvAdbAudioOutputSensor(coordinator, entry),
        AndroidTvAdbSessionStatusSensor(coordinator, entry),
        AndroidTvAdbTemperatureSensor(coordinator, entry),
        AndroidTvAdbMemoryUsageSensor(coordinator, entry),
        AndroidTvAdbMemoryAvailableSensor(coordinator, entry),
        AndroidTvAdbStorageAvailableSensor(coordinator, entry),
        AndroidTvAdbCpuLoadSensor(coordinator, entry),
        AndroidTvAdbOpenAppsSensor(coordinator, entry),
        AndroidTvAdbBluetoothDevicesSensor(coordinator, entry),
        AndroidTvAdbLastWakeReasonSensor(coordinator, entry),
        AndroidTvAdbLastSleepReasonSensor(coordinator, entry),
    ]

    hdmi_added = False
    if coordinator.is_tv_panel:
        entities.append(AndroidTvAdbHdmiInputSensor(coordinator, entry))
        hdmi_added = True

    async_add_entities(entities)

    @coordinator.async_add_listener
    def _check_hdmi_sensor() -> None:
        nonlocal hdmi_added
        if not hdmi_added and coordinator.is_tv_panel:
            hdmi_added = True
            async_add_entities([AndroidTvAdbHdmiInputSensor(coordinator, entry)])


class AndroidTvAdbCurrentAppSensor(AndroidTvAdbEntity, SensorEntity):
    """Sensor for current focused app on Android TV with dynamic icons."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_app"

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        """Initialize the current app sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_current_app"

    @property
    def icon(self) -> str:
        """Dynamically return app icon based on active package."""
        pkg = self.coordinator.data.get("current_app") if self.coordinator.data else None
        return app_icon(pkg)

    @property
    def native_value(self) -> str | None:
        """Return the friendly name or package of the current app."""
        if self.coordinator.data:
            return self.coordinator.data.get("app_name") or self.coordinator.data.get("current_app")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes like package ID."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data and (pkg := self.coordinator.data.get("current_app")):
            attrs["package"] = pkg
        return attrs


class AndroidTvAdbHdmiInputSensor(AndroidTvAdbEntity, SensorEntity):
    """Sensor for active HDMI input on Android TV."""

    _attr_has_entity_name = True
    _attr_translation_key = "hdmi_input"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_hdmi_input"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Only enable this sensor by default on physical TV panels with HDMI inputs."""
        return self.coordinator.is_tv_panel

    @property
    def available(self) -> bool:
        """Sensor is only available for devices that are actual TVs with HDMI inputs."""
        return super().available and self.coordinator.is_tv_panel

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.is_tv_panel:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("hdmi_input")
        return None


class AndroidTvAdbAudioOutputSensor(AndroidTvAdbEntity, SensorEntity):
    """Sensor for active STREAM_MUSIC audio output device."""

    _attr_has_entity_name = True
    _attr_translation_key = "audio_output"
    _attr_icon = "mdi:speaker"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_audio_output"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("audio_output")
        return None


class AndroidTvAdbSessionStatusSensor(AndroidTvAdbEntity, SensorEntity):
    """Sensor for ADB connection / session status."""

    _attr_has_entity_name = True
    _attr_translation_key = "session_status"
    _attr_icon = "mdi:shield-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_session_status"

    @property
    def native_value(self) -> str:
        if self.coordinator.client.is_connected:
            return "Active"
        return "Standby"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "tls_port": self.coordinator.client.port,
            "max_payload": getattr(self.coordinator.client, "_max_payload", 4096),
            "last_heard": getattr(self.coordinator.client, "last_heard", 0.0),
        }


__all__ = [
    "AndroidTvAdbAudioOutputSensor",
    "AndroidTvAdbBluetoothDevicesSensor",
    "AndroidTvAdbCpuLoadSensor",
    "AndroidTvAdbCurrentAppSensor",
    "AndroidTvAdbHdmiInputSensor",
    "AndroidTvAdbLastSleepReasonSensor",
    "AndroidTvAdbLastWakeReasonSensor",
    "AndroidTvAdbMemoryAvailableSensor",
    "AndroidTvAdbMemoryUsageSensor",
    "AndroidTvAdbOpenAppsSensor",
    "AndroidTvAdbSessionStatusSensor",
    "AndroidTvAdbStorageAvailableSensor",
    "AndroidTvAdbTemperatureSensor",
    "async_setup_entry",
]
