"""Action and control mixin for AndroidTvAdbCoordinator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState

from ..const import (
    CONF_ENABLE_WOL,
    CONF_MAC,
    CONF_VOLUME_STEP_FALLBACK,
    DEFAULT_ENABLE_WOL,
    DEFAULT_VOLUME_STEP_FALLBACK,
)
from ..core import async_send_magic_packet
from ..tv import (
    CMD_START_SCREENSAVER,
    CMD_TRIM_CACHES,
    CMD_VOLUME_GET,
    KEY_SLEEP,
    KEY_WAKEUP,
    TvInput,
    am_start_failed,
    app_name,
    close_task,
    force_stop,
    input_passthrough_uri,
    input_text,
    is_launcher,
    monkey_launch,
    parse_volume_get,
    resolve_app,
    resolve_key,
    resolve_launch_activity,
    search,
    settings_put,
    start_component,
    valid_input_id,
    view_uri,
    volume_adjust,
    volume_set,
)

if TYPE_CHECKING:
    from . import AndroidTvAdbCoordinator

_LOGGER = logging.getLogger(__name__)


class CoordinatorActionsMixin:
    """Mixin implementing command and control actions on Android TV."""

    async def async_send_key(self: AndroidTvAdbCoordinator, keycode: int) -> None:
        """Send an input keyevent code to the TV."""
        await self.client.shell(f"input keyevent {keycode}", timeout=4.0)

    async def async_power_on(self: AndroidTvAdbCoordinator) -> None:
        """Wake up the TV using KEY_WAKEUP and optional Wake-on-LAN."""
        if self.data:
            self.data["is_on"] = True
            self.data["state"] = MediaPlayerState.IDLE
            self.async_set_updated_data(self.data)
        if self.entry.options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL):
            mac = self.device_properties.get("mac") or self.entry.data.get(CONF_MAC)
            if mac:
                await async_send_magic_packet(mac)
        await self.async_send_key(KEY_WAKEUP)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_power_off(self: AndroidTvAdbCoordinator) -> None:
        """Idempotently put the TV to sleep using KEY_SLEEP."""
        if self.data:
            self.data["is_on"] = False
            self.data["state"] = MediaPlayerState.OFF
            self.async_set_updated_data(self.data)
        await self.async_send_key(KEY_SLEEP)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_set_volume_level(self: AndroidTvAdbCoordinator, volume: float) -> None:
        """Set relative volume level (0.0 to 1.0) with HDMI-CEC fallback."""
        abs_vol = round(volume * self.max_volume)
        cmd = volume_set(abs_vol)
        await self.client.shell(cmd, timeout=4.0)

        # Fallback check for TVs ignoring media_session volume --set
        if self.entry.options.get(CONF_VOLUME_STEP_FALLBACK, DEFAULT_VOLUME_STEP_FALLBACK):
            try:
                check_out = await self.client.shell(CMD_VOLUME_GET, timeout=2.5)
                vol_info = parse_volume_get(check_out)
                if vol_info and vol_info[0] != abs_vol:
                    delta = abs_vol - vol_info[0]
                    key = 24 if delta > 0 else 25  # VOLUME_UP / VOLUME_DOWN
                    for _ in range(abs(delta)):
                        await self.async_send_key(key)
                        await asyncio.sleep(0.05)
            except Exception as err:
                _LOGGER.debug("Volume fallback check failed on %s: %s", self.host, err)

        await self.async_request_refresh()

    async def async_mute_volume(self: AndroidTvAdbCoordinator, mute: bool) -> None:
        """Idempotently set volume mute state."""
        cmd = volume_adjust("mute" if mute else "unmute")
        await self.client.shell(cmd, timeout=4.0)
        await self.async_request_refresh()

    async def async_launch_app(self: AndroidTvAdbCoordinator, package_or_name: str, url: str | None = None) -> None:
        """Launch an app package or deep link on the TV."""
        pkg = resolve_app(package_or_name, self.installed_apps) or package_or_name

        # Optimistic update for immediate UI feedback
        if self.data:
            self.data["current_app"] = pkg
            self.data["app_name"] = app_name(pkg)
            self.data["state"] = MediaPlayerState.PLAYING if not is_launcher(pkg) else MediaPlayerState.IDLE
            self.async_set_updated_data(self.data)

        if url:
            cmd = view_uri(url, package=pkg)
            await self.client.shell(cmd, timeout=5.0)
        else:
            launched = False
            cached = self._launch_component_cache.get(pkg)
            if cached:
                res = await self.client.shell(start_component(cached), timeout=5.0)
                if not am_start_failed(res):
                    launched = True

            if not launched:
                try:
                    resolve_cmd = resolve_launch_activity(pkg)
                    out = await self.client.shell(resolve_cmd, timeout=4.0)
                    components = [line.strip() for line in out.splitlines() if "/" in line.strip()]
                    if components:
                        comp = components[0]
                        launch_cmd = start_component(comp)
                        res = await self.client.shell(launch_cmd, timeout=5.0)
                        if not am_start_failed(res):
                            self._launch_component_cache[pkg] = comp
                            launched = True
                except Exception:
                    pass

            if not launched:
                # Fallback to monkey
                await self.client.shell(monkey_launch(pkg), timeout=5.0)

        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_stop_app(self: AndroidTvAdbCoordinator, package_or_name: str) -> None:
        """Force-stop an app package and remove its recents stack."""
        pkg = resolve_app(package_or_name, self.installed_apps) or package_or_name
        # Find matching task in recents if present
        for task in self.open_app_tasks:
            if task.package == pkg:
                await self.client.shell(close_task(task.task_id), timeout=3.0)
        await self.client.shell(force_stop(pkg), timeout=4.0)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_select_input(self: AndroidTvAdbCoordinator, input_id_or_label: str) -> None:
        """Select a hardware input via passthrough URI or keycode fallback."""
        target_input: TvInput | None = None
        for inp in self.inputs:
            if inp.id == input_id_or_label or inp.label.lower() == input_id_or_label.lower():
                target_input = inp
                break

        if target_input:
            if target_input.kind == "tuner":
                await self.async_send_key(170)  # KEY_TV
            elif valid_input_id(target_input.id):
                uri = input_passthrough_uri(target_input.id)
                res = await self.client.shell(view_uri(uri), timeout=5.0)
                if am_start_failed(res) and target_input.key > 0:
                    await self.async_send_key(target_input.key)
            elif target_input.key > 0:
                await self.async_send_key(target_input.key)
        else:
            # Fallback to key alias or direct URI
            if valid_input_id(input_id_or_label):
                uri = input_passthrough_uri(input_id_or_label)
                await self.client.shell(view_uri(uri), timeout=5.0)

        await asyncio.sleep(0.8)
        await self.async_request_refresh()

    async def async_send_text(self: AndroidTvAdbCoordinator, text: str, submit: bool = False) -> None:
        """Type text into focused TV text field and optionally hit enter."""
        cmd = input_text(text)
        await self.client.shell(cmd, timeout=5.0)
        if submit:
            await asyncio.sleep(0.1)
            await self.async_send_key(66)  # KEY_ENTER

    async def async_search(self: AndroidTvAdbCoordinator, query: str, target: str = "global") -> None:
        """Search Android TV globally or on YouTube."""
        cmd = search(query, target)
        await self.client.shell(cmd, timeout=5.0)

    async def async_trim_caches(self: AndroidTvAdbCoordinator) -> str:
        """Trim app caches to reclaim storage."""
        out = await self.client.shell(CMD_TRIM_CACHES, timeout=12.0)
        await self.async_request_refresh()
        return out.strip()

    async def async_start_screensaver(self: AndroidTvAdbCoordinator) -> None:
        """Trigger daydream screensaver."""
        await self.client.shell(CMD_START_SCREENSAVER, timeout=5.0)

    async def async_set_setting(self: AndroidTvAdbCoordinator, namespace: str, key: str, value: Any) -> None:
        """Update an Android global/secure/system setting."""
        cmd = settings_put(namespace, key, value)
        await self.client.shell(cmd, timeout=4.0)
        self.settings[key] = str(value)
        await self.async_request_refresh()

    async def async_run_command(self: AndroidTvAdbCoordinator, command: str) -> str:
        """Run an arbitrary ADB command or named key."""
        key_cmd = command.strip()
        code = resolve_key(key_cmd)
        if code is not None:
            await self.async_send_key(code)
            res = f"Sent keyevent {code} ({key_cmd})"
        else:
            res = await self.client.shell(command, timeout=12.0)
        self.last_adb_response = res.strip() if res else None
        return res

    async def async_reboot(self: AndroidTvAdbCoordinator) -> None:
        """Reboot the Android TV."""
        _LOGGER.info("Sending reboot command to Android TV %s", self.host)
        await self.client.shell("reboot", timeout=5.0)

    async def async_screencap(self: AndroidTvAdbCoordinator) -> bytes:
        """Take a PNG screen capture using exec: service to prevent CRLF corruption."""
        return await self.client.exec_raw("screencap -p", timeout=10.0)
