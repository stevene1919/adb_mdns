"""Diagnostic sensor entities for Android TV ADB."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

from ..entity import AndroidTvAdbEntity

if TYPE_CHECKING:
    from ..coordinator import AndroidTvAdbCoordinator


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
        audio_devices = [d for d in devices if d.get("type") == "audio"]
        connected_devices = [d for d in devices if d.get("connected")]
        return {
            "devices": devices,
            "audio_devices": audio_devices,
            "connected_count": len(connected_devices),
        }


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
