"""Config flow for the Android TV ADB integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from zeroconf.asyncio import AsyncServiceBrowser

from .const import (
    CONF_PAIRING_PORT,
    CONF_PIN,
    CONF_PRIVATE_KEY,
    DEFAULT_NAME,
    DOMAIN,
)
from .core import (
    AndroidTvAdbClient,
    generate_keypair,
    pair_device,
)
from .options_flow import AndroidTvAdbOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

MDNS_CONNECT_TYPE = "_adb-tls-connect._tcp.local."
MDNS_PAIRING_TYPE = "_adb-tls-pairing._tcp.local."


class AndroidTvAdbConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Android TV ADB."""

    VERSION = 1

    def __init__(self) -> None:
        self.host: str | None = None
        self.connect_port: int = 0
        self.pairing_port: int = 0
        self.device_name: str = DEFAULT_NAME
        self.manufacturer: str = "Google"
        self.model: str = "Android TV"
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AndroidTvAdbOptionsFlowHandler(config_entry)

    async def _async_discover_mdns_ports(self, timeout: float = 1.8) -> None:
        """Query mDNS for both _adb-tls-connect and _adb-tls-pairing ports for self.host."""
        if not self.host or not getattr(self, "hass", None):
            return
        try:
            aiozc = await zeroconf.async_get_async_zeroconf(self.hass)
            if not aiozc or not getattr(aiozc, "zeroconf", None):
                return

            done_event = asyncio.Event()

            async def _inspect(service_type: str, name: str) -> None:
                try:
                    info = await aiozc.async_get_service_info(service_type, name)
                    if not info or not info.port:
                        return
                    for ip in info.parsed_addresses():
                        if ip == self.host:
                            if "pairing" in service_type.lower() and self.pairing_port <= 0:
                                self.pairing_port = info.port
                            elif "connect" in service_type.lower() and self.connect_port <= 0:
                                self.connect_port = info.port
                            if self.pairing_port > 0 and self.connect_port > 0:
                                done_event.set()
                            return
                except Exception:
                    pass

            def _on_change(zc: Any, service_type: str, name: str, state_change: Any, **kwargs: Any) -> None:
                self.hass.loop.call_soon_threadsafe(lambda: self.hass.async_create_task(_inspect(service_type, name)))

            services_to_query: list[str] = []
            if self.pairing_port <= 0:
                services_to_query.append(MDNS_PAIRING_TYPE)
            if self.connect_port <= 0:
                services_to_query.append(MDNS_CONNECT_TYPE)
            if not services_to_query:
                return

            browser = AsyncServiceBrowser(aiozc.zeroconf, services_to_query, handlers=[_on_change])
            try:
                await asyncio.wait_for(done_event.wait(), timeout=timeout)
            except TimeoutError:
                pass
            finally:
                await browser.async_cancel()
        except Exception as err:
            _LOGGER.debug("mDNS discovery during config flow failed for %s: %s", self.host, err)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual user setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST].strip()
            self.connect_port = user_input.get(CONF_PORT, 0)
            self.pairing_port = user_input.get(CONF_PAIRING_PORT, 0)

            await self.async_set_unique_id(self.host)
            updates: dict[str, Any] = {CONF_HOST: self.host}
            if self.connect_port > 0:
                updates[CONF_PORT] = self.connect_port
            self._abort_if_unique_id_configured(updates=updates)

            return await self.async_step_pair()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PAIRING_PORT, default=0): int,
                vol.Optional(CONF_PORT, default=0): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle discovery via mDNS / Zeroconf."""
        self.host = discovery_info.host
        _LOGGER.debug(
            "Discovered ADB service over Zeroconf: %s (%s:%s)",
            discovery_info.type,
            self.host,
            discovery_info.port,
        )

        service_type = discovery_info.type.lower()
        if "pairing" in service_type:
            self.pairing_port = discovery_info.port
        elif "connect" in service_type:
            self.connect_port = discovery_info.port

        await self.async_set_unique_id(self.host)
        updates: dict[str, Any] = {CONF_HOST: self.host}
        if self.connect_port > 0:
            updates[CONF_PORT] = self.connect_port
        self._abort_if_unique_id_configured(updates=updates)

        if hasattr(self, "context") and isinstance(self.context, dict):
            self.context["title_placeholders"] = {"name": f"Android TV ({self.host})"}
        return await self.async_step_pair()

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth initiation."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm reauth with a fresh PIN."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = user_input[CONF_PIN].strip().replace(" ", "")
            pairing_port = user_input.get(CONF_PAIRING_PORT) or self.pairing_port
            connect_port = user_input.get(CONF_PORT) or self.connect_port

            if not pairing_port or not connect_port:
                await self._async_discover_mdns_ports()
                if not pairing_port:
                    pairing_port = self.pairing_port
                if not connect_port:
                    connect_port = self.connect_port

            if not pairing_port:
                errors["base"] = "missing_pairing_port"
            elif len(pin) != 6 or not pin.isdigit():
                errors["base"] = "invalid_pin"
            else:
                try:
                    loop = asyncio.get_running_loop()
                    key, pem = await loop.run_in_executor(None, generate_keypair)
                    success = await pair_device(
                        host=self.host,
                        port=pairing_port,
                        pin=pin,
                        key=key,
                        timeout=12.0,
                    )
                    if not success:
                        errors["base"] = "pairing_failed"
                    else:
                        if not connect_port:
                            await self._async_discover_mdns_ports(timeout=2.5)
                            connect_port = self.connect_port

                        if self._reauth_entry:
                            new_data = {
                                **self._reauth_entry.data,
                                CONF_PRIVATE_KEY: pem,
                            }
                            if connect_port:
                                new_data[CONF_PORT] = connect_port
                            self.hass.config_entries.async_update_entry(
                                self._reauth_entry,
                                data=new_data,
                            )
                            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                            return self.async_abort(reason="reauth_successful")
                except Exception as err:
                    _LOGGER.exception("Reauth pairing failed: %s", err)
                    errors["base"] = "cannot_connect"

        schema_fields = {
            vol.Required(CONF_PIN): str,
            vol.Required(CONF_PAIRING_PORT, default=self.pairing_port or 0): int,
            vol.Optional(CONF_PORT, default=self.connect_port or 0): int,
        }
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={"host": self.host or ""},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguring the IP address or port."""
        reconfigure_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if not reconfigure_entry:
            return self.async_abort(reason="unknown_entry")

        errors: dict[str, str] = {}
        if user_input is not None:
            new_host = user_input[CONF_HOST].strip()
            new_port = user_input.get(CONF_PORT, 0)
            self.hass.config_entries.async_update_entry(
                reconfigure_entry,
                data={**reconfigure_entry.data, CONF_HOST: new_host, CONF_PORT: new_port},
            )
            await self.hass.config_entries.async_reload(reconfigure_entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST, "")): str,
                vol.Optional(CONF_PORT, default=reconfigure_entry.data.get(CONF_PORT, 0)): int,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle 6-digit PIN pairing step."""
        errors: dict[str, str] = {}

        if user_input is None and (self.pairing_port <= 0 or self.connect_port <= 0):
            await self._async_discover_mdns_ports()

        if user_input is not None:
            pin = user_input[CONF_PIN].strip().replace(" ", "")
            pairing_port = user_input.get(CONF_PAIRING_PORT) or self.pairing_port
            connect_port = user_input.get(CONF_PORT) or self.connect_port

            if not pairing_port or not connect_port:
                await self._async_discover_mdns_ports()
                if not pairing_port:
                    pairing_port = self.pairing_port
                if not connect_port:
                    connect_port = self.connect_port

            if not pairing_port:
                errors["base"] = "missing_pairing_port"
            elif len(pin) != 6 or not pin.isdigit():
                errors["base"] = "invalid_pin"
            else:
                try:
                    loop = asyncio.get_running_loop()
                    key, pem = await loop.run_in_executor(None, generate_keypair)
                    success = await pair_device(
                        host=self.host,
                        port=pairing_port,
                        pin=pin,
                        key=key,
                        timeout=12.0,
                    )
                    if not success:
                        errors["base"] = "pairing_failed"
                    else:
                        if not connect_port:
                            await self._async_discover_mdns_ports(timeout=2.5)
                            connect_port = self.connect_port

                        if connect_port:
                            client = AndroidTvAdbClient(self.host, connect_port, key)
                            try:
                                await client.connect(timeout=8.0)
                                mfg = await client.shell("getprop ro.product.manufacturer", timeout=5.0)
                                mdl = await client.shell("getprop ro.product.model", timeout=5.0)
                                if mfg and mfg.strip():
                                    self.manufacturer = mfg.strip()
                                if mdl and mdl.strip():
                                    self.model = mdl.strip()
                                    self.device_name = f"{self.manufacturer} {self.model}".strip()
                                await client.disconnect()
                            except Exception as err:
                                _LOGGER.debug("Could not fetch device properties immediately: %s", err)

                        return self.async_create_entry(
                            title=self.device_name,
                            data={
                                CONF_HOST: self.host,
                                CONF_PORT: connect_port,
                                CONF_PRIVATE_KEY: pem,
                                CONF_NAME: self.device_name,
                            },
                        )

                except ValueError as err:
                    _LOGGER.warning("Pairing validation error: %s", err)
                    errors["base"] = "invalid_pin"
                except Exception as err:
                    _LOGGER.exception("Pairing failed with %s: %s", type(err).__name__, err)
                    errors["base"] = "cannot_connect"

        schema_fields: dict[Any, Any] = {
            vol.Required(CONF_PIN): str,
        }
        if self.pairing_port:
            schema_fields[vol.Required(CONF_PAIRING_PORT, default=self.pairing_port)] = int
        else:
            schema_fields[vol.Required(CONF_PAIRING_PORT)] = int

        if self.connect_port:
            schema_fields[vol.Optional(CONF_PORT, default=self.connect_port)] = int
        else:
            schema_fields[vol.Optional(CONF_PORT, default=0)] = int

        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={"host": self.host or ""},
        )
