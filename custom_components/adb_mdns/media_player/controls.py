"""Controls and actions mixin for AndroidTvAdbMediaPlayer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    MediaClass,
    MediaType,
)
from homeassistant.components.media_player.browse_media import BrowseMedia

from ..const import (
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    KEY_MEDIA_NEXT,
    KEY_MEDIA_PLAY_PAUSE,
    KEY_MEDIA_PREVIOUS,
    KEY_MEDIA_STOP,
    KEY_PAUSE,
    KEY_PLAY,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
)
from ..tv import APPS, app_name, app_thumbnail

if TYPE_CHECKING:
    from . import AndroidTvAdbMediaPlayer


class AndroidTvAdbMediaPlayerControlsMixin:
    """Mixin implementing player actions, volume, source selection, and media browse."""

    async def async_get_media_image(self: AndroidTvAdbMediaPlayer) -> tuple[bytes | None, str | None]:
        """Serve screen capture image data."""
        if self.coordinator.data and (img := self.coordinator.data.get("screencap_bytes")):
            self._last_image_data = img
            return img, "image/png"
        if self._last_image_data:
            return self._last_image_data, "image/png"
        return None, None

    async def async_turn_on(self: AndroidTvAdbMediaPlayer) -> None:
        """Turn on the TV."""
        await self.coordinator.async_power_on()

    async def async_turn_off(self: AndroidTvAdbMediaPlayer) -> None:
        """Turn off the TV."""
        await self.coordinator.async_power_off()

    async def async_volume_up(self: AndroidTvAdbMediaPlayer) -> None:
        """Step volume up."""
        await self.coordinator.async_send_key(KEY_VOLUME_UP)
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self: AndroidTvAdbMediaPlayer) -> None:
        """Step volume down."""
        await self.coordinator.async_send_key(KEY_VOLUME_DOWN)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self: AndroidTvAdbMediaPlayer, volume: float) -> None:
        """Set relative volume level (0.0 to 1.0)."""
        await self.coordinator.async_set_volume_level(volume)

    async def async_mute_volume(self: AndroidTvAdbMediaPlayer, mute: bool) -> None:
        """Mute / Unmute volume."""
        await self.coordinator.async_mute_volume(mute)

    async def async_media_play(self: AndroidTvAdbMediaPlayer) -> None:
        """Send play command."""
        await self.coordinator.async_send_key(KEY_PLAY)
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self: AndroidTvAdbMediaPlayer) -> None:
        """Send pause command."""
        await self.coordinator.async_send_key(KEY_PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_media_play_pause(self: AndroidTvAdbMediaPlayer) -> None:
        """Send play/pause toggle."""
        await self.coordinator.async_send_key(KEY_MEDIA_PLAY_PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self: AndroidTvAdbMediaPlayer) -> None:
        """Send media stop."""
        await self.coordinator.async_send_key(KEY_MEDIA_STOP)
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self: AndroidTvAdbMediaPlayer) -> None:
        """Send next track."""
        await self.coordinator.async_send_key(KEY_MEDIA_NEXT)

    async def async_media_previous_track(self: AndroidTvAdbMediaPlayer) -> None:
        """Send previous track."""
        await self.coordinator.async_send_key(KEY_MEDIA_PREVIOUS)

    async def async_media_seek(self: AndroidTvAdbMediaPlayer, position: float) -> None:
        """Seek to position in seconds."""
        pos_ms = int(position * 1000)
        cmd = f"cmd media_session seek {pos_ms} 2>/dev/null"
        await self.coordinator.client.shell(cmd, timeout=4.0)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self: AndroidTvAdbMediaPlayer, source: str) -> None:
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

    async def async_play_media(
        self: AndroidTvAdbMediaPlayer, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media or launch app / deep-link URL / numeric channel."""
        if media_type in (MediaType.CHANNEL, "channel"):
            if not media_id.isnumeric():
                await self.coordinator.async_launch_app("", url=media_id)
                return
            for ch in media_id:
                # Keycodes for '0' through '9' are 7 through 16 (KEYCODE_0=7, KEYCODE_9=16)
                keycode = 7 + int(ch)
                await self.coordinator.async_send_key(keycode)
                await asyncio.sleep(0.1)
            return

        if media_type in (MediaType.APP, "app"):
            await self.coordinator.async_launch_app(media_id)
        elif media_type in (MediaType.URL, "url"):
            await self.coordinator.async_launch_app("", url=media_id)
        else:
            await self.coordinator.async_launch_app(media_id)

    async def async_browse_media(
        self: AndroidTvAdbMediaPlayer,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media browser for installed Android TV applications."""
        installed = self.coordinator.installed_apps or list(APPS.keys())
        children = []

        opts = getattr(self.entry, "options", {}) or {}
        exclude_unnamed = opts.get(CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS) if isinstance(opts, dict) else DEFAULT_EXCLUDE_UNNAMED_APPS
        custom_apps = opts.get(CONF_APPS, {}) if isinstance(opts, dict) else {}

        for pkg in sorted(installed):
            friendly_name = app_name(pkg, custom_apps)
            if exclude_unnamed and friendly_name == pkg:
                continue
            children.append(
                BrowseMedia(
                    title=friendly_name,
                    media_class=MediaClass.APP,
                    media_content_id=pkg,
                    media_content_type=MediaType.APP,
                    can_play=True,
                    can_expand=False,
                    thumbnail=app_thumbnail(pkg),
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
