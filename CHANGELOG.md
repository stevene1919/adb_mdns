# 📋 Changelog

All notable changes and user-facing improvements to the **ADB mDNS** integration are documented in this file.

---

## [1.0.0] - 2026-11-09 — 🚀 Inaugural Release

Welcome to the initial release of **ADB mDNS** — the zero-binary, high-performance Home Assistant custom integration for modern Android TV, Google TV, and Android 11+ streaming devices!

### 🌟 Release Highlights

- 🔒 **Zero-Hassle Wireless Debugging (No USB or Root Required)**:
  - Connects directly to stock Android 11+ Developer Options using native TLS 1.3 encryption and on-screen SPAKE2 PIN pairing.
  - Requires zero command-line tools or external `adb` binaries installed on your Home Assistant host.

- 🔄 **Reboot-Proof Dynamic mDNS Port Tracking**:
  - Automatically rediscovers and updates rotating connect ports across TV reboots using local Zeroconf discovery (`_adb-tls-connect._tcp.local.`), completely eliminating connection drops.

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
