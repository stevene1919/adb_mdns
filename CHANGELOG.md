# 📋 Changelog

All notable changes and user-facing improvements to the **ADB mDNS** integration are documented in this file.

---

## [1.0.1] - 2026-11-17 — 🎧 Bluetooth Sound Mode, Android 14 Playback & Standards Alignment

This release brings Bluetooth headphone/speaker integration, comprehensive fixes for Android 14 Google TV playback state and volume parsing, and Home Assistant 2026 standards compliance.

### 🌟 What's New & Fixed

- 🎧 **Bluetooth Audio & Headphone Sound Mode**:
  - **Media Player Sound Mode Selector (`sound_mode` / `sound_mode_list`)**: Paired Bluetooth headphones, earphones, and speakers are dynamically discovered and listed in the Sound Mode dropdown alongside primary TV/HDMI output.
  - **Instant Connection & Disconnection**: Selecting a Bluetooth device connects it directly via Google TV's native Slice provider; selecting TV/HDMI output automatically disconnects active Bluetooth headphones.
  - **One-Click Bluetooth Pairing**: Added `button.<device>_pair_bluetooth_accessory` and `adb_mdns.pair_bluetooth` service to jump directly to Android TV's native *"Searching for accessories..."* screen.
  - **Automation Actions**: New `adb_mdns.connect_bluetooth` and `adb_mdns.disconnect_bluetooth` services supporting friendly names or MAC addresses.
  - **Bluetooth Classification & Diagnostics**: Bonded Bluetooth devices are classified into `"audio"` vs `"input"` devices, and `sensor.<device>_bluetooth_devices` now reports active connected counts and audio device lists.

- 🐛 **Android 14 Google TV Fixes**:
  - **Playback State Stuck on Idle (#1)**: Fixed Android 14 `dumpsys media_session` regex where enum values formatted as `state=PLAYING(3)` or `state=PAUSED(2)` caused playback states to fail parsing and default to `idle` while metadata was active.
  - **Volume Level Scaling**: Fixed `STREAM_MUSIC` volume parsing on Android 14 where `Devices: hdmi(400)` failed against parenthesized bitmask entries and caused volume to incorrectly report `1.0` (100%).
  - **Wi-Fi MAC Discovery**: Added `dumpsys wifi` fallback parsing when `ip -o link show` is restricted by Android 14 SELinux policy.
  - **Negative Action Masks**: Supported negative signed action bitmasks (e.g. `actions=-1` on Kodi).

- 🏛️ **Home Assistant Standards Alignment**:
  - `media_position_updated_at` now strictly returns a UTC `datetime` object (`dt_util.utcnow()`) instead of a timestamp float.
  - `media_position` strictly returns an integer in seconds.
  - Exposed native `app_name` property and removed redundant `app_id` attribute from `extra_state_attributes`.
  - Upgraded Device Registry queries to prevent Home Assistant 2026.10 deprecation warnings (`dr.async_entries_for_config_entry`).
  - Cleared `media_image_hash` when the media player is `OFF`.

- 📖 **Documentation & Roadmap**:
  - Clarified reboot behavior in documentation: explains why stock Android resets the Wireless Debugging toggle on cold reboot and how dynamic port tracking reconnects once active.
  - Added architectural plan and roadmap for a companion auto-enabler APK ([`plans/adb_mdns_android_app.md`](https://github.com/stevene1919/adb_mdns/blob/main/TODO.md)).

---

## [1.0.0] - 2026-11-09 — 🚀 Inaugural Release

Welcome to the initial release of **ADB mDNS** — the zero-binary, high-performance Home Assistant custom integration for modern Android TV, Google TV, and Android 11+ streaming devices!

### 🌟 Release Highlights

- 🔒 **Zero-Hassle Wireless Debugging (No USB or Root Required)**:
  - Connects directly to stock Android 11+ Developer Options using native TLS 1.3 encryption and on-screen SPAKE2 PIN pairing.
  - Requires zero command-line tools or external `adb` binaries installed on your Home Assistant host.

- 🔄 **Dynamic mDNS Port Tracking**:
  - Automatically rediscovers and updates rotating connect ports using local Zeroconf discovery (`_adb-tls-connect._tcp.local.`), seamlessly reconnecting whenever Wireless Debugging is enabled without requiring static port setups.

- 🎨 **Rich Media Browser with High-Res App Artwork**:
  - Open Home Assistant's Media Browser to visually browse your installed Android TV apps with official high-resolution brand logos (Netflix, YouTube, Prime Video, Disney+, Plex, Kodi, Spotify, Stan, ABC iview, Twitch, Apple TV+, and more).
  - Launch any streaming app with a single click or through automation actions.

- 🔢 **Numeric Channel Tuning**:
  - Use `media_player.play_media` with `media_type: channel` and numeric channel numbers (e.g. `"102"`) to automatically sequence digit keypresses to your TV or live tuner.

- 🎛️ **Focused 3-Step Options Flow**:
  - Configure your TV easily through dedicated, organized settings menus:
    - **Sources & App Visibility**: Customize app dropdowns and hide unnamed system services.
    - **Polling & Screen Capture**: Tune background refresh intervals and optional screen grab frequency.
    - **Controls & Remote Power**: Adjust keypress repeat delays and configure custom vendor wake/sleep commands.

- ⚡ **Enhanced Reliability & Concurrency Guarding**:
  - Internal packet queuing and per-entity execution guards (`PARALLEL_UPDATES = 1`) prevent socket collisions and ensure smooth, reliable communication even during rapid automation sequences.

- 📺 **Hardware HDMI-CEC Discovery & Keyboard Detection**:
  - Automatically identifies and displays friendly names for connected HDMI-CEC devices (such as game consoles, soundbars, or Blu-ray players).
  - Real-time `binary_sensor.*_keyboard_active` sensor alerts Home Assistant whenever an on-screen text field or search bar is focused on your TV.

- 🧹 **System Care & Performance Tools**:
  - One-click buttons to reclaim storage by trimming temporary app caches (`pm trim-caches 999G`), immediately start your screensaver, or reboot the device.
  - Snappy UI animation switch entity to disable sluggish system animations for a lightning-fast TV experience.
