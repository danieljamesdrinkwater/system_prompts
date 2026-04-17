#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# set-resolution.sh - Set Quest 3 display resolution via ADB
# ==============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Defaults ---
DEFAULT_WIDTH=2064
DEFAULT_HEIGHT=2208
DEFAULT_DENSITY=570

# --- Functions ---
print_usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

Set Quest 3 display resolution and density via ADB.

${BOLD}Options:${RESET}
  --width W       Set display width (default: ${DEFAULT_WIDTH})
  --height H      Set display height (default: ${DEFAULT_HEIGHT})
  --density D     Set display density (default: ${DEFAULT_DENSITY})
  --reset         Reset resolution and density to device defaults
  --help          Show this help message

${BOLD}Common Quest 3 resolutions (per-eye):${RESET}
  Native:     2064x2208 (highest quality, most demanding)
  High:       1680x1760 (good balance)
  Medium:     1440x1536 (better performance)
  Low:        1200x1280 (maximum performance)

${BOLD}Examples:${RESET}
  $(basename "$0") --width 2064 --height 2208
  $(basename "$0") --reset
  $(basename "$0") --width 1680 --height 1760 --density 480
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

get_current_resolution() {
    local size density
    size=$(adb shell wm size 2>/dev/null | tail -1 || echo "unknown")
    density=$(adb shell wm density 2>/dev/null | tail -1 || echo "unknown")
    echo -e "  Resolution: ${BOLD}${size}${RESET}"
    echo -e "  Density:    ${BOLD}${density}${RESET}"
}

# --- Argument parsing ---
MODE=""
WIDTH=""
HEIGHT=""
DENSITY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            print_usage
            exit 0
            ;;
        --reset)
            MODE="reset"
            shift
            ;;
        --width)
            [[ $# -lt 2 ]] && { log_error "--width requires a value"; exit 1; }
            WIDTH="$2"
            shift 2
            ;;
        --height)
            [[ $# -lt 2 ]] && { log_error "--height requires a value"; exit 1; }
            HEIGHT="$2"
            shift 2
            ;;
        --density)
            [[ $# -lt 2 ]] && { log_error "--density requires a value"; exit 1; }
            DENSITY="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# --- Validate ---
if [[ "$MODE" != "reset" ]]; then
    # Apply defaults for any value not explicitly provided
    WIDTH="${WIDTH:-$DEFAULT_WIDTH}"
    HEIGHT="${HEIGHT:-$DEFAULT_HEIGHT}"
    DENSITY="${DENSITY:-$DEFAULT_DENSITY}"

    # Validate numeric
    if ! [[ "$WIDTH" =~ ^[0-9]+$ ]] || ! [[ "$HEIGHT" =~ ^[0-9]+$ ]] || ! [[ "$DENSITY" =~ ^[0-9]+$ ]]; then
        log_error "Width, height, and density must be positive integers."
        exit 1
    fi
fi

# --- Preflight ---
check_adb
check_device

echo ""
echo -e "${BOLD}--- Current Resolution ---${RESET}"
get_current_resolution
echo ""

# --- Apply ---
if [[ "$MODE" == "reset" ]]; then
    log_info "Resetting resolution and density to device defaults..."
    adb shell wm size reset
    adb shell wm density reset
    log_success "Resolution and density reset to defaults."
else
    log_info "Setting resolution to ${BOLD}${WIDTH}x${HEIGHT}${RESET} with density ${BOLD}${DENSITY}${RESET}..."
    adb shell wm size "${WIDTH}x${HEIGHT}"
    adb shell wm density "$DENSITY"
    log_success "Resolution set to ${WIDTH}x${HEIGHT}, density ${DENSITY}."
fi

echo ""
echo -e "${BOLD}--- Updated Resolution ---${RESET}"
get_current_resolution
echo ""
