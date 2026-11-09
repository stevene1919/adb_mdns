"""Constants for the ADB mDNS - Android Debug Bridge integration."""

from __future__ import annotations

DOMAIN = "adb_mdns"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PAIRING_PORT = "pairing_port"
CONF_PRIVATE_KEY = "private_key"
CONF_PIN = "pin"
CONF_NAME = "name"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"
CONF_SERIALNO = "serialno"
CONF_MAC = "mac"
CONF_APPS = "apps"

# Options Flow Configuration Keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_HEALTH_INTERVAL = "health_interval"
CONF_SCREENCAP_INTERVAL = "screencap_interval"
CONF_ENABLE_WOL = "enable_wol"
CONF_ENABLE_CEC_NAMES = "enable_cec_names"
CONF_EXCLUDE_UNNAMED_APPS = "exclude_unnamed_apps"
CONF_INCLUDE_APPS_IN_SOURCES = "include_apps_in_sources"
CONF_INCLUDE_LAUNCHER_IN_SOURCES = "include_launcher_in_sources"
CONF_KEY_DELAY = "key_delay"
CONF_KEY_REPEAT = "key_repeat"
CONF_VOLUME_STEP_FALLBACK = "volume_step_fallback"
CONF_TURN_ON_COMMAND = "turn_on_command"
CONF_TURN_OFF_COMMAND = "turn_off_command"

# mDNS Service Types
MDNS_CONNECT_TYPE = "_adb-tls-connect._tcp.local."
MDNS_PAIRING_TYPE = "_adb-tls-pairing._tcp.local."

# Defaults
DEFAULT_NAME = "Android TV"
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_HEALTH_INTERVAL = 60
DEFAULT_SCREENCAP_INTERVAL = 30
DEFAULT_ENABLE_WOL = True
DEFAULT_ENABLE_CEC_NAMES = True
DEFAULT_EXCLUDE_UNNAMED_APPS = True
DEFAULT_INCLUDE_APPS_IN_SOURCES = True
DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES = False
DEFAULT_KEY_DELAY = 0.2
DEFAULT_KEY_REPEAT = 1
DEFAULT_VOLUME_STEP_FALLBACK = True

# Service Names
SERVICE_ADB_COMMAND = "adb_command"
SERVICE_SEND_KEY = "send_key"
SERVICE_SEND_KEY_SEQUENCE = "send_key_sequence"
SERVICE_LAUNCH_APP = "launch_app"
SERVICE_STOP_APP = "stop_app"
SERVICE_SEND_TEXT_INPUT = "send_text_input"
SERVICE_SEARCH = "search"
SERVICE_TRIM_CACHES = "trim_caches"
SERVICE_START_SCREENSAVER = "start_screensaver"

# Service Attributes
ATTR_COMMAND = "command"
ATTR_ENTITY_ID = "entity_id"
ATTR_KEY = "key"
ATTR_KEY_SEQUENCE = "key_sequence"
ATTR_DELAY_SECS = "delay_secs"
ATTR_NUM_REPEATS = "num_repeats"
ATTR_APP = "app"
ATTR_APP_ID = "app_id"
ATTR_URL = "url"
ATTR_TEXT = "text"
ATTR_SUBMIT = "submit"
ATTR_QUERY = "query"
ATTR_TARGET = "target"

# Re-export keycodes and apps from tv package for backwards compatibility
from .tv.apps import APPS
from .tv.keys import (
    KEY_BACK,
    KEY_DPAD_CENTER,
    KEY_DPAD_DOWN,
    KEY_DPAD_LEFT,
    KEY_DPAD_RIGHT,
    KEY_DPAD_UP,
    KEY_ENTER,
    KEY_HOME,
    KEY_MEDIA_FAST_FORWARD,
    KEY_MEDIA_NEXT,
    KEY_MEDIA_PLAY_PAUSE,
    KEY_MEDIA_PREVIOUS,
    KEY_MEDIA_REWIND,
    KEY_MEDIA_STOP,
    KEY_MENU,
    KEY_NAMES,
    KEY_PAUSE,
    KEY_PLAY,
    KEY_POWER,
    KEY_SLEEP,
    KEY_TV,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_MUTE,
    KEY_VOLUME_UP,
    KEY_WAKEUP,
)

