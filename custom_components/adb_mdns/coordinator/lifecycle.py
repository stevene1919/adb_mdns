"""Lifecycle, initial background loading, and periodic health poll mixin."""

from __future__ import annotations

import inspect
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components import zeroconf
from zeroconf.asyncio import AsyncServiceBrowser

from ..const import (
    CONF_ENABLE_CEC_NAMES,
    CONF_PORT,
    DEFAULT_ENABLE_CEC_NAMES,
)
from ..tv import (
    build_health_command,
    cpu_percent,
    open_apps,
    parse_bluetooth,
    parse_cpu_times,
    parse_kv,
    parse_meminfo,
    parse_power_reasons,
    parse_recents,
    parse_storage,
    parse_thermal,
    parse_tv_inputs,
    split_sections,
)
from .discovery import MDNS_CONNECT_TYPE

if TYPE_CHECKING:
    from . import AndroidTvAdbCoordinator

_LOGGER = logging.getLogger(__name__)


class CoordinatorLifecycleMixin:
    """Mixin implementing setup, unload, initial background loading, and health poll."""

    async def _async_initial_background_load(self: AndroidTvAdbCoordinator) -> None:
        """Asynchronously load device properties, installed apps, and initial health telemetry in background."""
        try:
            if not self.client.is_connected:
                await self.client.connect(timeout=6.0)
            if self.client.is_connected:
                await self.async_fetch_device_properties()
                await self.async_refresh_installed_apps()
                await self._async_update_health()
                await self.async_request_refresh()
        except Exception as err:
            _LOGGER.debug("Background initial load deferred for %s: %s", self.host, err)

    async def async_setup(self: AndroidTvAdbCoordinator) -> None:
        """Set up dynamic mDNS listener to track changing TLS connect ports and load device info."""
        if self.client.port <= 0:
            discovered = await self.async_discover_port()
            if discovered > 0:
                self.client.update_port(discovered)
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, CONF_PORT: discovered},
                )

        try:
            if not self.client.is_connected:
                await self.client.connect(timeout=6.0)
            # Avoid delaying initial setup: defer slow queries (pm list, meminfo, screencap) to background
            now = time.time()
            self._last_health_time = now
            self._last_screencap_time = now
            self.hass.async_create_task(self._async_initial_background_load())
        except Exception as err:
            _LOGGER.debug("Initial setup connection deferred: %s", err)

        try:
            aiozc = zeroconf.async_get_async_zeroconf(self.hass)
            if inspect.isawaitable(aiozc):
                aiozc = await aiozc
            if not aiozc or not getattr(aiozc, "zeroconf", None):
                return

            def service_updated(*args: Any, **kwargs: Any) -> None:
                st = kwargs.get("service_type") or (args[1] if len(args) > 1 else "")
                nm = kwargs.get("name") or (args[2] if len(args) > 2 else "")
                if st and nm:
                    self.hass.loop.call_soon_threadsafe(
                        lambda s=st, n=nm: self.hass.async_create_task(self._handle_zeroconf_update(aiozc, s, n))
                    )

            self._browser = AsyncServiceBrowser(
                aiozc.zeroconf,
                [MDNS_CONNECT_TYPE],
                handlers=[service_updated],
            )
            _LOGGER.debug("Dynamic mDNS tracker active for Android TV %s", self.host)
        except Exception as err:
            _LOGGER.debug("Could not attach zeroconf listener: %s", err)

    async def async_unload(self: AndroidTvAdbCoordinator) -> None:
        """Cancel background browser and disconnect client."""
        if self._browser:
            try:
                await self._browser.async_cancel()
            except Exception:
                pass
            self._browser = None
        await self.client.disconnect()

    async def _async_update_health(self: AndroidTvAdbCoordinator) -> None:
        """Slow-tier telemetry and health poll."""
        enable_cec = self.entry.options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES)
        cmd = build_health_command(include_inputs=True)
        try:
            out = await self.client.shell(cmd, timeout=9.0)
            sections = split_sections(out)

            # Memory
            if mem_str := sections.get("MEM"):
                self.mem_info = parse_meminfo(mem_str)

            # Disk / Storage
            if disk_str := sections.get("DISK"):
                self.storage_info = parse_storage(disk_str)

            # CPU times delta
            if cpu_str := sections.get("CPU"):
                cur_cpu = parse_cpu_times(cpu_str)
                if cur_cpu:
                    self.cpu_load = cpu_percent(self._last_cpu_times, cur_cpu)
                    self._last_cpu_times = cur_cpu

            # Thermal
            hal_str = sections.get("THERMAL", "")
            zones_str = sections.get("ZONES", "")
            self.thermal_state = parse_thermal(hal_str, zones_str)

            # Power reasons & wake locks
            if pwr_str := sections.get("PWR"):
                self.power_reasons = parse_power_reasons(pwr_str)

            # Bluetooth
            bt_str = sections.get("BT", "")
            btin_str = sections.get("BTIN", "")
            self.bluetooth_info = parse_bluetooth(bt_str, btin_str)

            # Recents
            if rec_str := sections.get("RECENTS"):
                self.open_app_tasks = parse_recents(rec_str)
                self.running_apps = open_apps(self.open_app_tasks)

            # Settings
            if set_str := sections.get("SETTINGS"):
                self.settings = parse_kv(set_str)

            # TV Inputs
            if inp_str := sections.get("INPUTS"):
                self.inputs = parse_tv_inputs(inp_str, with_cec=enable_cec)

            self._last_health_time = time.time()
        except Exception as err:
            _LOGGER.debug("Health poll failed on %s: %s", self.host, err)
