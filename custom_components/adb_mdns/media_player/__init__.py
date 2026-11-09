"""Media Player platform for Android TV ADB."""

from __future__ import annotations

import logging
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
    ACTION_SEEK_TO as ADB_ACTION_SEEK_TO,
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

    def __init__(self, coordinator: AndroidTvAdbCoordinator, entry: ConfigEntry) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_HOST]}_media_player"
        self._last_image_data: bytes | None = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Dynamically compute supported features based on playback state and session actions."""
        features = (
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
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )
        if self.coordinator.data and (actions := self.coordinator.data.get("media_actions", 0)) and (actions & ADB_ACTION_SEEK_TO):
            features |= MediaPlayerEntityFeature.SEEK
        return features

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
    def source(self) -> str | None:
        """Return current friendly application name or active HDMI input."""
        if not self.coordinator.data:
            return None
        if hdmi := self.coordinator.data.get("hdmi_input"):
            return hdmi
        custom_apps = self.entry.options.get(CONF_APPS, {})
        return app_name(self.coordinator.data.get("current_app"), custom_apps) or self.coordinator.data.get("app_name")

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
    def media_position(self) -> float | None:
        """Position of current playing media in seconds."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position")
        return None

    @property
    def media_position_updated_at(self) -> float | None:
        """When was the position of the current playing media valid."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position_updated_at")
        return None

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image to trigger frontend refresh."""
        if self.coordinator.data:
            return self.coordinator.data.get("screencap_hash")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes matching reference ADB integration."""
        attrs: dict[str, Any] = {
            "adb_response": self.coordinator.data.get("adb_response") if self.coordinator.data else None,
            "hdmi_input": self.coordinator.data.get("hdmi_input") if self.coordinator.data else None,
            "audio_output": self.coordinator.data.get("audio_output") if self.coordinator.data else None,
            "keyboard_active": self.coordinator.data.get("keyboard_active", False) if self.coordinator.data else False,
            "open_apps_count": self.coordinator.data.get("open_apps_count", 0) if self.coordinator.data else 0,
        }
        if self.coordinator.data and (app_id := self.coordinator.data.get("current_app")):
            attrs["app_id"] = app_id
        return attrs


__all__ = ["AndroidTvAdbMediaPlayer", "async_setup_entry"]