__all__ = [
    "APPS",
    "ATTR_APP",
    "ATTR_APP_ID",
    "ATTR_COMMAND",
    "ATTR_DELAY_SECS",
    "ATTR_ENTITY_ID",
    "ATTR_KEY",
    "ATTR_KEY_SEQUENCE",
    "ATTR_NUM_REPEATS",
    "ATTR_QUERY",
    "ATTR_SUBMIT",
    "ATTR_TARGET",
    "ATTR_TEXT",
    "ATTR_URL",
    "CONF_APPS",
    "CONF_ENABLE_CEC_NAMES",
    "CONF_ENABLE_WOL",
    "CONF_EXCLUDE_UNNAMED_APPS",
    "CONF_INCLUDE_APPS_IN_SOURCES",
    "CONF_HEALTH_INTERVAL",
    "CONF_HOST",
    "CONF_INCLUDE_LAUNCHER_IN_SOURCES",
    "CONF_KEY_DELAY",
    "CONF_KEY_REPEAT",
    "CONF_MAC",
    "CONF_MANUFACTURER",
    "CONF_MODEL",
    "CONF_NAME",
    "CONF_PAIRING_PORT",
    "CONF_PIN",
    "CONF_PORT",
    "CONF_PRIVATE_KEY",
    "CONF_SCAN_INTERVAL",
    "CONF_SCREENCAP_INTERVAL",
    "CONF_SERIALNO",
    "CONF_SW_VERSION",
    "CONF_TURN_OFF_COMMAND",
    "CONF_TURN_ON_COMMAND",
    "CONF_VOLUME_STEP_FALLBACK",
    "DEFAULT_ENABLE_CEC_NAMES",
    "DEFAULT_ENABLE_WOL",
    "DEFAULT_EXCLUDE_UNNAMED_APPS",
    "DEFAULT_HEALTH_INTERVAL",
    "DEFAULT_INCLUDE_APPS_IN_SOURCES",
    "DEFAULT_INCLUDE_LAUNCHER_IN_SOURCES",
    "DEFAULT_KEY_DELAY",
    "DEFAULT_KEY_REPEAT",
    "DEFAULT_NAME",
    "DEFAULT_SCAN_INTERVAL",
    "DEFAULT_SCREENCAP_INTERVAL",
    "DEFAULT_VOLUME_STEP_FALLBACK",
    "DOMAIN",
    "KEY_BACK",
    "KEY_DPAD_CENTER",
    "KEY_DPAD_DOWN",
    "KEY_DPAD_LEFT",
    "KEY_DPAD_RIGHT",
    "KEY_DPAD_UP",
    "KEY_ENTER",
    "KEY_HOME",
    "KEY_MEDIA_FAST_FORWARD",
    "KEY_MEDIA_NEXT",
    "KEY_MEDIA_PLAY_PAUSE",
    "KEY_MEDIA_PREVIOUS",
    "KEY_MEDIA_REWIND",
    "KEY_MEDIA_STOP",
    "KEY_MENU",
    "KEY_NAMES",
    "KEY_PAUSE",
    "KEY_PLAY",
    "KEY_POWER",
    "KEY_SLEEP",
    "KEY_TV",
    "KEY_VOLUME_DOWN",
    "KEY_VOLUME_MUTE",
    "KEY_VOLUME_UP",
    "KEY_WAKEUP",
    "MDNS_CONNECT_TYPE",
    "MDNS_PAIRING_TYPE",
    "SERVICE_ADB_COMMAND",
    "SERVICE_LAUNCH_APP",
    "SERVICE_SEARCH",
    "SERVICE_SEND_KEY",
    "SERVICE_SEND_KEY_SEQUENCE",
    "SERVICE_SEND_TEXT_INPUT",
    "SERVICE_START_SCREENSAVER",
    "SERVICE_STOP_APP",
    "SERVICE_TRIM_CACHES",
]

# Backward compatibility aliases for old coordinator/media_player imports during migration
