# 🩺 Troubleshooting & FAQ

This guide provides diagnostic procedures and solutions for common network, pairing, and connection issues.

---

## 🔍 Common Issues & Solutions

### 1. "Failed to Connect" or "Pairing Timed Out"
- **Cause:** The pairing code and port displayed on Android TV are temporary.
- **Fix:** Keep the **Pair device with pairing code** dialog visible on your TV screen until Home Assistant finishes pairing. If the dialog disappears or is cancelled, Android invalidates the PIN immediately.

---

### 2. Connection Drops After TV Reboot
- **Cause:** Stock Android 11+ automatically disables the **Wireless debugging** toggle whenever the TV cold-reboots, and assigns a new random port when restarted.
- **How to reconnect:**
  1. Simply turn **Wireless debugging** back ON under **Developer options** on your TV.
  2. If you prefer automatic restoration on boot, you can use a lightweight Android utility (such as *ADB Auto Enable* or an automation app) to toggle Wireless Debugging on startup.
- **Automatic Port Tracking:** Once Wireless Debugging is active, ADB mDNS automatically detects the newly assigned connect port via `_adb-tls-connect._tcp.local.` without requiring any re-pairing or IP/port reconfiguration in Home Assistant.
- **If mDNS is blocked across VLANs:** Ensure your router's mDNS repeater (e.g., Avahi) forwards `_adb-tls-connect._tcp.local.` across subnets, and ensure TCP ports `30000–50000` are permitted in firewall rules.

---

### 3. TV Fails to Turn On via Integration
- **Cause:** In deep standby, Android devices shut down the Wi-Fi interface and wireless debugging daemon to conserve energy.
- **Fix:**
  1. In Home Assistant, open the integration **Options** and ensure **Enable Wake-on-LAN** is checked.
  2. In TV Settings: Go to **Settings** ➔ **Network & Internet** ➔ Enable **Network Standby** / **Remote Start** / **Wake on LAN**.
  3. For HDMI-CEC setups: Waking an AVR or another CEC device on the same HDMI chain can also trigger TV wake-up.

---

### 4. Re-Authenticating or Resetting Keys
If you ever revoked developer options authorization on the TV:
1. In Home Assistant: Navigate to **Settings** ➔ **Devices & Services** ➔ **ADB mDNS**.
2. Click the three dots on the entry and choose **Reconfigure**.
3. Re-open the **Pair device with pairing code** screen on the TV and provide the newly displayed port and PIN.
