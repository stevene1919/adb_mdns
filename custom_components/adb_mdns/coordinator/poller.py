"""Fast-tier state update polling mixin for AndroidTvAdbCoordinator."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..const import (
    CONF_HEALTH_INTERVAL,
    CONF_PORT,
    CONF_SCREENCAP_INTERVAL,
    DEFAULT_HEALTH_INTERVAL,
    DEFAULT_SCREENCAP_INTERVAL,
)
from ..core import AdbAuthError, AdbConnectionError, AdbTimeoutError
from ..tv import (
    CMD_KEYBOARD_TEXT,
    CMD_POLL_STATUS,
    app_name,
    current_position,
    is_launcher,
    parse_active_hdmi,
    parse_audio,
    parse_awake,
    parse_foreground,
    parse_keyboard_proto,
    parse_keyboard_text,
    parse_media_sessions,
    parse_uptime_ms,
    pick_media_session,
    split_sections,
)

if TYPE_CHECKING:
    from . import AndroidTvAdbCoordinator

_LOGGER = logging.getLogger(__name__)


class CoordinatorPollerMixin:
    """Mixin implementing the fast-tier poll and coordinator state update."""

    async def _async_update_data(self: AndroidTvAdbCoordinator) -> dict[str, Any]:
        """Fetch current state of Android TV via fast ADB poll and periodic slow telemetry."""
        if not self.client.is_connected:
            if self.client.port <= 0:
                discovered = await self.async_discover_port()
                if discovered > 0:
                    self.client.update_port(discovered)
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={**self.entry.data, CONF_PORT: discovered},
                    )

            try:
                await self.client.connect(timeout=6.0)
            except AdbConnectionError as err:
                discovered = await self.async_discover_port()
                if discovered > 0 and discovered != self.client.port:
                    _LOGGER.info("Re-trying connection to %s on discovered TLS port %s", self.host, discovered)
                    self.client.update_port(discovered)
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={**self.entry.data, CONF_PORT: discovered},
                    )
                    try:
                        await self.client.connect(timeout=6.0)
                    except Exception as retry_err:
                        raise UpdateFailed(f"Device offline or unreachable at {self.host}:{discovered}") from retry_err
                else:
                    raise UpdateFailed(f"Device offline or unreachable at {self.host}:{self.client.port}") from err
            except AdbAuthError as err:
                raise UpdateFailed("Device rejected connection - pairing may have been revoked") from err

        # Deferred device properties check
        if not self.device_properties.get("sw_version") or not self.device_properties.get("model"):
            await self.async_fetch_device_properties()

        data: dict[str, Any] = {
            "state": MediaPlayerState.OFF,
            "is_on": False,
            "current_app": None,
            "app_name": None,
            "volume_level": None,
            "is_volume_muted": None,
            "hdmi_input": None,
            "adb_response": self.last_adb_response,
            "running_apps": self.running_apps,
            "open_apps_count": len(self.running_apps),
            "keyboard_active": False,
            "screencap_bytes": self._last_screencap_bytes,
            "screencap_hash": self._last_screencap_hash,
            "media_title": None,
            "media_artist": None,
            "media_album": None,
            "media_position": None,
            "media_position_updated_at": None,
            "media_actions": 0,
            "audio_output": None,
            "temperature": None,
            "thermal_status": None,
            "memory_usage": None,
            "memory_available_mb": None,
            "storage_available_mb": None,
            "cpu_load": self.cpu_load,
            "bluetooth_devices": [],
            "last_wake_reason": self.power_reasons.get("last_wake_reason"),
            "last_sleep_reason": self.power_reasons.get("last_sleep_reason"),
            "wake_locks": self.power_reasons.get("wake_locks", []),
            "settings": self.settings,
        }

        try:
            output = await self.client.shell(CMD_POLL_STATUS, timeout=7.5)
            sections = split_sections(output)

            # 1. Power / Wakefulness / Screen state
            pwr_str = sections.get("POWER", output)
            is_awake = parse_awake(pwr_str)
            if is_awake is False:
                data["is_on"] = False
                data["state"] = MediaPlayerState.OFF
                self._last_state = MediaPlayerState.OFF
                return data

            data["is_on"] = True
            data["state"] = MediaPlayerState.IDLE

            # 2. Foreground Activity
            act_str = sections.get("ACT", output)
            win_str = sections.get("WIN", output)
            current_app = parse_foreground(act_str, win_str)
            if current_app:
                data["current_app"] = current_app
                data["app_name"] = app_name(current_app)

            # 3. MediaSession PlaybackState & Metadata
            media_str = sections.get("MEDIA", output)
            uptime_str = sections.get("UPTIME", "")
            uptime_ms = parse_uptime_ms(uptime_str)

            sessions = parse_media_sessions(media_str)
            chosen_session = pick_media_session(sessions, current_app)
            self.active_media_session = chosen_session

            if chosen_session:
                if chosen_session.state == 3:  # PLAYING
                    data["state"] = MediaPlayerState.PLAYING
                elif chosen_session.state == 2:  # PAUSED
                    data["state"] = MediaPlayerState.PAUSED
                elif chosen_session.state in (1, 0):  # STOPPED / NONE
                    data["state"] = MediaPlayerState.IDLE

                data["media_title"] = chosen_session.title
                data["media_artist"] = chosen_session.artist
                data["media_album"] = chosen_session.album
                data["media_actions"] = chosen_session.actions

                pos = current_position(chosen_session, uptime_ms)
                if pos is not None:
                    data["media_position"] = pos
                    data["media_position_updated_at"] = time.time()
                    self.media_position = pos
                    self.media_position_updated_at = data["media_position_updated_at"]

            # Launcher is IDLE
            if is_launcher(current_app) and data["state"] != MediaPlayerState.PLAYING:
                data["state"] = MediaPlayerState.IDLE

            # 4. Stream Music Volume & Mute
            audio_str = sections.get("AUDIO", output)
            self.audio_state = parse_audio(audio_str)
            if self.audio_state.max_volume:
                self.max_volume = float(self.audio_state.max_volume)
            if self.audio_state.muted is not None:
                data["is_volume_muted"] = self.audio_state.muted
            if self.audio_state.volume is not None:
                data["volume_level"] = min(1.0, max(0.0, self.audio_state.volume / self.max_volume))
            data["audio_output"] = self.audio_state.output_name

            # 5. Active HDMI Input
            tvin_str = sections.get("TVIN", "")
            hdmi_port = parse_active_hdmi(tvin_str)
            if hdmi_port is not None:
                data["hdmi_input"] = f"HDMI {hdmi_port}"

            # 6. Keyboard / Text field detection
            ime_str = sections.get("IME", "")
            kb_proto = parse_keyboard_proto(ime_str) if self._proto_failed_count < 30 else None
            if kb_proto is not None:
                data["keyboard_active"] = kb_proto
                self._proto_failed_count = 0
            else:
                self._proto_failed_count += 1
                try:
                    txt_out = await self.client.shell(CMD_KEYBOARD_TEXT, timeout=2.5)
                    data["keyboard_active"] = parse_keyboard_text(txt_out)
                except Exception:
                    data["keyboard_active"] = False
            self.keyboard_active = data["keyboard_active"]

            now = time.time()
            # 7. Slow-tier Telemetry poll (Health, recents, settings, inputs)
            opts = getattr(self.entry, "options", {}) or {}
            raw_h = (
                opts.get(CONF_HEALTH_INTERVAL, DEFAULT_HEALTH_INTERVAL)
                if isinstance(opts, dict)
                else DEFAULT_HEALTH_INTERVAL
            )
            try:
                health_interval = float(raw_h)
            except (ValueError, TypeError):
                health_interval = float(DEFAULT_HEALTH_INTERVAL)
            if (now - self._last_health_time) >= health_interval:
                await self._async_update_health()

            # Refresh data mapping from health state
            if self.thermal_state:
                data["temperature"] = self.thermal_state.max_temperature
                data["thermal_status"] = self.thermal_state.status
            if self.mem_info:
                total_kb, avail_kb = self.mem_info
                data["memory_available_mb"] = round(avail_kb / 1024, 1)
                if total_kb > 0:
                    data["memory_usage"] = round(100.0 * (total_kb - avail_kb) / total_kb, 1)
            if self.storage_info:
                avail_bytes, _ = self.storage_info
                data["storage_available_mb"] = round(avail_bytes / (1024 * 1024), 1)
            data["cpu_load"] = self.cpu_load
            if self.bluetooth_info:
                data["bluetooth_devices"] = self.bluetooth_info.get("devices", [])
            data["running_apps"] = self.running_apps
            data["open_apps_count"] = len(self.running_apps)
            data["settings"] = self.settings

            # 8. Installed apps refresh (every 10 minutes)
            if (not self.installed_apps or (now - self._last_installed_apps_time) >= 600.0) and data["is_on"]:
                await self.async_refresh_installed_apps()

            # 9. Screencap (configured interval, 0 to disable)
            opts = getattr(self.entry, "options", {}) or {}
            raw_sc = (
                opts.get(CONF_SCREENCAP_INTERVAL, DEFAULT_SCREENCAP_INTERVAL)
                if isinstance(opts, dict)
                else DEFAULT_SCREENCAP_INTERVAL
            )
            try:
                screencap_interval = float(raw_sc)
            except (ValueError, TypeError):
                screencap_interval = float(DEFAULT_SCREENCAP_INTERVAL)
            if screencap_interval > 0 and data["is_on"]:
                app_changed = current_app != self._last_app
                time_due = (now - self._last_screencap_time) >= float(screencap_interval)
                if app_changed or time_due or not self._last_screencap_bytes:
                    try:
                        img_bytes = await self.async_screencap()
                        if img_bytes and img_bytes.startswith(b"\x89PNG"):
                            self._last_screencap_bytes = img_bytes
                            self._last_screencap_hash = hashlib.sha256(img_bytes).hexdigest()[:16]
                            self._last_screencap_time = now
                            data["screencap_bytes"] = self._last_screencap_bytes
                            data["screencap_hash"] = self._last_screencap_hash
                    except Exception as err:
                        _LOGGER.debug("Could not take screencap during poll: %s", err)

            self._last_app = current_app
            self._last_state = data["state"]
            return data

        except AdbTimeoutError as err:
            _LOGGER.debug("Timeout polling Android TV status: %s", err)
            raise UpdateFailed(f"Timeout communicating with {self.host}") from err
        except Exception as err:
            _LOGGER.debug("ADB error polling %s: %s", self.host, err)
            await self.client.disconnect()
            raise UpdateFailed(f"ADB polling failed: {err}") from err
