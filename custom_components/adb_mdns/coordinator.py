"""DataUpdateCoordinator for Android TV ADB."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components import zeroconf
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from zeroconf.asyncio import AsyncServiceBrowser

from .const import (
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_WOL,
    CONF_HEALTH_INTERVAL,
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SCREENCAP_INTERVAL,
    CONF_VOLUME_STEP_FALLBACK,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_WOL,
    DEFAULT_HEALTH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCREENCAP_INTERVAL,
    DEFAULT_VOLUME_STEP_FALLBACK,
    DOMAIN,
)
from .core import (
    AdbAuthError,
    AdbConnectionError,
    AdbTimeoutError,
    AndroidTvAdbClient,
    async_send_magic_packet,
)
from .tv import (
    CMD_DEVICE_PROPERTIES,
    CMD_KEYBOARD_TEXT,
    CMD_LIST_PACKAGES,
    CMD_POLL_STATUS,
    CMD_START_SCREENSAVER,
    CMD_TRIM_CACHES,
    CMD_VOLUME_GET,
    KEY_SLEEP,
    KEY_WAKEUP,
    AudioState,
    MediaSession,
    RecentTask,
    ThermalState,
    TvInput,
    am_start_failed,
    app_name,
    build_health_command,
    close_task,
    cpu_percent,
    current_position,
    force_stop,
    input_passthrough_uri,
    input_text,
    is_launcher,
    monkey_launch,
    open_apps,
    parse_active_hdmi,
    parse_audio,
    parse_awake,
    parse_bluetooth,
    parse_cpu_times,
    parse_device_properties,
    parse_foreground,
    parse_keyboard_proto,
    parse_keyboard_text,
    parse_kv,
    parse_media_sessions,
    parse_meminfo,
    parse_packages,
    parse_power_reasons,
    parse_recents,
    parse_storage,
    parse_thermal,
    parse_tv_inputs,
    parse_uptime_ms,
    parse_volume_get,
    pick_media_session,
    resolve_app,
    resolve_key,
    resolve_launch_activity,
    search,
    settings_put,
    split_sections,
    start_component,
    valid_input_id,
    view_uri,
    volume_adjust,
    volume_set,
)

_LOGGER = logging.getLogger(__name__)

MDNS_CONNECT_TYPE = "_adb-tls-connect._tcp.local."


class AndroidTvAdbCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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

    async def async_fetch_device_properties(self) -> dict[str, str]:
        """Fetch hardware and firmware properties safely with key-value parser."""
        try:
            out = await self.client.shell(CMD_DEVICE_PROPERTIES, timeout=8.0)
            parsed = parse_device_properties(out, host=self.host)

            dev_name = parsed["name"] or self.device_properties.get("name") or "Android TV"
            mfg = parsed["manufacturer"] or self.device_properties.get("manufacturer") or "Google"
            mdl = parsed["model"] or self.device_properties.get("model") or "Android TV"
            ver = parsed["sw_version"] or self.device_properties.get("sw_version") or ""
            ser = parsed["serialno"] or self.device_properties.get("serialno") or ""
            mac = parsed["mac"] or self.device_properties.get("mac") or self.entry.data.get(CONF_MAC, "")

            self.device_properties = {
                "name": dev_name,
                "manufacturer": mfg,
                "model": mdl,
                "sw_version": ver,
                "serialno": ser,
                "mac": mac,
                "interface": parsed.get("interface", ""),
            }
            _LOGGER.info("Updated device properties for %s: %s", self.host, self.device_properties)

            self.hass.config_entries.async_update_entry(
                self.entry,
                title=dev_name,
                data={**self.entry.data, **self.device_properties},
            )
            # Live device registry update
            self.async_update_device_registry()
        except Exception as err:
            _LOGGER.debug("Could not fetch device properties: %s", err)
        return self.device_properties

    def async_update_device_registry(self) -> None:
        """Update the device registry with dynamic properties."""
        try:
            from homeassistant.helpers import device_registry as dr

            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get_device(identifiers={(DOMAIN, self.host)})
            if device:
                props = self.device_properties
                updates: dict[str, Any] = {}
                if props.get("name") and props["name"] != device.name:
                    updates["name"] = props["name"]
                if props.get("manufacturer") and props["manufacturer"] != device.manufacturer:
                    updates["manufacturer"] = props["manufacturer"]
                if props.get("model") and props["model"] != device.model:
                    updates["model"] = props["model"]
                if props.get("sw_version") and props["sw_version"] != device.sw_version:
                    updates["sw_version"] = props["sw_version"]
                if props.get("serialno") and props["serialno"] != device.serial_number:
                    updates["serial_number"] = props["serialno"]
                if props.get("mac"):
                    clean_mac = props["mac"].replace("-", ":").lower()
                    connections = set(device.connections)
                    connections.add((dr.CONNECTION_NETWORK_MAC, clean_mac))
                    updates["connections"] = connections

                if updates:
                    dev_reg.async_update_device(device.id, **updates)
        except Exception as err:
            _LOGGER.debug("Device registry update deferred for %s: %s", self.host, err)

    async def async_refresh_installed_apps(self) -> list[str]:
        """Fetch list of installed packages on the TV."""
        try:
            out = await self.client.shell(CMD_LIST_PACKAGES, timeout=6.0)
            packages = parse_packages(out)
            if not packages:
                out = await self.client.shell("pm list packages", timeout=7.0)
                packages = parse_packages(out)
            if packages:
                self.installed_apps = packages
                self._last_installed_apps_time = time.time()
                _LOGGER.info("Discovered %d installed apps on %s", len(packages), self.host)
        except Exception as err:
            _LOGGER.debug("Could not fetch installed packages: %s", err)
        return self.installed_apps

    async def async_discover_port(self, timeout: float = 2.5) -> int:
        """Discover the active TLS connect port via mDNS (_adb-tls-connect._tcp.local.)."""
        _LOGGER.debug("Attempting to auto-discover TLS connect port for %s", self.host)
        try:
            aiozc = await zeroconf.async_get_async_zeroconf(self.hass)
            if not aiozc or not getattr(aiozc, "zeroconf", None):
                return 0

            discovered_event = asyncio.Event()
            found_port: list[int] = []

            def on_service_change(*args: Any, **kwargs: Any) -> None:
                st = kwargs.get("service_type") or (args[1] if len(args) > 1 else "")
                nm = kwargs.get("name") or (args[2] if len(args) > 2 else "")
                if st and nm:
                    self.hass.loop.call_soon_threadsafe(
                        lambda s=st, n=nm: self.hass.async_create_task(
                            self._check_service(aiozc, s, n, found_port, discovered_event)
                        )
                    )

            browser = AsyncServiceBrowser(
                aiozc.zeroconf,
                [MDNS_CONNECT_TYPE],
                handlers=[on_service_change],
            )
            try:
                await asyncio.wait_for(discovered_event.wait(), timeout=timeout)
            except TimeoutError:
                pass
            finally:
                await browser.async_cancel()

            if found_port and found_port[0] > 0:
                _LOGGER.info("mDNS discovered active TLS connect port %s for %s", found_port[0], self.host)
                return found_port[0]
        except Exception as err:
            _LOGGER.debug("mDNS discovery failed for %s: %s", self.host, err)

        return 0

    async def _check_service(
        self,
        aiozc: Any,
        service_type: str,
        name: str,
        found_port: list[int],
        event: asyncio.Event,
    ) -> None:
        """Inspect discovered service info to match host IP."""
        try:
            info = await aiozc.async_get_service_info(service_type, name, timeout=2000)
            if info and info.parsed_addresses():
                for ip in info.parsed_addresses():
                    if ip == self.host and info.port:
                        found_port.append(info.port)
                        event.set()
                        return
        except Exception as err:
            _LOGGER.debug("Error checking service %s: %s", name, err)

    async def async_setup(self) -> None:
        """Set up dynamic mDNS listener to track changing TLS connect ports and load device info."""
        if self.client.port <= 0:
            discovered = await self.async_discover_port()
            if discovered > 0:
                self.client.update_port(discovered)
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, CONF_PORT: discovered},
                )

        try:
            if not self.client.is_connected:
                await self.client.connect(timeout=6.0)
            if self.client.is_connected:
                await self.async_fetch_device_properties()
                await self.async_refresh_installed_apps()
        except Exception as err:
            _LOGGER.debug("Initial setup device properties fetch deferred: %s", err)

        try:
            aiozc = await zeroconf.async_get_async_zeroconf(self.hass)
            if not aiozc or not getattr(aiozc, "zeroconf", None):
                return

            def service_updated(*args: Any, **kwargs: Any) -> None:
                st = kwargs.get("service_type") or (args[1] if len(args) > 1 else "")
                nm = kwargs.get("name") or (args[2] if len(args) > 2 else "")
                if st and nm:
                    self.hass.loop.call_soon_threadsafe(
                        lambda s=st, n=nm: self.hass.async_create_task(self._handle_zeroconf_update(aiozc, s, n))
                    )

            self._browser = AsyncServiceBrowser(
                aiozc.zeroconf,
                [MDNS_CONNECT_TYPE],
                handlers=[service_updated],
            )
            _LOGGER.debug("Dynamic mDNS tracker active for Android TV %s", self.host)
        except Exception as err:
            _LOGGER.debug("Could not attach zeroconf listener: %s", err)

    async def async_unload(self) -> None:
        """Cancel background browser and disconnect client."""
        if self._browser:
            try:
                await self._browser.async_cancel()
            except Exception:
                pass
            self._browser = None
        await self.client.disconnect()

    async def _handle_zeroconf_update(self, aiozc: Any, service_type: str, name: str) -> None:
        """Handle incoming Zeroconf record update."""
        try:
            info = await aiozc.async_get_service_info(service_type, name, timeout=2000)
            if info and info.parsed_addresses():
                for ip in info.parsed_addresses():
                    if ip == self.host and info.port:
                        if self.client.port != info.port:
                            _LOGGER.info("mDNS updated TLS connect port for %s to %s", self.host, info.port)
                            self.client.update_port(info.port)
                            self.hass.config_entries.async_update_entry(
                                self.entry,
                                data={**self.entry.data, CONF_PORT: info.port},
                            )
                            await self.client.disconnect()
                            await self.async_request_refresh()
                        break
        except Exception as err:
            _LOGGER.debug("Error processing zeroconf update: %s", err)

    async def _async_update_health(self) -> None:
        """Slow-tier telemetry and health poll."""
        enable_cec = self.entry.options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES)
        cmd = build_health_command(include_inputs=True)
        try:
            out = await self.client.shell(cmd, timeout=9.0)
            sections = split_sections(out)

            # Memory
            if mem_str := sections.get("MEM"):
                self.mem_info = parse_meminfo(mem_str)

            # Disk / Storage
            if disk_str := sections.get("DISK"):
                self.storage_info = parse_storage(disk_str)

            # CPU times delta
            if cpu_str := sections.get("CPU"):
                cur_cpu = parse_cpu_times(cpu_str)
                if cur_cpu:
                    self.cpu_load = cpu_percent(self._last_cpu_times, cur_cpu)
                    self._last_cpu_times = cur_cpu

            # Thermal
            hal_str = sections.get("THERMAL", "")
            zones_str = sections.get("ZONES", "")
            self.thermal_state = parse_thermal(hal_str, zones_str)

            # Power reasons & wake locks
            if pwr_str := sections.get("PWR"):
                self.power_reasons = parse_power_reasons(pwr_str)

            # Bluetooth
            bt_str = sections.get("BT", "")
            btin_str = sections.get("BTIN", "")
            self.bluetooth_info = parse_bluetooth(bt_str, btin_str)

            # Recents
            if rec_str := sections.get("RECENTS"):
                self.open_app_tasks = parse_recents(rec_str)
                self.running_apps = open_apps(self.open_app_tasks)

            # Settings
            if set_str := sections.get("SETTINGS"):
                self.settings = parse_kv(set_str)

            # TV Inputs
            if inp_str := sections.get("INPUTS"):
                self.inputs = parse_tv_inputs(inp_str, with_cec=enable_cec)

            self._last_health_time = time.time()
        except Exception as err:
            _LOGGER.debug("Health poll failed on %s: %s", self.host, err)

    async def _async_update_data(self) -> dict[str, Any]:
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

    async def async_send_key(self, keycode: int) -> None:
        """Send an input keyevent code to the TV."""
        await self.client.shell(f"input keyevent {keycode}", timeout=4.0)

    async def async_power_on(self) -> None:
        """Wake up the TV using KEY_WAKEUP and optional Wake-on-LAN."""
        if self.entry.options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL):
            mac = self.device_properties.get("mac") or self.entry.data.get(CONF_MAC)
            if mac:
                await async_send_magic_packet(mac)
        await self.async_send_key(KEY_WAKEUP)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_power_off(self) -> None:
        """Idempotently put the TV to sleep using KEY_SLEEP."""
        await self.async_send_key(KEY_SLEEP)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
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

    async def async_mute_volume(self, mute: bool) -> None:
        """Idempotently set volume mute state."""
        cmd = volume_adjust("mute" if mute else "unmute")
        await self.client.shell(cmd, timeout=4.0)
        await self.async_request_refresh()

    async def async_launch_app(self, package_or_name: str, url: str | None = None) -> None:
        """Launch an app package or deep link on the TV."""
        pkg = resolve_app(package_or_name, self.installed_apps) or package_or_name
        if url:
            cmd = view_uri(url, package=pkg)
            await self.client.shell(cmd, timeout=5.0)
        else:
            try:
                resolve_cmd = resolve_launch_activity(pkg)
                out = await self.client.shell(resolve_cmd, timeout=4.0)
                components = [line.strip() for line in out.splitlines() if "/" in line.strip()]
                if components:
                    launch_cmd = start_component(components[0])
                    res = await self.client.shell(launch_cmd, timeout=5.0)
                    if not am_start_failed(res):
                        await asyncio.sleep(0.8)
                        await self.async_request_refresh()
                        return
            except Exception:
                pass
            # Fallback to monkey
            await self.client.shell(monkey_launch(pkg), timeout=5.0)

        await asyncio.sleep(0.8)
        await self.async_request_refresh()

    async def async_stop_app(self, package_or_name: str) -> None:
        """Force-stop an app package and remove its recents stack."""
        pkg = resolve_app(package_or_name, self.installed_apps) or package_or_name
        # Find matching task in recents if present
        for task in self.open_app_tasks:
            if task.package == pkg:
                await self.client.shell(close_task(task.task_id), timeout=3.0)
        await self.client.shell(force_stop(pkg), timeout=4.0)
        await asyncio.sleep(0.5)
        await self.async_request_refresh()

    async def async_select_input(self, input_id_or_label: str) -> None:
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

    async def async_send_text(self, text: str, submit: bool = False) -> None:
        """Type text into focused TV text field and optionally hit enter."""
        cmd = input_text(text)
        await self.client.shell(cmd, timeout=5.0)
        if submit:
            await asyncio.sleep(0.1)
            await self.async_send_key(66)  # KEY_ENTER

    async def async_search(self, query: str, target: str = "global") -> None:
        """Search Android TV globally or on YouTube."""
        cmd = search(query, target)
        await self.client.shell(cmd, timeout=5.0)

    async def async_trim_caches(self) -> str:
        """Trim app caches to reclaim storage."""
        out = await self.client.shell(CMD_TRIM_CACHES, timeout=12.0)
        await self.async_request_refresh()
        return out.strip()

    async def async_start_screensaver(self) -> None:
        """Trigger daydream screensaver."""
        await self.client.shell(CMD_START_SCREENSAVER, timeout=5.0)

    async def async_set_setting(self, namespace: str, key: str, value: Any) -> None:
        """Update an Android global/secure/system setting."""
        cmd = settings_put(namespace, key, value)
        await self.client.shell(cmd, timeout=4.0)
        self.settings[key] = str(value)
        await self.async_request_refresh()

    async def async_run_command(self, command: str) -> str:
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

    async def async_reboot(self) -> None:
        """Reboot the Android TV."""
        _LOGGER.info("Sending reboot command to Android TV %s", self.host)
        await self.client.shell("reboot", timeout=5.0)

    async def async_screencap(self) -> bytes:
        """Take a PNG screen capture using exec: service to prevent CRLF corruption."""
        return await self.client.exec_raw("screencap -p", timeout=10.0)
