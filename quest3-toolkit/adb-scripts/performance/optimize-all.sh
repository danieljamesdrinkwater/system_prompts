#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# optimize-all.sh - Apply Quest 3 "dev productivity" performance profile via ADB
# ==============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Profile: Dev Productivity ---
PROFILE_NAME="Dev Productivity"
PROFILE_REFRESH_RATE=120
PROFILE_CPU_LEVEL=3
PROFILE_GPU_LEVEL=3

# --- Functions ---
print_usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

Apply the Quest 3 "${PROFILE_NAME}" performance profile via ADB.

This profile tunes the device for a responsive development and testing
experience without overriding the current display resolution.

${BOLD}Profile settings:${RESET}
  Refresh rate:   ${PROFILE_REFRESH_RATE}Hz
  CPU level:      ${PROFILE_CPU_LEVEL} (of 0-4)
  GPU level:      ${PROFILE_GPU_LEVEL} (of 0-4)
  Resolution:     (unchanged, keeps current setting)

${BOLD}Options:${RESET}
  --help          Show this help message

${BOLD}Examples:${RESET}
  $(basename "$0")

${BOLD}Note:${RESET} CPU/GPU levels and refresh rate reset on device reboot.
       Run this script again after rebooting.
EOF
}

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*"; }

check_adb() {
    if ! command -v adb &>/dev/null; then
        log_error "ADB is not installed or not in PATH."
        echo "       Install it via: brew install android-platform-tools (macOS)"
        echo "       Or:             sudo apt install adb (Linux)"
        exit 1
    fi
}

check_device() {
    local devices
    devices=$(adb devices 2>/dev/null | tail -n +2 | grep -w "device" || true)
    if [[ -z "$devices" ]]; then
        log_error "No ADB device connected."
        echo "       Make sure your Quest 3 is connected via USB and developer mode is enabled."
        echo "       Run 'adb devices' to troubleshoot."
        exit 1
    fi
    local device_id
    device_id=$(echo "$devices" | head -1 | awk '{print $1}')
    log_info "Connected device: ${BOLD}${device_id}${RESET}"
}

get_prop_or_default() {
    local prop="$1"
    local val
    val=$(adb shell getprop "$prop" 2>/dev/null || echo "")
    if [[ -z "$val" ]]; then
        echo "(not set)"
    else
        echo "$val"
    fi
}

print_full_state() {
    local refresh cpu gpu resolution density
    refresh=$(get_prop_or_default debug.oculus.refreshRate)
    cpu=$(get_prop_or_default debug.oculus.cpuLevel)
    gpu=$(get_prop_or_default debug.oculus.gpuLevel)
    resolution=$(adb shell wm size 2>/dev/null | tail -1 || echo "unknown")
    density=$(adb shell wm density 2>/dev/null | tail -1 || echo "unknown")

    echo -e "  Refresh rate: ${BOLD}${refresh}${RESET}"
    echo -e "  CPU level:    ${BOLD}${cpu}${RESET}"
    echo -e "  GPU level:    ${BOLD}${gpu}${RESET}"
    echo -e "  Resolution:   ${BOLD}${resolution}${RESET}"
    echo -e "  Density:      ${BOLD}${density}${RESET}"
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# --- Preflight ---
check_adb
check_device

echo ""
echo -e "${BOLD}========================================${RESET}"
echo -e "${BOLD} Quest 3 - ${PROFILE_NAME} Profile${RESET}"
echo -e "${BOLD}========================================${RESET}"
echo ""

echo -e "${BOLD}--- Current State ---${RESET}"
print_full_state
echo ""

# --- Apply settings ---
ERRORS=0

log_info "Setting refresh rate to ${BOLD}${PROFILE_REFRESH_RATE}Hz${RESET}..."
if adb shell setprop debug.oculus.refreshRate "$PROFILE_REFRESH_RATE"; then
    log_success "Refresh rate set to ${PROFILE_REFRESH_RATE}Hz."
else
    log_error "Failed to set refresh rate."
    ERRORS=$((ERRORS + 1))
fi

log_info "Setting CPU level to ${BOLD}${PROFILE_CPU_LEVEL}${RESET}..."
if adb shell setprop debug.oculus.cpuLevel "$PROFILE_CPU_LEVEL"; then
    log_success "CPU level set to ${PROFILE_CPU_LEVEL}."
else
    log_error "Failed to set CPU level."
    ERRORS=$((ERRORS + 1))
fi

log_info "Setting GPU level to ${BOLD}${PROFILE_GPU_LEVEL}${RESET}..."
if adb shell setprop debug.oculus.gpuLevel "$PROFILE_GPU_LEVEL"; then
    log_success "GPU level set to ${PROFILE_GPU_LEVEL}."
else
    log_error "Failed to set GPU level."
    ERRORS=$((ERRORS + 1))
fi

log_info "Resolution left unchanged (keeping current setting)."

echo ""
echo -e "${BOLD}--- Updated State ---${RESET}"
print_full_state
echo ""

# --- Summary ---
echo -e "${BOLD}========================================${RESET}"
echo -e "${BOLD} Profile Summary: ${PROFILE_NAME}${RESET}"
echo -e "${BOLD}========================================${RESET}"
echo -e "  Refresh rate:  ${GREEN}${PROFILE_REFRESH_RATE}Hz${RESET}"
echo -e "  CPU level:     ${GREEN}${PROFILE_CPU_LEVEL}${RESET}"
echo -e "  GPU level:     ${GREEN}${PROFILE_GPU_LEVEL}${RESET}"
echo -e "  Resolution:    ${CYAN}unchanged${RESET}"
echo ""

if (( ERRORS > 0 )); then
    log_warn "${ERRORS} setting(s) failed to apply. Check the output above."
    exit 1
else
    log_success "All settings applied successfully."
fi

echo ""
log_warn "CPU/GPU levels and refresh rate will reset on device reboot."
log_info "Re-run this script after rebooting to reapply."
