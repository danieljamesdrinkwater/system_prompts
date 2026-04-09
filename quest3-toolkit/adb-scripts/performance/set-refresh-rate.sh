#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# set-refresh-rate.sh - Set Quest 3 display refresh rate via ADB
# ==============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Defaults ---
DEFAULT_RATE=120
VALID_RATES=(72 90 120)

# --- Functions ---
print_usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

Set Quest 3 display refresh rate via ADB.

${BOLD}Options:${RESET}
  --rate RATE     Set refresh rate: 72, 90, or 120 (default: ${DEFAULT_RATE})
  --help          Show this help message

${BOLD}Refresh rate guide:${RESET}
  72Hz    Lowest power consumption, adequate for media and simple apps
  90Hz    Good balance between smoothness and battery life
  120Hz   Smoothest experience, highest power draw (Quest 3 maximum)

${BOLD}Examples:${RESET}
  $(basename "$0") --rate 120
  $(basename "$0") --rate 90
  $(basename "$0")              # defaults to 120Hz

${BOLD}Note:${RESET} This sets debug.oculus.refreshRate. Applications may override this value.
       The setting persists until reboot or until changed again.
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

get_current_rate() {
    local rate
    rate=$(adb shell getprop debug.oculus.refreshRate 2>/dev/null || echo "")
    if [[ -z "$rate" ]]; then
        echo -e "  Refresh rate: ${YELLOW}(not set / device default)${RESET}"
    else
        echo -e "  Refresh rate: ${BOLD}${rate}Hz${RESET}"
    fi
}

is_valid_rate() {
    local rate="$1"
    for v in "${VALID_RATES[@]}"; do
        [[ "$rate" == "$v" ]] && return 0
    done
    return 1
}

# --- Argument parsing ---
RATE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            print_usage
            exit 0
            ;;
        --rate)
            [[ $# -lt 2 ]] && { log_error "--rate requires a value (72, 90, or 120)"; exit 1; }
            RATE="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

RATE="${RATE:-$DEFAULT_RATE}"

# --- Validate ---
if ! is_valid_rate "$RATE"; then
    log_error "Invalid refresh rate: ${RATE}"
    echo "       Valid rates: ${VALID_RATES[*]}"
    exit 1
fi

# --- Preflight ---
check_adb
check_device

echo ""
echo -e "${BOLD}--- Current Refresh Rate ---${RESET}"
get_current_rate
echo ""

# --- Apply ---
log_info "Setting refresh rate to ${BOLD}${RATE}Hz${RESET}..."
adb shell setprop debug.oculus.refreshRate "$RATE"
log_success "Refresh rate set to ${RATE}Hz."

echo ""
echo -e "${BOLD}--- Updated Refresh Rate ---${RESET}"
get_current_rate
echo ""
