"""Helpers for Android TV ADB config and pairing flow."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant
from zeroconf.asyncio import AsyncServiceBrowser

from .const import (
    MDNS_CONNECT_TYPE,
    MDNS_PAIRING_TYPE,
)

_LOGGER = logging.getLogger(__name__)


async def async_discover_mdns_ports(
    hass: HomeAssistant,
    host: str,
    timeout: float = 3.0,
) -> tuple[int, int]:
    """Discover pairing and connect ports for a host via mDNS."""
    if not host:
        return 0, 0

    pairing_port = 0
    connect_port = 0

    try:
        aiozc = zeroconf.async_get_async_zeroconf(hass)
        if inspect.isawaitable(aiozc):
            aiozc = await aiozc
        if not aiozc or not getattr(aiozc, "zeroconf", None):
            return 0, 0

        done_event = asyncio.Event()

        async def _inspect(service_type: str, name: str) -> None:
            nonlocal pairing_port, connect_port
            try:
                info = await aiozc.async_get_service_info(service_type, name, timeout=2000)
                if info and info.parsed_addresses():
                    for ip in info.parsed_addresses():
                        if ip == host and info.port:
                            if "pairing" in service_type.lower():
                                pairing_port = info.port
                            elif "connect" in service_type.lower():
                                connect_port = info.port
                            if pairing_port > 0 and connect_port > 0:
                                done_event.set()
                            return
            except Exception:
                pass

        def _on_change(*args: Any, **kwargs: Any) -> None:
            st = kwargs.get("service_type") or (args[1] if len(args) > 1 else "")
            nm = kwargs.get("name") or (args[2] if len(args) > 2 else "")
            if st and nm:
                hass.loop.call_soon_threadsafe(
                    lambda s=st, n=nm: hass.async_create_task(_inspect(s, n))
                )

        services_to_query: list[str] = [MDNS_PAIRING_TYPE, MDNS_CONNECT_TYPE]
        browser = AsyncServiceBrowser(aiozc.zeroconf, services_to_query, handlers=[_on_change])
        try:
            await asyncio.wait_for(done_event.wait(), timeout=timeout)
        except TimeoutError:
            pass
        finally:
            await browser.async_cancel()
    except Exception as err:
        _LOGGER.debug("mDNS discovery during config flow failed for %s: %s", host, err)

    return pairing_port, connect_port
