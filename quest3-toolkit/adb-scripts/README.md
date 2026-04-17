# Quest 3 ADB Scripts

Command-line utilities for managing an Oculus Quest 3 over ADB. All scripts
target macOS and Linux with `bash` and require
[Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)
(`adb`) on your PATH.

---

## Sections

### wifi-adb/ — Wireless ADB connection management

| Script | Purpose |
|--------|---------|
| `connect-wifi-adb.sh` | One-shot setup of a Wi-Fi ADB session (USB required to start) |
| `auto-reconnect.sh` | Long-running monitor that detects drops and reconnects automatically |

```bash
# Initial wireless setup (Quest 3 plugged in via USB)
./wifi-adb/connect-wifi-adb.sh

# Keep the connection alive, checking every 20 seconds
./wifi-adb/auto-reconnect.sh --ip 192.168.1.42 --interval 20

# Auto-detect IP and use defaults (30 s interval, 10 retries)
./wifi-adb/auto-reconnect.sh
```

### performance/ — Performance profiling and tuning

Scripts for capturing GPU/CPU metrics, adjusting clock speeds, and toggling
Quest 3 performance profiles.

```bash
# Example (placeholder)
./performance/set-gpu-level.sh --level 4
./performance/capture-fps.sh --duration 60 --output fps.csv
```

### system/ — Device system utilities

Helpers for device info, storage management, screenshot/recording capture, and
Guardian/boundary configuration.

```bash
# Example (placeholder)
./system/device-info.sh
./system/capture-screenshot.sh --output screenshot.png
```

### sideload/ — APK sideloading

Install, update, and manage sideloaded applications on the Quest 3.

```bash
# Example (placeholder)
./sideload/install-apk.sh ~/Downloads/my-app.apk
./sideload/list-sideloaded.sh
```

---

## Prerequisites

1. **ADB** installed and on your PATH (`adb version` to verify).
2. **Developer mode** enabled on the Quest 3 (Settings > System > Developer).
3. **USB debugging** enabled and the host computer authorized on the headset.

## Quick start

```bash
# Clone / copy the scripts, then make them executable
chmod +x wifi-adb/*.sh

# Connect wirelessly
./wifi-adb/connect-wifi-adb.sh
```
