"""Repairs platform for Android TV ADB."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


class AndroidTvAdbRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, issue_id: str, data: dict[str, Any] | None) -> None:
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Handle the confirmation step."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self.data,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None = None,
) -> RepairsFlow:
    """Create flow to repair an issue."""
    return AndroidTvAdbRepairFlow(issue_id, data)
