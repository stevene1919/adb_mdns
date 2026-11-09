"""mDNS discovery and port tracking mixin for AndroidTvAdbCoordinator."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import zeroconf
from zeroconf.asyncio import AsyncServiceBrowser

from ..const import CONF_PORT

if TYPE_CHECKING:
    from . import AndroidTvAdbCoordinator

_LOGGER = logging.getLogger(__name__)

MDNS_CONNECT_TYPE = "_adb-tls-connect._tcp.local."


class CoordinatorDiscoveryMixin:
    """Mixin providing mDNS port discovery and active port tracking."""

    async def async_discover_port(self: AndroidTvAdbCoordinator, timeout: float = 2.5) -> int:
        """Discover the active TLS connect port via mDNS (_adb-tls-connect._tcp.local.)."""
        _LOGGER.debug("Attempting to auto-discover TLS connect port for %s", self.host)
        try:
            aiozc = zeroconf.async_get_async_zeroconf(self.hass)
            if inspect.isawaitable(aiozc):
                aiozc = await aiozc
            if not aiozc or not getattr(aiozc, "zeroconf", None):
                return 0

            discovered_event = asyncio.Event()
            found_port: list[int] = []

            def on_service_change(*args: Any, **kwargs: Any) -> None:
                st = kwargs.get("service_type") or (args[1] if len(args) > 1 else "")
                nm = kwargs.get("name") or (args[2] if len(args) > 2 else "")
                if st and nm:
                    self.hass.loop.call_soon_threadsafe(
                        lambda s=st, n=nm: self.hass.async_create_task(
                            self._check_service(aiozc, s, n, found_port, discovered_event)
                        )
                    )

            browser = AsyncServiceBrowser(
                aiozc.zeroconf,
                [MDNS_CONNECT_TYPE],
                handlers=[on_service_change],
            )
            try:
                await asyncio.wait_for(discovered_event.wait(), timeout=timeout)
            except TimeoutError:
                pass
            finally:
                await browser.async_cancel()

            if found_port and found_port[0] > 0:
                _LOGGER.info("mDNS discovered active TLS connect port %s for %s", found_port[0], self.host)
                return found_port[0]
        except Exception as err:
            _LOGGER.debug("mDNS discovery failed for %s: %s", self.host, err)

        return 0

    async def _check_service(
        self: AndroidTvAdbCoordinator,
        aiozc: Any,
        service_type: str,
        name: str,
        found_port: list[int],
        event: asyncio.Event,
    ) -> None:
        """Inspect discovered service info to match host IP."""
        try:
            info = await aiozc.async_get_service_info(service_type, name, timeout=2000)
            if info and info.parsed_addresses():
                for ip in info.parsed_addresses():
                    if ip == self.host and info.port:
                        found_port.append(info.port)
                        event.set()
                        return
        except Exception as err:
            _LOGGER.debug("Error checking service %s: %s", name, err)

    async def _handle_zeroconf_update(
        self: AndroidTvAdbCoordinator, aiozc: Any, service_type: str, name: str
    ) -> None:
        """Handle incoming Zeroconf record update."""
        try:
            info = await aiozc.async_get_service_info(service_type, name, timeout=2000)
            if info and info.parsed_addresses():
                for ip in info.parsed_addresses():
                    if ip == self.host and info.port:
                        if self.client.port != info.port:
                            _LOGGER.info("mDNS updated TLS connect port for %s to %s", self.host, info.port)
                            self.client.update_port(info.port)
                            self.hass.config_entries.async_update_entry(
                                self.entry,
                                data={**self.entry.data, CONF_PORT: info.port},
                            )
                            await self.client.disconnect()
                            await self.async_request_refresh()
                        break
        except Exception as err:
            _LOGGER.debug("Error processing zeroconf update: %s", err)
