"""Media Player platform for Android TV ADB."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_INCLUDE_LAUNCHER_IN_SOURCES,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES,
    DOMAIN,
)
from ..coordinator import AndroidTvAdbCoordinator
from ..entity import AndroidTvAdbEntity
from ..tv import (
    APPS,
    app_name,
    is_launcher,
)
from .controls import AndroidTvAdbMediaPlayerControlsMixin

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV ADB media player."""
    coordinator: AndroidTvAdbCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and isinstance(entry.runtime_data, AndroidTvAdbCoordinator)
        else hass.data[DOMAIN][entry.entry_id]
    )
    async_add_entities([AndroidTvAdbMediaPlayer(coordinator, entry)])


class AndroidTvAdbMediaPlayer(
    AndroidTvAdbMediaPlayerControlsMixin,
    AndroidTvAdbEntity,
    MediaPlayerEntity,
):
    """Representation of an Android TV Media Player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_media_player"
        self._last_image_data: bytes | None = None

    @property
    def state(self) -> MediaPlayerState:
        """Return the current playback/power state."""
        if self.coordinator.data:
            return self.coordinator.data.get("state", MediaPlayerState.OFF)
        return MediaPlayerState.OFF

    @property
    def app_id(self) -> str | None:
        """Return current foreground app package ID."""
        if self.coordinator.data:
            return self.coordinator.data.get("current_app")
        return None

    @property
    def app_name(self) -> str | None:
        """Return current foreground application friendly name."""
        if not self.coordinator.data:
            return None
        custom_apps = self.entry.options.get(CONF_APPS, {})
        return app_name(self.coordinator.data.get("current_app"), custom_apps) or self.coordinator.data.get("app_name")

    @property
    def source(self) -> str | None:
        """Return current friendly application name or active HDMI input."""
        if not self.coordinator.data:
            return None
        if hdmi := self.coordinator.data.get("hdmi_input"):
            return hdmi
        return self.app_name

    def _paired_audio_bluetooth_devices(self) -> list[dict[str, Any]]:
        """Return paired Bluetooth audio devices with unique display labels."""
        raw_devices: list[dict[str, Any]] = []
        if self.coordinator.data and isinstance(self.coordinator.data.get("bluetooth_devices"), list):
            raw_devices = self.coordinator.data["bluetooth_devices"]
        elif self.coordinator.bluetooth_info and isinstance(self.coordinator.bluetooth_info.get("devices"), list):
            raw_devices = self.coordinator.bluetooth_info["devices"]

        audio_devs = [d for d in raw_devices if d.get("type") == "audio"]
        name_counts: dict[str, int] = {}
        for d in audio_devs:
            n = str(d.get("name", "")).strip()
            name_counts[n] = name_counts.get(n, 0) + 1

        labeled: list[dict[str, Any]] = []
        for d in audio_devs:
            n = str(d.get("name", "")).strip()
            addr = str(d.get("address", "")).upper()
            short_mac = addr[-5:] if len(addr) >= 5 else addr
            label = f"{n} ({short_mac})" if name_counts.get(n, 0) > 1 else (n or addr)
            labeled.append({**d, "label": label})
        return labeled

    @property
    def sound_mode(self) -> str | None:
        """Return the current active audio output / Bluetooth headphone."""
        for d in self._paired_audio_bluetooth_devices():
            if d.get("connected"):
                return d["label"]
        if self.coordinator.data and (out := self.coordinator.data.get("audio_output")):
            return out
        return "TV Speaker" if self.coordinator.is_tv_panel else "HDMI"

    @property
    def sound_mode_list(self) -> list[str]:
        """Return available audio output modes including paired Bluetooth headphones."""
        default_out = "TV Speaker" if self.coordinator.is_tv_panel else "HDMI"
        if self.coordinator.data:
            cur_out = self.coordinator.data.get("audio_output")
            if cur_out and cur_out != "Bluetooth":
                default_out = cur_out
        modes: list[str] = [default_out]
        for d in self._paired_audio_bluetooth_devices():
            lbl = d["label"]
            if lbl and lbl not in modes:
                modes.append(lbl)
        return modes

    @property
    def source_list(self) -> list[str]:
        """Dynamically construct source list with hardware inputs and installed apps."""
        sources: list[str] = []

        # 1. Hardware TV Inputs (HDMI, AV, Tuner, etc.)
        for inp in self.coordinator.inputs:
            sources.append(inp.label)

        # 2. Installed applications
        if self.entry.options.get(CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES):
            exclude_unnamed = self.entry.options.get(CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS)
            include_launcher = self.entry.options.get(CONF_INCLUDE_LAUNCHER_IN_SOURCES, DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES)
            custom_apps = self.entry.options.get(CONF_APPS, {})

            app_packages = set(self.coordinator.installed_apps or list(APPS.keys()))
            app_packages.update(custom_apps.keys())
            for pkg in sorted(app_packages):
                if not include_launcher and is_launcher(pkg):
                    continue
                friendly = app_name(pkg, custom_apps)
                if exclude_unnamed and friendly == pkg:
                    continue
                if friendly and friendly not in sources:
                    sources.append(friendly)

        return sources

    @property
    def volume_level(self) -> float | None:
        """Volume level of media player (0.0 to 1.0)."""
        if self.coordinator.data:
            return self.coordinator.data.get("volume_level")
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if self.coordinator.data:
            return self.coordinator.data.get("is_volume_muted")
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_title")
        return None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_artist")
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_album")
        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position")
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position_updated_at")
        return None

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image to trigger frontend refresh."""
        if self.state == MediaPlayerState.OFF:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("screencap_hash")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes matching reference ADB integration."""
        bt_audio = [
            {
                "name": d.get("name"),
                "address": d.get("address"),
                "connected": bool(d.get("connected")),
            }
            for d in self._paired_audio_bluetooth_devices()
        ]
        return {
            "adb_response": self.coordinator.data.get("adb_response") if self.coordinator.data else None,
            "hdmi_input": self.coordinator.data.get("hdmi_input") if self.coordinator.data else None,
            "audio_output": self.coordinator.data.get("audio_output") if self.coordinator.data else None,
            "bluetooth_audio_devices": bt_audio,
            "keyboard_active": self.coordinator.data.get("keyboard_active", False) if self.coordinator.data else False,
            "open_apps_count": self.coordinator.data.get("open_apps_count", 0) if self.coordinator.data else 0,
        }


__all__ = ["AndroidTvAdbMediaPlayer", "async_setup_entry"]
