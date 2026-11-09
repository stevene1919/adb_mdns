"""Options flow for the Android TV ADB integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_WOL,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_HEALTH_INTERVAL,
    CONF_INCLUDE_LAUNCHER_IN_SOURCES,
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    CONF_SCAN_INTERVAL,
    CONF_SCREENCAP_INTERVAL,
    CONF_VOLUME_STEP_FALLBACK,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_WOL,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_HEALTH_INTERVAL,
    DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCREENCAP_INTERVAL,
    DEFAULT_VOLUME_STEP_FALLBACK,
)


class AndroidTvAdbOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Android TV ADB."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialize options flow."""
        if config_entry is not None:
            self._initial_config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = getattr(self, "_initial_config_entry", None)
        if entry is None:
            try:
                entry = self.config_entry
            except Exception:
                entry = None
        options = getattr(entry, "options", {}) or {}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=3, max=60)),
                vol.Optional(
                    CONF_HEALTH_INTERVAL,
                    default=options.get(CONF_HEALTH_INTERVAL, DEFAULT_HEALTH_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
                vol.Optional(
                    CONF_SCREENCAP_INTERVAL,
                    default=options.get(CONF_SCREENCAP_INTERVAL, DEFAULT_SCREENCAP_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
                vol.Optional(
                    CONF_ENABLE_WOL,
                    default=options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_CEC_NAMES,
                    default=options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES),
                ): bool,
                vol.Optional(
                    CONF_EXCLUDE_UNNAMED_APPS,
                    default=options.get(CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_LAUNCHER_IN_SOURCES,
                    default=options.get(CONF_INCLUDE_LAUNCHER_IN_SOURCES, DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES),
                ): bool,
                vol.Optional(
                    CONF_VOLUME_STEP_FALLBACK,
                    default=options.get(CONF_VOLUME_STEP_FALLBACK, DEFAULT_VOLUME_STEP_FALLBACK),
                ): bool,
                vol.Optional(
                    CONF_KEY_DELAY,
                    default=options.get(CONF_KEY_DELAY, DEFAULT_KEY_DELAY),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=2.0)),
                vol.Optional(
                    CONF_KEY_REPEAT,
                    default=options.get(CONF_KEY_REPEAT, DEFAULT_KEY_REPEAT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
