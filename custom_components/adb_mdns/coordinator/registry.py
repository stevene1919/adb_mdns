"""Device registry and package management mixin for AndroidTvAdbCoordinator."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from ..const import CONF_MAC, DOMAIN
from ..tv import (
    CMD_DEVICE_PROPERTIES,
    CMD_LIST_PACKAGES,
    parse_device_properties,
    parse_packages,
)

if TYPE_CHECKING:
    from . import AndroidTvAdbCoordinator

_LOGGER = logging.getLogger(__name__)


class CoordinatorRegistryMixin:
    """Mixin providing device properties, registry updates, and installed apps discovery."""

    async def async_fetch_device_properties(self: AndroidTvAdbCoordinator) -> dict[str, str]:
        """Fetch hardware and firmware properties safely with key-value parser."""
        try:
            out = await self.client.shell(CMD_DEVICE_PROPERTIES, timeout=8.0)
            parsed = parse_device_properties(out, host=self.host)

            dev_name = parsed["name"] or self.device_properties.get("name") or "Android TV"
            mfg = parsed["manufacturer"] or self.device_properties.get("manufacturer") or "Google"
            mdl = parsed["model"] or self.device_properties.get("model") or "Android TV"
            ver = parsed["sw_version"] or self.device_properties.get("sw_version") or ""
            ser = parsed["serialno"] or self.device_properties.get("serialno") or ""
            mac = parsed["mac"] or self.device_properties.get("mac") or self.entry.data.get(CONF_MAC, "")

            self.device_properties = {
                "name": dev_name,
                "manufacturer": mfg,
                "model": mdl,
                "sw_version": ver,
                "serialno": ser,
                "mac": mac,
                "hdmi_device_type": parsed.get("hdmi_device_type", ""),
                "interface": parsed.get("interface", ""),
            }
            _LOGGER.info("Updated device properties for %s: %s", self.host, self.device_properties)

            self.hass.config_entries.async_update_entry(
                self.entry,
                title=dev_name,
                data={**self.entry.data, **self.device_properties},
            )
            # Live device registry update
            self.async_update_device_registry()
        except Exception as err:
            _LOGGER.debug("Could not fetch device properties: %s", err)
        return self.device_properties

    def async_update_device_registry(self: AndroidTvAdbCoordinator) -> None:
        """Update the device registry with dynamic properties."""
        try:
            from homeassistant.helpers import device_registry as dr

            dev_reg = dr.async_get(self.hass)
            if hasattr(dev_reg, "async_get_device_by_identifier"):
                device = dev_reg.async_get_device_by_identifier((DOMAIN, self.host))
            else:
                device = dev_reg.async_get_device(identifiers={(DOMAIN, self.host)})
            if device:
                props = self.device_properties
                updates: dict[str, Any] = {}
                if props.get("name") and props["name"] != device.name:
                    updates["name"] = props["name"]
                if props.get("manufacturer") and props["manufacturer"] != device.manufacturer:
                    updates["manufacturer"] = props["manufacturer"]
                if props.get("model") and props["model"] != device.model:
                    updates["model"] = props["model"]
                if props.get("sw_version") and props["sw_version"] != device.sw_version:
                    updates["sw_version"] = props["sw_version"]
                if props.get("serialno") and props["serialno"] != device.serial_number:
                    updates["serial_number"] = props["serialno"]
                if props.get("mac"):
                    clean_mac = props["mac"].replace("-", ":").lower()
                    connections = set(device.connections)
                    connections.add((dr.CONNECTION_NETWORK_MAC, clean_mac))
                    updates["connections"] = connections

                if updates:
                    dev_reg.async_update_device(device.id, **updates)
        except Exception as err:
            _LOGGER.debug("Device registry update deferred for %s: %s", self.host, err)

    async def async_refresh_installed_apps(self: AndroidTvAdbCoordinator) -> list[str]:
        """Fetch list of installed packages on the TV."""
        try:
            out = await self.client.shell(CMD_LIST_PACKAGES, timeout=6.0)
            packages = parse_packages(out)
            if not packages:
                out = await self.client.shell("pm list packages", timeout=7.0)
                packages = parse_packages(out)
            if packages:
                self.installed_apps = packages
                self._last_installed_apps_time = time.time()
                _LOGGER.info("Discovered %d installed apps on %s", len(packages), self.host)
        except Exception as err:
            _LOGGER.debug("Could not fetch installed packages: %s", err)
        return self.installed_apps
