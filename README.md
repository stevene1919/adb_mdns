# 📺 ADB mDNS - Android Debug Bridge

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/adb_mdns)](https://github.com/stevene1919/adb_mdns/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=adb_mdns&category=integration)

A modern, high-performance Home Assistant custom integration for Android TV, Google TV, and Android 11+ devices communicating directly over **native Wireless Debugging** (TLS 1.3 with SPAKE2 PIN pairing) and dynamic **mDNS port tracking**.

---

## 🎯 Why ADB mDNS? (Bridging the Home Assistant Android Gap)

Home Assistant users with Android TV and Google TV devices previously faced an awkward dilemma between two core integrations:

| Feature / Capability | Legacy Built-in `androidtv` | Built-in `androidtv_remote` | ⚡ **ADB mDNS** (This Integration) |
| :--- | :---: | :---: | :---: |
| **Connection Transport** | Plaintext TCP Port `5555` | TLS / Protocol Buffers | **Mutual TLS 1.3 over mDNS** |
| **Android 11+ Reboot Survival** | ❌ Drops permanently (port rotates) | ✅ Survives | ✅ **Dynamic mDNS tracking** (`_adb-tls-connect`) |
| **Setup Complexity** | High (USB tether / `adb tcpip 5555`) | Low (PIN pairing) | **Low (On-Screen PIN pairing)** |
| **Directional Remote Keys** | ✅ Yes | ✅ Yes | ✅ **Yes (Fast key repeats & delays)** |
| **True ADB Shell Access** | ✅ Yes | ❌ None | ✅ **Pure OS shell (`dumpsys`, `am`, `pm`)** |
| **Hardware HDMI-CEC Discovery** | ❌ Basic | ❌ None | ✅ **Dynamic CEC naming via `dumpsys`** |
| **On-Screen Keyboard Detection** | ❌ None | ❌ None | ✅ **Real-time `binary_sensor` active state** |
| **System Diagnostics** | ❌ None | ❌ None | ✅ **SoC Temp, RAM, Storage, CPU Load** |
| **Background App Control** | ❌ Limited | ❌ None | ✅ **Force-stop apps & trim cache button** |
| **Zero On-Device Binaries** | ⚠️ Installs helper | ✅ Pure | ✅ **Zero APKs / zero jar files pushed** |

---

## 🔰 Quick Start (Beginners Guide)

Setting up your Android TV takes less than 3 minutes across 3 simple steps:

### 1️⃣ Install via HACS
Click the one-click button below to open this repository directly inside HACS:

[![Open HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=adb_mdns&category=integration)

*(If adding manually: open **HACS** ➔ **Integrations** ➔ top-right menu ➔ **Custom repositories** ➔ URL: `https://github.com/stevene1919/adb_mdns` ➔ Type: **Integration**).*

### 2️⃣ Enable Wireless Debugging on TV
1. On your TV, navigate to **Settings** ➔ **System** ➔ **About** (or **Device Preferences** ➔ **About**).
2. Click **Android TV OS build** **7 times** until you see *"You are now a developer!"*.
3. Go back to **Developer options** and toggle **Wireless debugging** to **ON**.
4. Select **Pair device with pairing code** (keep this dialog open on your TV screen).

### 3️⃣ Pair in Home Assistant
1. In Home Assistant, go to **Settings** ➔ **Devices & Services** ➔ **Add Integration**.
2. Search for and select **ADB mDNS - Android Debug Bridge**.
3. Enter your TV's IP address. Home Assistant will automatically detect the active mDNS ports for you.
4. Enter the 6-digit PIN shown on your TV screen (and verify the pre-filled pairing port) to complete pairing!

> [!TIP]
> **Need detailed step-by-step instructions?**  
> Consult the dedicated **[Quick Start & Pairing Guide](docs/quick_start.md)**.

---

## 📺 Supported Devices

Compatible with any device running **Android 11 (API 30) or higher** with Wireless Debugging:

- 📺 **Google Chromecast** (Chromecast with Google TV 4K & HD)
- 📺 **NVIDIA Shield TV & Shield TV Pro** (Software Experience 9.0+)
- 📺 **Sony Bravia** (Google TV models)
- 📺 **TCL & Hisense Android TV / Google TV models**
- 📺 **Xiaomi Mi Box & Mi TV Stick**
- 📺 **Amazon Fire TV** (Fire OS 8+ running Android 11 base)
- 📺 **Walmart onn. Google TV Streaming Box**
- 📱 **Android 11+ Tablets, Projectors, and Smart Displays**

---

## ✨ Features

- 🔒 **Native TLS 1.3 Wireless Debugging:** Directly authenticates with stock Android developer options. Zero legacy port 5555 vulnerabilities.
- ⚡ **Dynamic mDNS Port Tracking:** Automatically tracks changing connect ports via `_adb-tls-connect._tcp.local.` whenever the device reboots.
- 📺 **Rich Media Player & Media Browser:** Play, Pause, Stop, Seek, Volume, App Launcher dropdown, and interactive Browsable App Tiles.
- 🎮 **Hardware HDMI Inputs & CEC Discovery:** Dynamically names inputs based on connected HDMI-CEC devices (`HDMI 1 · PlayStation 5`) with direct passthrough URI switching.
- ⌨️ **Real-Time On-Screen Keyboard Detection:** Detects when a search bar or text field is focused on the TV screen (`binary_sensor.*_keyboard_active`).
- 🧹 **System Management & Storage Reclaim:** Buttons to trim app caches (`pm trim-caches 999G`), immediately start screensaver, and restart the TV.
- ⚙️ **Snappy UI Switch:** Switch entity to disable window/transition animations for a snappy interface.
- 📊 **Diagnostic Telemetry:** Sensors for SoC temperature, RAM usage/free, internal storage, CPU load, and connected Bluetooth controllers.
- 🎯 **Target-Resolved Automation Services:** Full entity, device, area, floor, and label targeting with multi-TV ambiguity protection.

---

## 📚 Complete Documentation Library

For deep technical details, configuration parameters, and automation blueprints, refer to the dedicated documentation library:

| Guide | Description |
| :--- | :--- |
| 🔰 **[Quick Start & Pairing Guide](docs/quick_start.md)** | Step-by-step setup guide for enabling developer options and pairing. |
| 🛠️ **[Services & Automations Guide](docs/services_and_automations.md)** | Complete reference and YAML recipes for `send_text_input`, `search`, and macros. |
| 📊 **[Platforms & Entity Reference](docs/entities_and_sensors.md)** | Full list and descriptions of all media player, remote, sensor, button, and switch entities. |
| 🔬 **[Protocol & Cryptographic Architecture](docs/protocol_architecture.md)** | Technical breakdown of TLS 1.3, SPAKE2 derivation, Zeroconf discovery, and wire framing. |
| 🩺 **[Troubleshooting & FAQ](docs/troubleshooting.md)** | Resolving Wi-Fi standby sleep, pairing timeouts, and VLAN routing rules. |

---

## 🔧 Automation Services Preview

All services accept standard Home Assistant target selectors (`entity_id`, `device_id`, `area_id`):

```yaml
# 1. Type text directly into focused TV search field
action: adb_mdns.send_text_input
target:
  entity_id: media_player.living_room_tv
data:
  text: "Interstellar 4K"
  submit: true

# 2. Search YouTube TV directly
action: adb_mdns.search
target:
  entity_id: media_player.living_room_tv
data:
  query: "SpaceX Starship launch"
  target: youtube

# 3. Send key sequence macro with custom delay
action: adb_mdns.send_key_sequence
target:
  entity_id: media_player.living_room_tv
data:
  key_sequence: "HOME, DOWN, RIGHT, SELECT"
  delay_secs: 0.2
```

> See the **[Services & Automations Guide](docs/services_and_automations.md)** for full YAML examples.

---

## ☕ Support the Project

If this integration makes your smart home better or saved you hours of troubleshooting, consider supporting continued maintenance and development:

<p align="center">
  <a href="https://ko-fi.com/stevene_" target="_blank">
    <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="44" style="border:0px;height:44px;" alt="Buy Me A Coffee at ko-fi.com" />
  </a>
</p>

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
