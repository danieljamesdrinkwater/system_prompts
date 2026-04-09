# Automation Scripts

Helper scripts for Quest 3 monitoring, backup/restore, and common tasks.

## Monitoring (run from macOS via ADB)

```bash
# Battery status with live updates
./monitoring/battery-monitor.sh --watch

# Storage overview
./monitoring/storage-monitor.sh

# Top processes by CPU usage
./monitoring/process-monitor.sh --top 10

# Full system snapshot
./monitoring/system-info.sh
```

## Backup & Restore

```bash
# Backup all sideloaded app data (from macOS)
./backup-restore/backup-app-data.sh --all-sideloaded

# Restore from backup
./backup-restore/restore-app-data.sh ./quest3-backups/<timestamp>/

# Backup Termux environment (run IN Termux on Quest)
./backup-restore/backup-termux.sh

# Restore Termux (run IN Termux)
./backup-restore/restore-termux.sh ~/storage/shared/termux-backups/<timestamp>/
```

## Helpers

```bash
# Auto-start Wi-Fi ADB on boot (copy to ~/.termux/boot/)
cp helpers/wifi-adb-auto.sh ~/.termux/boot/

# Launch apps
./helpers/app-launcher.sh --browser
./helpers/app-launcher.sh com.my.app

# Take a screenshot
./helpers/screenshot.sh -o ~/Pictures --open
```
