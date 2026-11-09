"""DataUpdateCoordinator for Android TV ADB."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from zeroconf.asyncio import AsyncServiceBrowser

from ..const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from ..core import AndroidTvAdbClient
from ..tv import (
    AudioState,
    MediaSession,
    RecentTask,
    ThermalState,
    TvInput,
)
from .actions import CoordinatorActionsMixin
from .discovery import CoordinatorDiscoveryMixin
from .lifecycle import CoordinatorLifecycleMixin
from .poller import CoordinatorPollerMixin
from .registry import CoordinatorRegistryMixin

_LOGGER = logging.getLogger(__name__)


class AndroidTvAdbCoordinator(
    CoordinatorActionsMixin,
    CoordinatorDiscoveryMixin,
    CoordinatorRegistryMixin,
    CoordinatorLifecycleMixin,
    CoordinatorPollerMixin,
    DataUpdateCoordinator[dict[str, Any]],
):
    """Coordinator to manage fetching Android TV status via ADB over TLS 1.3."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AndroidTvAdbClient,
    ) -> None:
        opts = getattr(entry, "options", {}) or {}
        raw_interval = (
            opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) if isinstance(opts, dict) else DEFAULT_SCAN_INTERVAL
        )
        try:
            scan_interval = float(raw_interval)
        except (ValueError, TypeError):
            scan_interval = float(DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.data[CONF_HOST]})",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client
        self.host = entry.data[CONF_HOST]
        self._browser: AsyncServiceBrowser | None = None
        self.max_volume: float = 15.0
        self.installed_apps: list[str] = []
        self.running_apps: list[str] = []
        self.open_app_tasks: list[RecentTask] = []
        self.inputs: list[TvInput] = []
        self.audio_state: AudioState = AudioState()
        self.thermal_state: ThermalState | None = None
        self.mem_info: tuple[int, int] | None = None
        self.storage_info: tuple[int, int] | None = None
        self.cpu_load: float | None = None
        self._last_cpu_times: tuple[int, int] | None = None
        self.power_reasons: dict[str, Any] = {}
        self.bluetooth_info: dict[str, Any] | None = None
        self.settings: dict[str, str] = {}
        self.keyboard_active: bool = False
        self._proto_failed_count: int = 0
        self._last_installed_apps_time: float = 0.0
        self._last_health_time: float = 0.0
        self._last_screencap_time: float = 0.0
        self._last_screencap_bytes: bytes | None = None
        self._last_screencap_hash: str | None = None
        self._last_app: str | None = None
        self._last_state: MediaPlayerState = MediaPlayerState.OFF
        self.last_adb_response: str | None = None
        self.active_media_session: MediaSession | None = None
        self.media_position: float | None = None
        self.media_position_updated_at: float | None = None
        self.device_properties: dict[str, str] = {
            "name": entry.data.get("name") or entry.title or "",
            "manufacturer": entry.data.get("manufacturer") or "",
            "model": entry.data.get("model") or "",
            "sw_version": entry.data.get("sw_version") or "",
            "serialno": entry.data.get("serialno") or "",
            "mac": entry.data.get("mac") or "",
            "interface": "",
        }

    @property
    def is_connected(self) -> bool:
        """Return True if ADB client is connected."""
        return self.client.is_connected

    @property
    def is_tv_panel(self) -> bool:
        """Return True if the target device is a physical TV panel with HDMI inputs."""
        model = (self.device_properties.get("model") or "").lower()
        mfg = (self.device_properties.get("manufacturer") or "").lower()
        dev_type = str(self.device_properties.get("hdmi_device_type") or "").strip()

        # Obvious playback devices/dongles (e.g. Chromecast, Fire TV, Shield, Mi Box)
        if "chromecast" in model or "chromecast" in mfg:
            return False
        if dev_type == "4":  # HDMI-CEC Playback Device
            return False
        if any(term in model for term in ("shield", "fire tv stick", "firestick", "mi box", "onn.", "stick")):
            return False

        # If it has enumerated physical hardware inputs, it's definitely a TV
        if any(inp.kind == "hdmi" for inp in self.inputs):
            return True

        # If hdmi_device_type is explicitly 0 (TV)
        if dev_type == "0":
            return True

        # Fallback: if model has "tv" and not a streaming stick/box
        return "tv" in model and not any(term in model for term in ("stick", "box", "dongle"))


__all__ = ["AndroidTvAdbCoordinator"]
