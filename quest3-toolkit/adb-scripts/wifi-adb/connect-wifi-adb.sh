#!/usr/bin/env bash
set -euo pipefail

# connect-wifi-adb.sh — Set up a wireless ADB connection to an Oculus Quest 3.
# Requires: ADB installed and a Quest 3 connected via USB to start.

readonly PORT=5555

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()    { printf "${CYAN}[INFO]${RESET}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${RESET}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${RESET}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${RESET} %s\n" "$*" >&2; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Step 1: Check ADB is installed
# ---------------------------------------------------------------------------
info "Checking for ADB..."
if ! command -v adb &>/dev/null; then
    die "ADB is not installed or not in PATH. Install it via Android SDK Platform-Tools."
fi
success "ADB found: $(command -v adb)"

# ---------------------------------------------------------------------------
# Step 2: Check a device is connected via USB
# ---------------------------------------------------------------------------
info "Checking for a USB-connected device..."

device_line=$(adb devices 2>/dev/null | grep -E $'\t''device$' | head -n 1 || true)

if [[ -z "$device_line" ]]; then
    die "No device detected. Connect your Quest 3 via USB and ensure USB debugging is enabled."
fi

device_serial=$(echo "$device_line" | awk '{print $1}')
success "Device connected: ${device_serial}"

# ---------------------------------------------------------------------------
# Step 3: Get device IP from wlan0
# ---------------------------------------------------------------------------
info "Retrieving device IP address..."

ip_output=$(adb shell ip addr show wlan0 2>/dev/null || true)

device_ip=$(echo "$ip_output" | grep -oP 'inet \K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)

if [[ -z "$device_ip" ]]; then
    die "Could not determine device IP. Make sure the Quest 3 is connected to Wi-Fi."
fi
success "Device IP: ${device_ip}"

# ---------------------------------------------------------------------------
# Step 4: Switch ADB to TCP/IP mode on port 5555
# ---------------------------------------------------------------------------
info "Switching ADB to TCP/IP mode on port ${PORT}..."

tcpip_output=$(adb tcpip "$PORT" 2>&1 || true)

if echo "$tcpip_output" | grep -qi "error\|failed"; then
    die "Failed to switch to TCP/IP mode: ${tcpip_output}"
fi
success "ADB is now listening on port ${PORT}."

# ---------------------------------------------------------------------------
# Step 5: Prompt user to disconnect USB
# ---------------------------------------------------------------------------
printf "\n${BOLD}${YELLOW}>>> Disconnect the USB cable from your Quest 3, then press Enter to continue...${RESET}"
read -r
echo ""

# Give the device a moment to settle after USB disconnect.
sleep 2

# ---------------------------------------------------------------------------
# Step 6: Connect via Wi-Fi
# ---------------------------------------------------------------------------
info "Connecting to ${device_ip}:${PORT}..."

connect_output=$(adb connect "${device_ip}:${PORT}" 2>&1 || true)

if echo "$connect_output" | grep -qi "connected"; then
    success "ADB connected to ${device_ip}:${PORT}"
else
    die "Connection failed: ${connect_output}"
fi

# ---------------------------------------------------------------------------
# Step 7: Verify connection
# ---------------------------------------------------------------------------
info "Verifying connection..."

sleep 1

verify_line=$(adb devices 2>/dev/null | grep "${device_ip}:${PORT}" || true)

if echo "$verify_line" | grep -q "device"; then
    echo ""
    printf "${GREEN}${BOLD}============================================${RESET}\n"
    printf "${GREEN}${BOLD}  Wireless ADB connected successfully!${RESET}\n"
    printf "${GREEN}${BOLD}  Device: %s:%s${RESET}\n" "$device_ip" "$PORT"
    printf "${GREEN}${BOLD}============================================${RESET}\n"
    echo ""
    info "You can now run ADB commands wirelessly."
    info "To disconnect later:  adb disconnect ${device_ip}:${PORT}"
else
    echo ""
    error "Device appeared in 'adb devices' but status is not 'device'."
    error "Verify line: ${verify_line}"
    die "Wireless ADB connection could not be verified."
fi
