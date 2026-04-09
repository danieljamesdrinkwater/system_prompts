#!/usr/bin/env bash
set -euo pipefail

# auto-reconnect.sh — Keep a wireless ADB connection to an Oculus Quest 3 alive.
# Monitors connectivity and automatically reconnects when the link drops.

readonly DEFAULT_PORT=5555
readonly DEFAULT_INTERVAL=30
readonly DEFAULT_MAX_RETRIES=10

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ts()      { date '+%Y-%m-%d %H:%M:%S'; }
info()    { printf "${CYAN}[INFO  %s]${RESET}  %s\n" "$(ts)" "$*"; }
success() { printf "${GREEN}[OK    %s]${RESET}  %s\n" "$(ts)" "$*"; }
warn()    { printf "${YELLOW}[WARN  %s]${RESET}  %s\n" "$(ts)" "$*"; }
error()   { printf "${RED}[ERROR %s]${RESET} %s\n" "$(ts)" "$*" >&2; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Keep a wireless ADB connection to an Oculus Quest 3 alive.

Options:
  --ip <IP>             Device IP address (auto-detected if omitted)
  --port <PORT>         ADB port (default: ${DEFAULT_PORT})
  --interval <SECONDS>  Seconds between connectivity checks (default: ${DEFAULT_INTERVAL})
  --max-retries <N>     Max consecutive reconnect attempts before giving up (default: ${DEFAULT_MAX_RETRIES})
  -h, --help            Show this help message

Examples:
  $(basename "$0")
  $(basename "$0") --ip 192.168.1.42
  $(basename "$0") --ip 192.168.1.42 --interval 15 --max-retries 5
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DEVICE_IP=""
PORT="$DEFAULT_PORT"
INTERVAL="$DEFAULT_INTERVAL"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)
            DEVICE_IP="${2:-}"
            [[ -z "$DEVICE_IP" ]] && die "--ip requires an IP address argument."
            shift 2
            ;;
        --port)
            PORT="${2:-}"
            [[ -z "$PORT" ]] && die "--port requires a port number argument."
            shift 2
            ;;
        --interval)
            INTERVAL="${2:-}"
            [[ -z "$INTERVAL" ]] && die "--interval requires a number of seconds."
            shift 2
            ;;
        --max-retries)
            MAX_RETRIES="${2:-}"
            [[ -z "$MAX_RETRIES" ]] && die "--max-retries requires a number."
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            die "Unknown option: $1 (use --help for usage)"
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate ADB
# ---------------------------------------------------------------------------
if ! command -v adb &>/dev/null; then
    die "ADB is not installed or not in PATH."
fi

# ---------------------------------------------------------------------------
# Auto-detect IP if not supplied
# ---------------------------------------------------------------------------
auto_detect_ip() {
    # Try to pull the IP from a currently connected wireless device first.
    local connected
    connected=$(adb devices 2>/dev/null | grep -oP '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(?=:)' | head -n 1 || true)
    if [[ -n "$connected" ]]; then
        echo "$connected"
        return
    fi

    # Fall back to reading wlan0 from a USB-connected device.
    local wlan_output
    wlan_output=$(adb shell ip addr show wlan0 2>/dev/null || true)
    echo "$wlan_output" | grep -oP 'inet \K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true
}

if [[ -z "$DEVICE_IP" ]]; then
    info "No --ip provided. Attempting auto-detection..."
    DEVICE_IP=$(auto_detect_ip)
    if [[ -z "$DEVICE_IP" ]]; then
        die "Could not auto-detect device IP. Provide one with --ip <IP>."
    fi
    success "Auto-detected device IP: ${DEVICE_IP}"
fi

readonly TARGET="${DEVICE_IP}:${PORT}"

# ---------------------------------------------------------------------------
# Trap for clean exit on Ctrl+C / SIGTERM
# ---------------------------------------------------------------------------
RUNNING=true

cleanup() {
    RUNNING=false
    echo ""
    info "Shutting down auto-reconnect monitor."
    info "Final status — target: ${TARGET}"
    # Show current ADB state for the user.
    local status
    status=$(adb devices 2>/dev/null | grep "$TARGET" || true)
    if [[ -n "$status" ]]; then
        info "Device is still connected: ${status}"
    else
        warn "Device is not currently connected."
    fi
    info "Goodbye."
    exit 0
}

trap cleanup SIGINT SIGTERM

# ---------------------------------------------------------------------------
# Connection check
# ---------------------------------------------------------------------------
is_connected() {
    adb devices 2>/dev/null | grep -q "${TARGET}.*device"
}

# ---------------------------------------------------------------------------
# Reconnect
# ---------------------------------------------------------------------------
attempt_reconnect() {
    local attempt=0
    while (( attempt < MAX_RETRIES )); do
        (( attempt++ ))
        warn "Reconnect attempt ${attempt}/${MAX_RETRIES} to ${TARGET}..."

        local output
        output=$(adb connect "$TARGET" 2>&1 || true)

        # Give the connection a moment to stabilise.
        sleep 2

        if is_connected; then
            success "Reconnected to ${TARGET} (attempt ${attempt})."
            return 0
        fi

        warn "Attempt ${attempt} result: ${output}"
        sleep 3
    done

    error "Failed to reconnect after ${MAX_RETRIES} attempts."
    return 1
}

# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------
echo ""
printf "${BOLD}${CYAN}========================================${RESET}\n"
printf "${BOLD}${CYAN}  Quest 3 Wi-Fi ADB Auto-Reconnect${RESET}\n"
printf "${BOLD}${CYAN}  Target:      %s${RESET}\n" "$TARGET"
printf "${BOLD}${CYAN}  Interval:    %ss${RESET}\n" "$INTERVAL"
printf "${BOLD}${CYAN}  Max retries: %s${RESET}\n" "$MAX_RETRIES"
printf "${BOLD}${CYAN}========================================${RESET}\n"
echo ""

consecutive_failures=0
was_connected=false

while $RUNNING; do
    if is_connected; then
        if ! $was_connected; then
            success "Device is online: ${TARGET}"
            was_connected=true
        else
            printf "${DIM}[CHECK %s]  Connection OK${RESET}\n" "$(ts)"
        fi
        consecutive_failures=0
    else
        if $was_connected; then
            warn "Connection to ${TARGET} lost!"
            was_connected=false
        fi

        if ! attempt_reconnect; then
            (( consecutive_failures++ ))
            error "Consecutive full-cycle failures: ${consecutive_failures}"
            if (( consecutive_failures >= 3 )); then
                die "Too many consecutive reconnection failures. Exiting."
            fi
        else
            consecutive_failures=0
            was_connected=true
        fi
    fi

    # Sleep in 1-second ticks so the trap can fire promptly.
    remaining=$INTERVAL
    while (( remaining > 0 )) && $RUNNING; do
        sleep 1
        (( remaining-- ))
    done
done
