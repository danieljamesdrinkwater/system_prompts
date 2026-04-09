#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# set-cpu-gpu-levels.sh - Set Quest 3 CPU/GPU performance levels via ADB
# ==============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Defaults ---
MIN_LEVEL=0
MAX_LEVEL=4

# --- Functions ---
print_usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

Set Quest 3 CPU and GPU performance levels via ADB.

${BOLD}Options:${RESET}
  --cpu N         Set CPU performance level (0-4)
  --gpu N         Set GPU performance level (0-4)
  --help          Show this help message

${BOLD}Level guide:${RESET}
  0    Lowest clock speed, minimum power draw
  1    Low performance
  2    Balanced (default system behavior)
  3    High performance, recommended for development
  4    Maximum performance, highest power/thermal output

${BOLD}Examples:${RESET}
  $(basename "$0") --cpu 3 --gpu 3
  $(basename "$0") --cpu 4 --gpu 4
  $(basename "$0") --gpu 2

${BOLD}Note:${RESET} These settings use debug.oculus.cpuLevel and debug.oculus.gpuLevel.
       They reset on device reboot. Applications may also override these values.
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

validate_level() {
    local name="$1"
    local value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        log_error "${name} level must be an integer (0-${MAX_LEVEL}), got: ${value}"
        exit 1
    fi
    if (( value < MIN_LEVEL || value > MAX_LEVEL )); then
        log_error "${name} level out of range: ${value} (must be ${MIN_LEVEL}-${MAX_LEVEL})"
        exit 1
    fi
}

get_current_levels() {
    local cpu gpu
    cpu=$(adb shell getprop debug.oculus.cpuLevel 2>/dev/null || echo "")
    gpu=$(adb shell getprop debug.oculus.gpuLevel 2>/dev/null || echo "")
    if [[ -z "$cpu" ]]; then
        echo -e "  CPU level: ${YELLOW}(not set / device default)${RESET}"
    else
        echo -e "  CPU level: ${BOLD}${cpu}${RESET}"
    fi
    if [[ -z "$gpu" ]]; then
        echo -e "  GPU level: ${YELLOW}(not set / device default)${RESET}"
    else
        echo -e "  GPU level: ${BOLD}${gpu}${RESET}"
    fi
}

# --- Argument parsing ---
CPU_LEVEL=""
GPU_LEVEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            print_usage
            exit 0
            ;;
        --cpu)
            [[ $# -lt 2 ]] && { log_error "--cpu requires a value (0-${MAX_LEVEL})"; exit 1; }
            CPU_LEVEL="$2"
            shift 2
            ;;
        --gpu)
            [[ $# -lt 2 ]] && { log_error "--gpu requires a value (0-${MAX_LEVEL})"; exit 1; }
            GPU_LEVEL="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# --- Must specify at least one ---
if [[ -z "$CPU_LEVEL" && -z "$GPU_LEVEL" ]]; then
    log_error "You must specify at least one of --cpu or --gpu."
    echo ""
    print_usage
    exit 1
fi

# --- Validate ---
[[ -n "$CPU_LEVEL" ]] && validate_level "CPU" "$CPU_LEVEL"
[[ -n "$GPU_LEVEL" ]] && validate_level "GPU" "$GPU_LEVEL"

# --- Preflight ---
check_adb
check_device

echo ""
echo -e "${BOLD}--- Current CPU/GPU Levels ---${RESET}"
get_current_levels
echo ""

# --- Apply ---
if [[ -n "$CPU_LEVEL" ]]; then
    log_info "Setting CPU level to ${BOLD}${CPU_LEVEL}${RESET}..."
    adb shell setprop debug.oculus.cpuLevel "$CPU_LEVEL"
    log_success "CPU level set to ${CPU_LEVEL}."
fi

if [[ -n "$GPU_LEVEL" ]]; then
    log_info "Setting GPU level to ${BOLD}${GPU_LEVEL}${RESET}..."
    adb shell setprop debug.oculus.gpuLevel "$GPU_LEVEL"
    log_success "GPU level set to ${GPU_LEVEL}."
fi

echo ""
echo -e "${BOLD}--- Updated CPU/GPU Levels ---${RESET}"
get_current_levels
echo ""

log_warn "These settings will reset on device reboot."
