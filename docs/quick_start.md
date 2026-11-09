# 🔰 Quick Start & Pairing Guide

This guide walks you through pairing your Android TV, Google TV, or Android 11+ device with Home Assistant using **native Wireless Debugging** (TLS 1.3 with SPAKE2 authentication).

---

## 📋 Prerequisites

1. **Android 11 or Newer:**
   - Wireless Debugging with dynamic port negotiation was introduced in Android 11 (API level 30).
   - Supported on Chromecast with Google TV, NVIDIA Shield TV (Experience 9.0+), Sony Bravia (Google TV), Xiaomi TV Box / Stick, TCL / Hisense Android TVs, and Fire OS 8+ devices.
2. **Same Local Network:**
   - Ensure your Home Assistant host and the TV are on the same local subnet, or that mDNS (`_adb-tls-connect._tcp.local.`, `_adb-tls-pairing._tcp.local.`) and dynamic TCP ports (30000–50000) are routed between your IoT VLAN and Home Assistant.
3. **Integration Installed:**
   - Installed via HACS as a custom repository or placed in `config/custom_components/adb_mdns/`.

---

## 🛠️ Step-by-Step Pairing Process

### Step 1: Enable Developer Options on Your TV
1. On your TV, navigate to **Settings** ➔ **System** ➔ **About** (or **Device Preferences** ➔ **About**).
2. Scroll down to **Android TV OS build** (or **Build**).
3. Press the **OK / Select** button on your remote **7 times** until a toast notification appears saying:
   > *"You are now a developer!"*

---

### Step 2: Enable Wireless Debugging
1. Return to the previous menu and select **Developer options**.
2. Scroll down to the **Debugging** section.
3. Toggle **Wireless debugging** to **ON**.
4. *(Optional but recommended)* Check **Always allow on this network** if prompted.

---

### Step 3: Open the Pairing Dialog
1. Inside the **Wireless debugging** menu, click **Pair device with pairing code**.
2. A pop-up dialog will appear on your TV displaying:
   - **Wi-Fi pairing code** (a 6-digit numeric PIN, e.g., `123456`)
   - **IP address & Port** (e.g., `192.168.50.10:42181`)

> [!IMPORTANT]
> **Keep this pairing screen open on your TV while setting up Home Assistant!**
> The pairing port and PIN are temporary. If you exit or cancel this screen, Android invalidates the PIN, and a new port will be generated.

---

### Step 4: Add the Integration in Home Assistant
1. In Home Assistant, navigate to **Settings** ➔ **Devices & Services** ➔ **Add Integration**.
2. Search for **ADB mDNS - Android Debug Bridge** (or click the auto-discovered notification card if Zeroconf discovered your TV).
3. Enter the TV details:
   - **Host:** The TV's IP address (e.g., `192.168.50.10`).
   - **Pairing Port:** The port displayed on the pairing dialog (e.g., `42181`).
   - **PIN:** The 6-digit PIN displayed on your TV screen (e.g., `123456`).
4. Click **Submit**.

---

### Step 5: Pairing Verification & Auto-Discovery
1. Home Assistant will perform the cryptographic SPAKE2 key exchange over TLS 1.3, register its generated RSA client key with Android OS, and immediately discover the active connect port via mDNS (`_adb-tls-connect._tcp.local.`).
2. The pairing dialog on your TV will automatically dismiss, and Home Assistant will appear under **Paired devices** on the TV screen.
3. Assign your TV to an area in Home Assistant (e.g., *Living Room*) and click **Finish**.

---

## 🔄 Reconfiguration & Re-Pairing

If you ever toggle Wireless Debugging off and on or reset TV developer options:
1. Home Assistant will detect the invalid TLS certificate or missing auth key and create a repair issue.
2. Go to **Settings** ➔ **Devices & Services** ➔ **ADB mDNS**.
3. Click the menu next to the entry and select **Reconfigure** (or follow the Repair prompt).
4. Open the TV's **Pair device with pairing code** screen and submit the new temporary port and PIN.
