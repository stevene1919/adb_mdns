# 📋 Project Roadmap & Future Enhancements

## 📱 Lightweight Android Wireless Debugging Auto-Enabler APK

### Background & Problem Statement
On stock Android 11+ (including Google TV and Android TV), the operating system disables the **Wireless Debugging** toggle (`adb_wifi_enabled`) whenever the device undergoes a cold reboot. While Home Assistant's `adb_mdns` integration automatically resolves changing mDNS ports dynamically once active, users currently have to either:
1. Manually open Developer Options on the TV after every cold reboot to toggle Wireless Debugging back on.
2. Rely on third-party automation tools or generic apps to re-enable it.

---

### 🎯 Objective
Develop an ultra-lightweight, open-source Android TV utility app (e.g. `adb-wifi-keepalive` or `adb-mdns-enabler`) specifically designed to run on Android 11+ TV devices and ensure Wireless Debugging is enabled at boot.

---

### 🏗️ Technical Architecture & Requirements

#### 1. Permissions & API Feasibility
- **Target Setting:** `Settings.Global.ADB_WIFI_ENABLED` (`1` = ON, `0` = OFF).
- **Required Permission:** `android.permission.WRITE_SECURE_SETTINGS`.
- **One-Time Provisioning:**
  Because third-party apps cannot request `WRITE_SECURE_SETTINGS` via standard runtime prompts, the initial setup can be granted via ADB during integration setup:
  ```bash
  adb shell pm grant <package_name> android.permission.WRITE_SECURE_SETTINGS
  ```
- **Alternative Approach (Shizuku / Sudo API):**
  - Integrate with Shizuku or local ADB loopback if available to trigger the setting without manual terminal permissions.

#### 2. Key Components
- **`BootReceiver` (`BroadcastReceiver`):**
  - Listens for `Intent.ACTION_BOOT_COMPLETED` and `Intent.ACTION_LOCKED_BOOT_COMPLETED`.
  - Checks if `Settings.Global.getInt(resolver, "adb_wifi_enabled", 0) == 0`.
  - If `0`, sets `Settings.Global.putInt(resolver, "adb_wifi_enabled", 1)`.
- **Leanback UI Activity:**
  - Simple 1-screen Android TV Leanback dashboard showing current Wireless Debugging status, current dynamic connect port, and permission check status (`WRITE_SECURE_SETTINGS` granted/missing).
  - One-click button to test toggle and view instructions for granting permissions.
- **Watchdog / Network State Receiver:**
  - Listens for network changes (`ConnectivityManager.CONNECTIVITY_ACTION` or `NetworkCallback`) to re-assert Wireless Debugging if Wi-Fi reconnects after router reboot.

#### 3. Constraints & Principles
- **Zero Heavy Dependencies:** Native Kotlin without heavy frameworks to keep the APK footprint under 1 MB.
- **Zero Telemetry / Zero Cloud:** 100% offline and privacy-first.
- **Battery & Resource Friendly:** Passive broadcast receiver only; no persistent foreground services or CPU-draining polling loops.
