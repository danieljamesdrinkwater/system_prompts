# Quest 3 Automation Scripts

Helper scripts for Quest 3 monitoring, backup/restore, and common tasks.

**Execution environments:**
- Scripts that run from macOS via ADB use `#!/usr/bin/env bash`
- Scripts that run inside Termux on Quest use `#!/data/data/com.termux/files/usr/bin/bash`

## Monitoring (run from macOS via ADB)

### battery-monitor.sh
Parse battery level, temperature, charging status, health, and voltage.

```bash
# Single-shot battery report
./monitoring/battery-monitor.sh

# Live monitoring every 5 seconds
./monitoring/battery-monitor.sh --watch 5
```

### storage-monitor.sh
Show storage usage for /data (apps/games), /sdcard (shared storage), and other partitions.

```bash
# Key partition summary
./monitoring/storage-monitor.sh

# All mounted partitions
./monitoring/storage-monitor.sh --all
```

### process-monitor.sh
Show top processes by CPU or memory usage with optional filtering.

```bash
# Top 10 by CPU
./monitoring/process-monitor.sh

# Top 20 by memory, filtered
./monitoring/process-monitor.sh --top 20 --sort mem --filter oculus

# Watch mode
./monitoring/process-monitor.sh --watch 3
```

### system-info.sh
Aggregate device snapshot: model, Android version, firmware, battery, storage, network, uptime.

```bash
# Formatted report
./monitoring/system-info.sh

# JSON output for scripting
./monitoring/system-info.sh --json
```

## Backup and Restore

### backup-app-data.sh (from macOS via ADB)
Back up app data for a single package or all sideloaded apps.

```bash
# Backup a single app
./backup-restore/backup-app-data.sh --package com.example.myapp

# Backup all sideloaded apps
./backup-restore/backup-app-data.sh --all-sideloaded

# Custom output directory
./backup-restore/backup-app-data.sh --all-sideloaded --output ~/my-backups
```

### restore-app-data.sh (from macOS via ADB)
Restore from a backup created by backup-app-data.sh.

```bash
# Restore all apps from a backup
./backup-restore/restore-app-data.sh ./quest3-backups/20250115_143022/

# Restore a specific package
./backup-restore/restore-app-data.sh ./quest3-backups/20250115_143022/ --package com.example.app

# Dry run to preview
./backup-restore/restore-app-data.sh ./quest3-backups/20250115_143022/ --dry-run
```

### backup-termux.sh (runs inside Termux on Quest)
Back up the Termux home directory and installed package list.

```bash
# Standard backup
./backup-restore/backup-termux.sh

# Exclude patterns
./backup-restore/backup-termux.sh --exclude "*.cache" --exclude "node_modules"

# Dry run
./backup-restore/backup-termux.sh --dry-run
```

### restore-termux.sh (runs inside Termux on Quest)
Restore a backup created by backup-termux.sh.

```bash
# Full restore
./backup-restore/restore-termux.sh ~/storage/shared/termux-backups/20250115_143022/

# Restore only files (skip package reinstallation)
./backup-restore/restore-termux.sh ~/storage/shared/termux-backups/20250115_143022/ --skip-packages
```

## Helpers

### wifi-adb-auto.sh (runs inside Termux on Quest)
Designed for Termux:Boot. On boot, enables ADB TCP mode and logs the device IP.

```bash
# Setup for auto-start
mkdir -p ~/.termux/boot
cp helpers/wifi-adb-auto.sh ~/.termux/boot/
chmod +x ~/.termux/boot/wifi-adb-auto.sh

# Manual run
./helpers/wifi-adb-auto.sh --port 5555
```

### app-launcher.sh (from macOS via ADB)
Launch apps by package name with built-in shortcuts.

```bash
# Launch by package name
./helpers/app-launcher.sh com.example.myapp

# Use shortcuts
./helpers/app-launcher.sh --browser
./helpers/app-launcher.sh --settings
./helpers/app-launcher.sh --termux

# List all shortcuts
./helpers/app-launcher.sh --shortcuts

# List activities for a package
./helpers/app-launcher.sh --list com.termux

# Launch a specific activity
./helpers/app-launcher.sh com.example.app --activity .MainActivity
```

### screenshot.sh (from macOS via ADB)
Capture a screenshot, pull it locally with a timestamped filename, and open it.

```bash
# Capture and auto-open
./helpers/screenshot.sh

# Save to specific directory
./helpers/screenshot.sh -o ~/Screenshots

# Capture without opening
./helpers/screenshot.sh --no-open
```
