"""Service handlers and schema registration for Android TV ADB."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_APP,
    ATTR_APP_ID,
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_KEY,
    ATTR_KEY_SEQUENCE,
    ATTR_NUM_REPEATS,
    ATTR_QUERY,
    ATTR_SUBMIT,
    ATTR_TARGET,
    ATTR_TEXT,
    ATTR_URL,
    DOMAIN,
    SERVICE_ADB_COMMAND,
    SERVICE_LAUNCH_APP,
    SERVICE_SEARCH,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_START_SCREENSAVER,
    SERVICE_STOP_APP,
    SERVICE_TRIM_CACHES,
)
from .services_target import (
    _resolve_service_targets,
    _target_selector_fields,
    _validate_launch_app_data,
    parse_key_sequence,
)
from .tv import resolve_key

_LOGGER = logging.getLogger(__name__)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all integration services with target resolution."""

    # 1. adb_command
    schema_adb_command = vol.Schema(
        {
            vol.Required(ATTR_COMMAND): cv.string,
            **_target_selector_fields(),
        }
    )

    async def handle_adb_command(call: ServiceCall) -> dict[str, Any]:
        cmd = call.data[ATTR_COMMAND]
        targets = _resolve_service_targets(hass, call)
        responses: dict[str, str] = {}
        for coord in targets:
            try:
                res = await coord.async_run_command(cmd)
                responses[coord.host] = res
            except Exception as err:
                _LOGGER.error("Error executing ADB command on %s: %s", coord.host, err)
                responses[coord.host] = f"Error: {err}"
        return {"response": responses}

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADB_COMMAND,
        handle_adb_command,
        schema=schema_adb_command,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # 2. send_key
    schema_send_key = vol.Schema(
        {
            vol.Required(ATTR_KEY): vol.Any(cv.string, int),
            vol.Optional(ATTR_NUM_REPEATS, default=1): cv.positive_int,
            vol.Optional(ATTR_DELAY_SECS, default=0.2): vol.Coerce(float),
            **_target_selector_fields(),
        }
    )

    async def handle_send_key(call: ServiceCall) -> None:
        key_raw = call.data[ATTR_KEY]
        repeats = call.data[ATTR_NUM_REPEATS]
        delay = call.data[ATTR_DELAY_SECS]
        code = resolve_key(key_raw)
        if code is None:
            raise ServiceValidationError(
                f"Unknown keycode or key alias: '{key_raw}'",
                translation_domain=DOMAIN,
                translation_key="unknown_key",
            )
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            for _ in range(repeats):
                await coord.async_send_key(code)
                if delay > 0:
                    await asyncio.sleep(delay)

    hass.services.async_register(DOMAIN, SERVICE_SEND_KEY, handle_send_key, schema=schema_send_key)

    # 3. send_key_sequence
    schema_send_key_sequence = vol.Schema(
        {
            vol.Required(ATTR_KEY_SEQUENCE): vol.Any(cv.string, [vol.Any(cv.string, int)]),
            vol.Optional(ATTR_DELAY_SECS, default=0.2): vol.Coerce(float),
            **_target_selector_fields(),
        }
    )

    async def handle_send_key_sequence(call: ServiceCall) -> None:
        raw_seq = call.data[ATTR_KEY_SEQUENCE]
        delay = call.data[ATTR_DELAY_SECS]
        keys = parse_key_sequence(raw_seq)
        resolved_codes = []
        for k in keys:
            code = resolve_key(k)
            if code is None:
                raise ServiceValidationError(
                    f"Unknown keycode in sequence: '{k}'",
                    translation_domain=DOMAIN,
                    translation_key="unknown_key",
                )
            resolved_codes.append(code)

        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            for code in resolved_codes:
                await coord.async_send_key(code)
                if delay > 0:
                    await asyncio.sleep(delay)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_KEY_SEQUENCE, handle_send_key_sequence, schema=schema_send_key_sequence
    )

    # 4. launch_app
    schema_launch_app = vol.Schema(
        vol.All(
            {
                vol.Optional(ATTR_APP): cv.string,
                vol.Optional(ATTR_APP_ID): cv.string,
                vol.Optional(ATTR_URL): cv.string,
                **_target_selector_fields(),
            },
            _validate_launch_app_data,
        )
    )

    async def handle_launch_app(call: ServiceCall) -> None:
        app = call.data.get(ATTR_APP) or call.data.get(ATTR_APP_ID)
        url = call.data.get(ATTR_URL)
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            await coord.async_launch_app(app, url=url)

    hass.services.async_register(DOMAIN, SERVICE_LAUNCH_APP, handle_launch_app, schema=schema_launch_app)

    # 5. stop_app
    schema_stop_app = vol.Schema(
        {
            vol.Required(ATTR_APP): cv.string,
            **_target_selector_fields(),
        }
    )

    async def handle_stop_app(call: ServiceCall) -> None:
        app = call.data[ATTR_APP]
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            await coord.async_stop_app(app)

    hass.services.async_register(DOMAIN, SERVICE_STOP_APP, handle_stop_app, schema=schema_stop_app)

    # 6. send_text_input
    schema_send_text_input = vol.Schema(
        {
            vol.Required(ATTR_TEXT): cv.string,
            vol.Optional(ATTR_SUBMIT, default=False): cv.boolean,
            **_target_selector_fields(),
        }
    )

    async def handle_send_text_input(call: ServiceCall) -> None:
        text = call.data[ATTR_TEXT]
        submit = call.data[ATTR_SUBMIT]
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            await coord.async_send_text(text, submit=submit)

    hass.services.async_register(DOMAIN, SERVICE_SEND_TEXT_INPUT, handle_send_text_input, schema=schema_send_text_input)

    # 7. search
    schema_search = vol.Schema(
        {
            vol.Required(ATTR_QUERY): cv.string,
            vol.Optional(ATTR_TARGET, default="global"): vol.In(["global", "youtube"]),
            **_target_selector_fields(),
        }
    )

    async def handle_search(call: ServiceCall) -> None:
        query = call.data[ATTR_QUERY]
        target = call.data[ATTR_TARGET]
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            await coord.async_search(query, target=target)

    hass.services.async_register(DOMAIN, SERVICE_SEARCH, handle_search, schema=schema_search)

    # 8. trim_caches
    schema_trim_caches = vol.Schema(
        {
            **_target_selector_fields(),
        }
    )

    async def handle_trim_caches(call: ServiceCall) -> dict[str, Any]:
        targets = _resolve_service_targets(hass, call)
        results: dict[str, str] = {}
        for coord in targets:
            res = await coord.async_trim_caches()
            results[coord.host] = res
        return {"result": results}

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIM_CACHES,
        handle_trim_caches,
        schema=schema_trim_caches,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # 9. start_screensaver
    schema_screensaver = vol.Schema(
        {
            **_target_selector_fields(),
        }
    )

    async def handle_start_screensaver(call: ServiceCall) -> None:
        targets = _resolve_service_targets(hass, call)
        for coord in targets:
            await coord.async_start_screensaver()

    hass.services.async_register(DOMAIN, SERVICE_START_SCREENSAVER, handle_start_screensaver, schema=schema_screensaver)


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove all registered services when no config entries remain."""
    services = [
        SERVICE_ADB_COMMAND,
        SERVICE_SEND_KEY,
        SERVICE_SEND_KEY_SEQUENCE,
        SERVICE_LAUNCH_APP,
        SERVICE_STOP_APP,
        SERVICE_SEND_TEXT_INPUT,
        SERVICE_SEARCH,
        SERVICE_TRIM_CACHES,
        SERVICE_START_SCREENSAVER,
    ]
    for s in services:
        if hass.services.has_service(DOMAIN, s):
            hass.services.async_remove(DOMAIN, s)
