#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# =============================================================================
# wifi-adb-auto.sh - Wireless ADB Auto-Setup (runs INSIDE Termux on Quest 3)
# =============================================================================
# Designed for Termux:Boot - on boot, enables ADB TCP mode on port 5555
# and logs the device IP so the user knows what to connect to.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

ADB_PORT=5555
LOG_FILE="$HOME/.wifi-adb-auto.log"
QUIET=false

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Wireless ADB Auto-Setup for Termux:Boot${RESET}

Enables ADB over TCP on port 5555 at boot and prints/logs the device IP.
Place in ~/.termux/boot/ for automatic execution on device start.

Options:
  --port <N>       ADB TCP port (default: 5555)
  --log <file>     Log file path (default: ~/.wifi-adb-auto.log)
  --quiet          Suppress terminal output (log only)
  -h, --help       Show this help message

Setup:
  mkdir -p ~/.termux/boot
  cp wifi-adb-auto.sh ~/.termux/boot/
  chmod +x ~/.termux/boot/wifi-adb-auto.sh
EOF
}

log_msg() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" >> "$LOG_FILE"
    if ! $QUIET; then
        echo -e "$2"
    fi
}

get_device_ip() {
    local ip=""

    # Method 1: ip route
    ip=$(ip route 2>/dev/null | grep "src" | head -1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')

    # Method 2: ifconfig wlan0
    if [[ -z "$ip" ]]; then
        ip=$(ifconfig wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | sed 's/addr://')
    fi

    # Method 3: getprop
    if [[ -z "$ip" ]]; then
        ip=$(getprop dhcp.wlan0.ipaddress 2>/dev/null || true)
    fi

    echo "$ip"
}

wait_for_network() {
    local max_wait=60
    local waited=0

    while (( waited < max_wait )); do
        local ip
        ip=$(get_device_ip)
        if [[ -n "$ip" && "$ip" != "127.0.0.1" ]]; then
            echo "$ip"
            return 0
        fi
        sleep 2
        ((waited += 2)) || true
    done

    return 1
}

run_setup() {
    # Rotate log if too large (> 100KB)
    if [[ -f "$LOG_FILE" ]]; then
        local log_size
        log_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo "0")
        if (( log_size > 102400 )); then
            mv "$LOG_FILE" "${LOG_FILE}.old"
        fi
    fi

    log_msg "=== Wi-Fi ADB Auto-Setup Starting ===" \
            "${BOLD}${CYAN}--- Wi-Fi ADB Auto-Setup ---${RESET}"

    # Wait for network connectivity
    log_msg "Waiting for network..." \
            "  ${DIM}Waiting for network connectivity...${RESET}"

    local device_ip
    if device_ip=$(wait_for_network); then
        log_msg "Network ready. IP: ${device_ip}" \
                "  ${GREEN}Network ready.${RESET} IP: ${BOLD}${device_ip}${RESET}"
    else
        log_msg "ERROR: Network not available after 60s" \
                "  ${RED}Error:${RESET} Network not available after 60s timeout."
        exit 1
    fi

    # Enable ADB TCP mode
    log_msg "Setting ADB to TCP mode on port ${ADB_PORT}..." \
            "  ${DIM}Enabling ADB TCP on port ${ADB_PORT}...${RESET}"

    if setprop service.adb.tcp.port "$ADB_PORT" 2>/dev/null; then
        log_msg "Set ADB TCP port property" \
                "  ${GREEN}ADB TCP port set.${RESET}"
    else
        log_msg "Warning: Could not set ADB TCP port via setprop" \
                "  ${YELLOW}Warning:${RESET} Could not set ADB TCP port via setprop."
    fi

    # Try to restart adbd (may need root)
    if stop adbd 2>/dev/null && start adbd 2>/dev/null; then
        log_msg "ADB daemon restarted" \
                "  ${GREEN}ADB daemon restarted.${RESET}"
    else
        log_msg "Note: Could not restart adbd (may need root or manual restart)" \
                "  ${DIM}Note: Could not restart adbd. ADB TCP may already be active,${RESET}"
        log_msg "" \
                "  ${DIM}or you may need to enable it via developer settings.${RESET}"
    fi

    # Print connection info
    local connect_cmd="adb connect ${device_ip}:${ADB_PORT}"

    log_msg "=== Ready ===" \
            ""
    log_msg "Device IP: ${device_ip}" \
            "  ${BOLD}${GREEN}=== Wireless ADB Ready ===${RESET}"
    log_msg "Port: ${ADB_PORT}" \
            ""
    log_msg "Connect command: ${connect_cmd}" \
            "  ${BOLD}Connect from your computer:${RESET}"

    if ! $QUIET; then
        echo ""
        echo -e "    ${CYAN}${connect_cmd}${RESET}"
        echo ""
        echo -e "  ${DIM}Log file: ${LOG_FILE}${RESET}"
        echo -e "${BOLD}${CYAN}----------------------------${RESET}"
    fi

    # Write a connection file to shared storage for easy reference
    if [[ -d "$HOME/storage/shared" ]]; then
        local connect_file="$HOME/storage/shared/quest3-adb-connect.txt"
        cat > "$connect_file" <<CONN
Quest 3 Wireless ADB Connection
================================
IP Address: ${device_ip}
Port:       ${ADB_PORT}
Updated:    $(date '+%Y-%m-%d %H:%M:%S')

Connect command:
  ${connect_cmd}
CONN
        log_msg "Connection info saved to shared storage" \
                "  ${DIM}Connection info saved: ${connect_file}${RESET}"
    fi
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            ADB_PORT="${2:?--port requires a number}"
            shift 2
            ;;
        --log)
            LOG_FILE="${2:?--log requires a file path}"
            shift 2
            ;;
        --quiet)
            QUIET=true
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
run_setup
