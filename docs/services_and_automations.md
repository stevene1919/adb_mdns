# 🛠️ Services & Automations Guide

The **ADB mDNS** integration exposes dedicated Home Assistant actions (services) for scripts, automations, and custom dashboard cards.

Every action supports full Home Assistant targeting: `entity_id`, `device_id`, `area_id`, `floor_id`, and `label_id`. If multiple TVs exist, the integration protects against ambiguous calls when no target is passed.

---

## 📑 Service Index

| Service | Description | Example Payload |
| :--- | :--- | :--- |
| **`adb_mdns.adb_command`** | Execute an arbitrary ADB shell command on the device. | `command: "dumpsys power"` |
| **`adb_mdns.send_key`** | Send a named key or numeric Android keycode. | `key: "HOME"`, `num_repeats: 1` |
| **`adb_mdns.send_key_sequence`** | Execute a timed multi-step macro of keypresses. | `key_sequence: "HOME, RIGHT, SELECT"` |
| **`adb_mdns.launch_app`** | Launch an app by friendly name, package ID, or deep-link URL. | `app: "YouTube"`, `url: "..."` |
| **`adb_mdns.stop_app`** | Force stop an application and remove it from recents. | `app: "com.netflix.ninja"` |
| **`adb_mdns.send_text_input`** | Type text directly into an on-screen search or input box. | `text: "Interstellar 4K"`, `submit: true` |
| **`adb_mdns.search`** | Search globally across Android TV or directly inside YouTube. | `query: "SpaceX"`, `target: "youtube"` |
| **`adb_mdns.trim_caches`** | Reclaim storage by trimming app caches (`pm trim-caches`). | *(no fields required)* |
| **`adb_mdns.start_screensaver`** | Immediately trigger the Android Daydream screensaver. | *(no fields required)* |
| **`adb_mdns.pair_bluetooth`** | Open the Android TV Bluetooth accessory pairing screen. | *(no fields required)* |
| **`adb_mdns.connect_bluetooth`** | Connect a paired Bluetooth headphone or accessory by name or MAC. | `device: "Steven's Pixel Buds Pro 2"` |
| **`adb_mdns.disconnect_bluetooth`** | Disconnect a connected Bluetooth headphone or accessory. | `device: "Steven's Pixel Buds Pro 2"` |

---

## ⚙️ Detailed Service Reference

### 1. `adb_mdns.send_text_input`
Injects text directly into the focused input field using stock `input text` or broadcast intents. Ideal for typing passwords, search queries, or URLs without dealing with the slow on-screen D-pad keyboard.

```yaml
action: adb_mdns.send_text_input
target:
  entity_id: media_player.living_room_tv
data:
  text: "Oppenheimer"
  submit: true  # Automatically presses Enter after typing
```

---

### 2. `adb_mdns.search`
Initiates a global Google TV / Android TV voice/text search or opens the YouTube TV app directly to search results:

```yaml
action: adb_mdns.search
target:
  entity_id: media_player.living_room_tv
data:
  query: "4K HDR Nature Relax"
  target: youtube  # Options: 'global' or 'youtube'
```

---

### 3. `adb_mdns.send_key_sequence`
Sends a timed sequence of keys with configurable inter-key delays. Extremely useful for navigating complex menus or bypassing pop-up confirmations.

```yaml
action: adb_mdns.send_key_sequence
target:
  entity_id: media_player.living_room_tv
data:
  key_sequence: "HOME, DOWN, RIGHT, RIGHT, SELECT"
  delay_secs: 0.25
```

---

### 4. `adb_mdns.launch_app`
Launches any installed application. Supports built-in friendly aliases (`"YouTube"`, `"Netflix"`, `"Plex"`, `"Spotify"`, `"Kodi"`, etc.) or raw Android package IDs:

```yaml
# Launch by friendly name
action: adb_mdns.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "Plex"

# Launch video directly via deep-link intent
action: adb_mdns.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "YouTube"
  url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

### 5. `adb_mdns.stop_app`
Forcefully kills an application in the background (`am force-stop`) to free up memory or resolve frozen apps:

```yaml
action: adb_mdns.stop_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "com.netflix.ninja"
```

---

### 6. `adb_mdns.adb_command`
Executes raw shell commands on the Android OS. Runs safely over the TLS 1.3 socket:

```yaml
action: adb_mdns.adb_command
target:
  entity_id: media_player.living_room_tv
data:
  command: "dumpsys battery"
```

---

### 7. `adb_mdns.trim_caches`
Frees temporary internal storage across all installed apps by calling Android's package manager cache trimmer:

```yaml
action: adb_mdns.trim_caches
target:
  entity_id: media_player.living_room_tv
```

---

### 8. `adb_mdns.pair_bluetooth`, `adb_mdns.connect_bluetooth`, & `adb_mdns.disconnect_bluetooth`
Control Bluetooth headphones, speakers, and accessories on Android TV / Google TV:

```yaml
# Launch the "Searching for accessories..." Bluetooth pairing screen
action: adb_mdns.pair_bluetooth
target:
  entity_id: media_player.living_room_tv

# Connect paired Bluetooth headphones by friendly name or MAC address
action: adb_mdns.connect_bluetooth
target:
  entity_id: media_player.living_room_tv
data:
  device: "Steven's Pixel Buds Pro 2"

# Disconnect active Bluetooth headphones
action: adb_mdns.disconnect_bluetooth
target:
  entity_id: media_player.living_room_tv
data:
  device: "Steven's Pixel Buds Pro 2"
```

---

## 💡 Practical Automation Examples

### Automation 1: Auto-Focus Search when On-Screen Keyboard Opens
When an on-screen keyboard appears on the TV (e.g. YouTube search), send a push notification to your phone with a quick text input prompt:

```yaml
alias: "TV: Quick Phone Keyboard Input"
trigger:
  - platform: state
    entity_id: binary_sensor.bedroom_tv_keyboard_active
    to: "on"
action:
  - action: notify.mobile_app_phone
    data:
      title: "TV Search Active"
      message: "Type search query on TV:"
      data:
        actions:
          - action: "REPLY"
            title: "Type Text"
```

---

### Automation 2: Night Mode & Screensaver
Dim lights and trigger the Android screensaver at midnight if the TV is awake:

```yaml
alias: "Living Room: Night Screensaver"
trigger:
  - platform: time
    at: "23:30:00"
condition:
  - condition: state
    entity_id: binary_sensor.living_room_tv_in_use
    state: "on"
action:
  - action: adb_mdns.start_screensaver
    target:
      entity_id: media_player.living_room_tv
  - action: light.turn_off
    target:
      area_id: living_room
```

---

### Automation 3: Daily Storage Maintenance
Run cache trimming at 4 AM to prevent low storage warnings on streaming dongles:

```yaml
alias: "System: TV Cache Maintenance"
trigger:
  - platform: time
    at: "04:00:00"
action:
  - action: adb_mdns.trim_caches
    target:
      entity_id: media_player.living_room_tv
```
