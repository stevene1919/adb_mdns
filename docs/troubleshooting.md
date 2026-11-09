# 🩺 Troubleshooting & FAQ

This guide provides diagnostic procedures and solutions for common network, pairing, and connection issues.

---

## 🔍 Common Issues & Solutions

### 1. "Failed to Connect" or "Pairing Timed Out"
- **Cause:** The pairing code and port displayed on Android TV are temporary.
- **Fix:** Keep the **Pair device with pairing code** dialog visible on your TV screen until Home Assistant finishes pairing. If the dialog disappears or is cancelled, Android invalidates the PIN immediately.

---

### 2. Connection Drops After TV Reboot
- **Cause:** Android 11+ changes the wireless debugging port upon reboot.
- **How ADB mDNS handles it:** The integration automatically monitors `_adb-tls-connect._tcp.local.` via Home Assistant Zeroconf and switches ports dynamically.
- **If mDNS is blocked across VLANs:** Ensure mDNS repeater/reflector (Avahi or your router's mDNS relay) forwards `_adb-tls-connect._tcp.local.` across your IoT VLAN and the Home Assistant subnet, and verify TCP ports `30000–50000` are permitted in firewall egress.

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
