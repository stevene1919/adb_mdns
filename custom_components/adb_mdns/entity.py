"""Base entity for the Android TV ADB integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AndroidTvAdbCoordinator


class AndroidTvAdbEntity(CoordinatorEntity[AndroidTvAdbCoordinator]):
    """Base entity representation for Android TV ADB."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AndroidTvAdbCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant DeviceInfo dynamically from live coordinator properties."""
        props = self.coordinator.device_properties
        name = props.get("name") or self.entry.title or self.entry.data.get(CONF_NAME, "Android TV")
        manufacturer = props.get("manufacturer") or "Google"
        model = props.get("model") or "Android TV"
        sw_version = props.get("sw_version") or None
        serial_number = props.get("serialno") or None

        info = DeviceInfo(
            identifiers={(DOMAIN, self.entry.data[CONF_HOST])},
            name=name,
            manufacturer=manufacturer,
            model=model,
            sw_version=sw_version,
            serial_number=serial_number,
        )
        if mac := props.get("mac"):
            cleaned_mac = mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
        return info
