# Quest 3 Development Toolkit

A complete development toolkit for Oculus Quest 3, covering Termux environment setup, ADB customization, automation scripts, and a spatial computing productivity app.

## Prerequisites

- **Oculus Quest 3** with Developer Mode enabled
- **Termux** installed on Quest 3 (via sideloading)
- **macOS** (or Linux) with [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) installed
- **Node.js 18+** on your development machine (for the spatial app)

## Structure

| Directory | Description | Runs On |
|-----------|-------------|---------|
| `termux-setup/` | Automated dev environment setup for Termux | Quest 3 (Termux) |
| `adb-scripts/` | ADB-based device customization and management | macOS/Linux |
| `automation/` | Backup, monitoring, and helper scripts | Both |
| `spatial-app/` | WebXR spatial productivity app (React Three Fiber) | macOS (dev) / Quest 3 (browser) |

## Quick Start

### 1. Connect to Quest 3 via Wi-Fi ADB

```bash
# With Quest connected via USB first:
./adb-scripts/wifi-adb/connect-wifi-adb.sh
```

### 2. Set Up Termux Dev Environment

Copy the setup scripts to Quest 3 and run:

```bash
# From macOS, push scripts to Quest:
adb push termux-setup/ /sdcard/Download/termux-setup/

# In Termux on Quest 3:
cp -r /sdcard/Download/termux-setup/ ~/termux-setup/
cd ~/termux-setup
bash setup-all.sh
```

### 3. Optimize Quest 3 for Development

```bash
./adb-scripts/performance/optimize-all.sh
```

### 4. Run the Spatial Productivity App

```bash
cd spatial-app
npm install
npm run dev
# Open https://<your-mac-ip>:5173 in Quest 3 browser
```

## Safety

- Nothing here requires root access
- All ADB tweaks reset on reboot or can be reversed with `--reset` flags
- Disabled system apps can be re-enabled with `enable-system-apps.sh`
- The spatial app runs in the browser -- nothing is installed to the system
- Termux is fully sandboxed and can be uninstalled cleanly
