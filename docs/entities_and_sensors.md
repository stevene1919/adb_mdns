# 📊 Platforms & Entity Reference

The **ADB mDNS** integration creates a rich set of Home Assistant entities exposing media controls, remote navigation, hardware telemetry, and system diagnostics.

---

## 📺 Media Player (`media_player.<device>`)

The primary platform representing your Android TV or Google TV:

- **Power State:** Accurately reflects device sleep/awake state parsed from `dumpsys power`.
- **Playback Control:** Play, Pause, Stop, Previous / Next Track, Seek, Volume Set/Step/Mute.
- **Progress Extrapolation:** Extrapolates current track playback position in real-time from Android OS MediaSession tokens (`cmd media_session`).
- **Dynamic App & Media Artwork:** Displays currently active media titles, artists, and dynamically loads high-resolution application icons.
- **Hardware HDMI Inputs:** Discovers connected HDMI ports and dynamically queries connected HDMI-CEC devices (e.g., `HDMI 1 · PlayStation 5`, `HDMI 2 · Apple TV`) with instant input switching via passthrough URIs.
- **Media Browser:** Interactive grid of all installed TV applications. Click any app tile to launch it directly.

---

## 📱 Remote (`remote.<device>_remote`)

Virtual remote control for automations and Lovelace dashboard remote cards:

- **Key Sending:** Supports standard keys (`HOME`, `BACK`, `DPAD_UP`, `DPAD_DOWN`, `DPAD_LEFT`, `DPAD_RIGHT`, `DPAD_CENTER`, `MENU`, `VOLUME_UP`, `VOLUME_DOWN`, `VOLUME_MUTE`, `POWER`, `SLEEP`, `WAKEUP`).
- **Custom Key Delays:** Configurable inter-key delays and repeat counts.
- **Turn On / Off:** Controls wake and sleep states via Android key events.

---

## 📈 Diagnostic & Status Sensors

| Entity ID | Friendly Name | Description |
| :--- | :--- | :--- |
| `sensor.<tv>_current_app` | Current App | Name of the active foreground application with dynamic app icon. |
| `sensor.<tv>_hdmi_input` | Current HDMI Input | Active HDMI input port, including CEC device name if available. |
| `sensor.<tv>_audio_output` | Audio Output | Current audio output destination (`HDMI ARC`, `Speaker`, `Bluetooth`). |
| `sensor.<tv>_session_status` | Session Status | Real-time health and transport status of the ADB TLS socket. |
| `sensor.<tv>_temperature` | SoC Temperature | Processor temperature in °C (queried via hardware thermal zones). |
| `sensor.<tv>_memory_usage` | RAM Usage | Percentage of device RAM currently utilized. |
| `sensor.<tv>_memory_available` | RAM Available | Free available memory in megabytes (parsed from `dumpsys meminfo`). |
| `sensor.<tv>_storage_available` | Storage Available | Free internal flash storage in gigabytes. |
| `sensor.<tv>_cpu_load` | CPU Load | Active CPU load percentage calculated from `/proc/stat`. |
| `sensor.<tv>_open_apps` | Open Apps Count | Number of active applications in the Android recent tasks stack. |
| `sensor.<tv>_bluetooth_devices` | Connected Bluetooth Devices | Count and list of connected remotes, gamepads, and audio gear. |
| `sensor.<tv>_last_wake_reason` | Last Wake Reason | OS reason for waking up (HDMI-CEC, remote power button, WoL). |
| `sensor.<tv>_last_sleep_reason` | Last Sleep Reason | OS reason for entering sleep/standby (timeout, remote sleep key). |

---

## 🚦 Binary Sensors

| Entity ID | Name | Description |
| :--- | :--- | :--- |
| `binary_sensor.<tv>_adb_connected` | ADB Connected | Indicates whether the TLS 1.3 socket is currently active and authenticated. |
| `binary_sensor.<tv>_in_use` | In Use | `on` when TV is awake and actively displaying content; `off` during deep sleep. |
| `binary_sensor.<tv>_keyboard_active` | Keyboard Active | Turns `on` immediately whenever an on-screen text input or search bar is focused. |

---

## 🔘 Buttons

| Entity ID | Name | Description |
| :--- | :--- | :--- |
| `button.<tv>_restart` | Restart TV | Safely reboots the Android operating system (`reboot`). |
| `button.<tv>_trim_caches` | Trim Caches | Calls `pm trim-caches 999G` to reclaim storage without affecting user data. |
| `button.<tv>_start_screensaver` | Start Screensaver | Immediately activates the Daydream screensaver (`am start -n ...`). |

---

## 🎛️ Switches

| Entity ID | Name | Description |
| :--- | :--- | :--- |
| `switch.<tv>_ui_animations` | Snappy UI Animations | Sets window and transition animation scales to `0.0x` for a lightning-fast interface. |
| `switch.<tv>_screensaver_enabled` | Screensaver Enabled | Toggles whether the ambient screensaver kicks in automatically when idle. |
| `switch.<tv>_hdmi_cec_auto_off` | HDMI-CEC Auto-Off | Toggles whether connected HDMI-CEC AVRs/soundbars turn off when TV sleeps. |
