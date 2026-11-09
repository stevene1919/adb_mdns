"""Media Player platform for Android TV ADB."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_INCLUDE_LAUNCHER_IN_SOURCES,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES,
    DOMAIN,
    KEY_MEDIA_NEXT,
    KEY_MEDIA_PLAY_PAUSE,
    KEY_MEDIA_PREVIOUS,
    KEY_MEDIA_STOP,
    KEY_PAUSE,
    KEY_PLAY,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
)
from .coordinator import AndroidTvAdbCoordinator
from .entity import AndroidTvAdbEntity
from .tv import (
    ACTION_SEEK_TO as ADB_ACTION_SEEK_TO,
    APPS,
    app_name,
    is_launcher,
)

_LOGGER = logging.getLogger(__name__)


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


class AndroidTvAdbMediaPlayer(AndroidTvAdbEntity, MediaPlayerEntity):
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
        if not self.coordinator.data:
            return MediaPlayerState.OFF
        return self.coordinator.data.get("state", MediaPlayerState.OFF)

    @property
    def app_id(self) -> str | None:
        """Return the currently focused app package name."""
        if self.coordinator.data:
            return self.coordinator.data.get("current_app")
        return None

    @property
    def source(self) -> str | None:
        """Return the friendly name of the current app or input."""
        if not self.coordinator.data:
            return None
        # If HDMI input is active, prioritize input label
        hdmi = self.coordinator.data.get("hdmi_input")
        if hdmi:
            for inp in self.coordinator.inputs:
                if inp.kind == "hdmi" and f"HDMI {inp.port}" == hdmi:
                    return inp.label
            return hdmi
        return self.coordinator.data.get("app_name") or self.coordinator.data.get("current_app")

    @property
    def source_list(self) -> list[str]:
        """Return a sorted list of friendly available app sources and hardware inputs."""
        sources: set[str] = set()

        # 1. Add Hardware Inputs (HDMI 1 · PS5, etc.)
        for inp in self.coordinator.inputs:
            sources.add(inp.label)

        # 2. Add Installed / Supported Apps
        installed = self.coordinator.installed_apps
        exclude_unnamed = self.entry.options.get(CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS)
        include_launcher = self.entry.options.get(CONF_INCLUDE_LAUNCHER_IN_SOURCES, DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES)

        app_pool = installed if installed else list(APPS.keys())
        for pkg in app_pool:
            if not include_launcher and is_launcher(pkg):
                continue
            name = APPS.get(pkg)
            if name:
                sources.add(name)
            elif not exclude_unnamed:
                sources.add(pkg)

        return sorted(list(sources))

    @property
    def volume_level(self) -> float | None:
        """Return current volume level (0.0 to 1.0)."""
        if self.coordinator.data:
            return self.coordinator.data.get("volume_level")
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean whether volume is currently muted."""
        if self.coordinator.data:
            return self.coordinator.data.get("is_volume_muted")
        return None

    @property
    def media_title(self) -> str | None:
        """Title of currently playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_title")
        return None

    @property
    def media_artist(self) -> str | None:
        """Artist / Channel of currently playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_artist")
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album of currently playing media."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_album")
        return None

    @property
    def media_position(self) -> float | None:
        """Current playback position in seconds."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position")
        return None

    @property
    def media_position_updated_at(self) -> float | None:
        """Timestamp when position was updated."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position_updated_at")
        return None

    @property
    def media_image_hash(self) -> str | None:
        """Return current media image hash from coordinator."""
        if self.coordinator.data and self.state != MediaPlayerState.OFF:
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

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Serve screen capture image data."""
        if self.coordinator.data and (img := self.coordinator.data.get("screencap_bytes")):
            self._last_image_data = img
            return img, "image/png"
        if self._last_image_data:
            return self._last_image_data, "image/png"
        return None, None

    async def async_turn_on(self) -> None:
        """Turn on the TV."""
        await self.coordinator.async_power_on()

    async def async_turn_off(self) -> None:
        """Turn off the TV."""
        await self.coordinator.async_power_off()

    async def async_volume_up(self) -> None:
        """Step volume up."""
        await self.coordinator.async_send_key(KEY_VOLUME_UP)
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Step volume down."""
        await self.coordinator.async_send_key(KEY_VOLUME_DOWN)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set relative volume level (0.0 to 1.0)."""
        await self.coordinator.async_set_volume_level(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute / Unmute volume."""
        await self.coordinator.async_mute_volume(mute)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.async_send_key(KEY_PLAY)
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.async_send_key(KEY_PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_media_play_pause(self) -> None:
        """Send play/pause toggle."""
        await self.coordinator.async_send_key(KEY_MEDIA_PLAY_PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send media stop."""
        await self.coordinator.async_send_key(KEY_MEDIA_STOP)
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track."""
        await self.coordinator.async_send_key(KEY_MEDIA_NEXT)

    async def async_media_previous_track(self) -> None:
        """Send previous track."""
        await self.coordinator.async_send_key(KEY_MEDIA_PREVIOUS)

    async def async_media_seek(self, position: float) -> None:
        """Seek to position in seconds."""
        pos_ms = int(position * 1000)
        cmd = f"cmd media_session seek {pos_ms} 2>/dev/null"
        await self.coordinator.client.shell(cmd, timeout=4.0)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select input source or stop app (if prefixed with '!')."""
        if source.startswith("!"):
            raw_source = source[1:].strip()
            await self.coordinator.async_stop_app(raw_source)
            return

        # Check if source is a hardware input
        for inp in self.coordinator.inputs:
            if inp.label == source or inp.id == source:
                await self.coordinator.async_select_input(inp.id)
                return

        await self.coordinator.async_launch_app(source)

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        """Play media or launch app / deep-link URL."""
        if media_type in (MediaType.APP, "app"):
            await self.coordinator.async_launch_app(media_id)
        elif media_type in (MediaType.URL, "url", "channel"):
            await self.coordinator.async_launch_app("", url=media_id)
        else:
            await self.coordinator.async_launch_app(media_id)

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media browser for installed Android TV applications."""
        installed = self.coordinator.installed_apps or list(APPS.keys())
        children = []

        for pkg in sorted(installed):
            friendly_name = app_name(pkg)
            children.append(
                BrowseMedia(
                    title=friendly_name,
                    media_class=MediaClass.APP,
                    media_content_id=pkg,
                    media_content_type=MediaType.APP,
                    can_play=True,
                    can_expand=False,
                    thumbnail=None,
                )
            )

        return BrowseMedia(
            title="Android TV Apps",
            media_class=MediaClass.DIRECTORY,
            media_content_id="root",
            media_content_type="root",
            can_play=False,
            can_expand=True,
            children=children,
        )
