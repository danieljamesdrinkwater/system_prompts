#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# battery-monitor.sh - Quest 3 Battery Monitor (runs from macOS via ADB)
# =============================================================================
# Parses "adb shell dumpsys battery" for level, temperature, charging status,
# health, and voltage. Supports single-shot and continuous watch mode.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

WATCH_MODE=false
POLL_INTERVAL=10

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Quest 3 Battery Monitor${RESET}

Options:
  --watch [N]    Poll every N seconds (default: 10)
  -h, --help     Show this help message

Examples:
  $(basename "$0")              # Single-shot battery report
  $(basename "$0") --watch      # Poll every 10 seconds
  $(basename "$0") --watch 5    # Poll every 5 seconds
EOF
}

check_prerequisites() {
    if ! command -v adb &>/dev/null; then
        echo -e "${RED}Error:${RESET} adb not found in PATH." >&2
        echo "Install Android platform-tools or add them to your PATH." >&2
        exit 1
    fi

    if ! adb get-state &>/dev/null 2>&1; then
        echo -e "${RED}Error:${RESET} No ADB device connected." >&2
        echo "Connect your Quest 3 via USB or wireless ADB." >&2
        exit 1
    fi
}

parse_battery_field() {
    local dump="$1" field="$2"
    echo "$dump" | grep -i "^\s*${field}:" | head -1 | sed 's/.*: //'
}

health_to_string() {
    case "$1" in
        2) echo "Good" ;;
        3) echo "Overheat" ;;
        4) echo "Dead" ;;
        5) echo "Over voltage" ;;
        6) echo "Unspecified failure" ;;
        7) echo "Cold" ;;
        *) echo "Unknown ($1)" ;;
    esac
}

status_to_string() {
    case "$1" in
        1) echo "Unknown" ;;
        2) echo "Charging" ;;
        3) echo "Discharging" ;;
        4) echo "Not charging" ;;
        5) echo "Full" ;;
        *) echo "Unknown ($1)" ;;
    esac
}

battery_bar() {
    local level=$1
    local width=30
    local filled=$(( level * width / 100 ))
    local empty=$(( width - filled ))
    local color="$GREEN"

    if (( level <= 15 )); then
        color="$RED"
    elif (( level <= 40 )); then
        color="$YELLOW"
    fi

    printf "${color}["
    printf '%0.s#' $(seq 1 "$filled" 2>/dev/null) || true
    printf '%0.s-' $(seq 1 "$empty" 2>/dev/null) || true
    printf "]${RESET}"
}

print_battery_report() {
    local dump
    dump=$(adb shell dumpsys battery 2>/dev/null)

    if [[ -z "$dump" ]]; then
        echo -e "${RED}Error:${RESET} Failed to read battery data." >&2
        return 1
    fi

    local level status health temperature voltage plugged
    level=$(parse_battery_field "$dump" "level")
    status=$(parse_battery_field "$dump" "status")
    health=$(parse_battery_field "$dump" "health")
    temperature=$(parse_battery_field "$dump" "temperature")
    voltage=$(parse_battery_field "$dump" "voltage")
    plugged=$(parse_battery_field "$dump" "plugged")

    # Temperature: dumpsys reports in tenths of degrees C
    local temp_c temp_f
    if [[ -n "$temperature" ]]; then
        temp_c=$(awk "BEGIN {printf \"%.1f\", ${temperature} / 10}")
        temp_f=$(awk "BEGIN {printf \"%.1f\", (${temperature} / 10) * 9/5 + 32}")
    else
        temp_c="N/A"
        temp_f="N/A"
    fi

    # Voltage: dumpsys reports in millivolts
    local voltage_v="N/A"
    if [[ -n "$voltage" ]]; then
        voltage_v=$(awk "BEGIN {printf \"%.2f\", ${voltage} / 1000}")
    fi

    local status_str health_str plugged_str
    status_str=$(status_to_string "${status:-0}")
    health_str=$(health_to_string "${health:-0}")

    case "${plugged:-0}" in
        0) plugged_str="Not plugged in" ;;
        1) plugged_str="AC charger" ;;
        2) plugged_str="USB" ;;
        4) plugged_str="Wireless" ;;
        *) plugged_str="Unknown (${plugged})" ;;
    esac

    local status_color="$RESET"
    if [[ "$status_str" == "Charging" ]]; then
        status_color="$GREEN"
    elif [[ "$status_str" == "Discharging" ]]; then
        status_color="$YELLOW"
    fi

    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo -e "${DIM}${timestamp}${RESET}"
    echo -e "${BOLD}${CYAN}--- Quest 3 Battery Report ---${RESET}"
    printf "  %-14s %s %s%%\n" "Level:" "$(battery_bar "${level:-0}")" "${level:-N/A}"
    echo -e "  Status:        ${status_color}${status_str}${RESET}"
    echo -e "  Plugged:       ${plugged_str}"
    echo -e "  Health:        ${health_str}"
    echo -e "  Temperature:   ${temp_c}°C / ${temp_f}°F"
    echo -e "  Voltage:       ${voltage_v}V"
    echo -e "${BOLD}${CYAN}------------------------------${RESET}"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --watch)
            WATCH_MODE=true
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
                POLL_INTERVAL="$2"
                shift
            fi
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error:${RESET} Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# --- Main ---
check_prerequisites

if $WATCH_MODE; then
    echo -e "${BOLD}Watching battery every ${POLL_INTERVAL}s${RESET} (Ctrl+C to stop)"
    echo ""
    while true; do
        print_battery_report
        echo ""
        sleep "$POLL_INTERVAL"
    done
else
    print_battery_report
fi
