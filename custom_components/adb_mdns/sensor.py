"""Sensor platform for Android TV ADB."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AndroidTvAdbCoordinator
from .entity import AndroidTvAdbEntity
from .tv import app_icon

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
        AndroidTvAdbHdmiInputSensor(coordinator, entry),
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
    async_add_entities(entities)


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
    def native_value(self) -> str | None:
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


class AndroidTvAdbTemperatureSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for SoC temperature."""

    _attr_has_entity_name = True
    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_temperature"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("temperature")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.thermal_state:
            attrs["thermal_status"] = self.coordinator.thermal_state.status
            attrs["sensors"] = self.coordinator.thermal_state.temperatures
        return attrs


class AndroidTvAdbMemoryUsageSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for RAM usage percentage."""

    _attr_has_entity_name = True
    _attr_translation_key = "memory_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_memory_usage"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("memory_usage")
        return None


class AndroidTvAdbMemoryAvailableSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for available RAM in MB."""

    _attr_has_entity_name = True
    _attr_translation_key = "memory_available"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_memory_available"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("memory_available_mb")
        return None


class AndroidTvAdbStorageAvailableSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for available internal storage in MB."""

    _attr_has_entity_name = True
    _attr_translation_key = "storage_available"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_storage_available"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("storage_available_mb")
        return None


class AndroidTvAdbCpuLoadSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for CPU load percentage."""

    _attr_has_entity_name = True
    _attr_translation_key = "cpu_load"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_cpu_load"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("cpu_load")
        return None


class AndroidTvAdbOpenAppsSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor counting open recents tasks."""

    _attr_has_entity_name = True
    _attr_translation_key = "open_apps"
    _attr_icon = "mdi:view-carousel"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_open_apps"

    @property
    def native_value(self) -> int:
        if self.coordinator.data:
            return self.coordinator.data.get("open_apps_count", 0)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.data:
            attrs["running_apps"] = self.coordinator.data.get("running_apps", [])
        return attrs


class AndroidTvAdbBluetoothDevicesSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor counting paired/connected Bluetooth devices."""

    _attr_has_entity_name = True
    _attr_translation_key = "bluetooth_devices"
    _attr_icon = "mdi:bluetooth"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_bluetooth_devices"

    @property
    def native_value(self) -> int:
        devices = self.coordinator.data.get("bluetooth_devices", []) if self.coordinator.data else []
        return len(devices)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        devices = self.coordinator.data.get("bluetooth_devices", []) if self.coordinator.data else []
        return {"devices": devices}


class AndroidTvAdbLastWakeReasonSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for last TV wake reason."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_wake_reason"
    _attr_icon = "mdi:power"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_last_wake_reason"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("last_wake_reason")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        locks = self.coordinator.data.get("wake_locks", []) if self.coordinator.data else []
        return {"wake_locks": locks}


class AndroidTvAdbLastSleepReasonSensor(AndroidTvAdbEntity, SensorEntity):
    """Diagnostic sensor for last TV sleep reason."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_sleep_reason"
    _attr_icon = "mdi:sleep"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_last_sleep_reason"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("last_sleep_reason")
        return None
