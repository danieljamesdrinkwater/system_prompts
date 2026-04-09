#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# system-info.sh - Quest 3 System Information (runs from macOS via ADB)
# =============================================================================
# Aggregate snapshot of device info: model, Android version, firmware,
# IP addresses, battery, storage, uptime, and Wi-Fi SSID.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Quest 3 System Information${RESET}

Options:
  --json         Output as JSON (for scripting)
  -h, --help     Show this help message
EOF
}

JSON_MODE=false

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

safe_adb_prop() {
    adb shell getprop "$1" 2>/dev/null | tr -d '\r' || echo "N/A"
}

safe_adb_shell() {
    adb shell "$@" 2>/dev/null | tr -d '\r' || echo "N/A"
}

print_section() {
    echo -e "\n  ${BOLD}${CYAN}$1${RESET}"
    echo -e "  ${DIM}$(printf '%.0s-' {1..50})${RESET}"
}

print_row() {
    printf "  ${BOLD}%-22s${RESET} %s\n" "$1:" "$2"
}

print_system_info() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo -e "${DIM}${timestamp}${RESET}"
    echo -e "${BOLD}${CYAN}========================================${RESET}"
    echo -e "${BOLD}${CYAN}   Quest 3 System Information Report    ${RESET}"
    echo -e "${BOLD}${CYAN}========================================${RESET}"

    # --- Device Info ---
    print_section "Device"

    local model brand device product
    model=$(safe_adb_prop ro.product.model)
    brand=$(safe_adb_prop ro.product.brand)
    device=$(safe_adb_prop ro.product.device)
    product=$(safe_adb_prop ro.product.name)

    print_row "Model" "$model"
    print_row "Brand" "$brand"
    print_row "Device" "$device"
    print_row "Product" "$product"

    # --- Software ---
    print_section "Software"

    local android_ver sdk_ver build_id security_patch
    android_ver=$(safe_adb_prop ro.build.version.release)
    sdk_ver=$(safe_adb_prop ro.build.version.sdk)
    build_id=$(safe_adb_prop ro.build.display.id)
    security_patch=$(safe_adb_prop ro.build.version.security_patch)

    # Quest firmware version (Meta-specific props)
    local quest_fw runtime_ver
    quest_fw=$(safe_adb_prop ro.build.version.incremental)
    runtime_ver=$(safe_adb_prop sys.oculus.runtime_version)

    print_row "Android Version" "$android_ver (SDK $sdk_ver)"
    print_row "Build ID" "$build_id"
    print_row "Firmware" "$quest_fw"
    if [[ "$runtime_ver" != "N/A" && -n "$runtime_ver" ]]; then
        print_row "Runtime Version" "$runtime_ver"
    fi
    print_row "Security Patch" "$security_patch"

    # --- Battery ---
    print_section "Battery"

    local battery_dump level status temperature
    battery_dump=$(adb shell dumpsys battery 2>/dev/null || echo "")
    level=$(echo "$battery_dump" | grep "level:" | head -1 | sed 's/.*: //' | tr -d '\r')
    status=$(echo "$battery_dump" | grep "status:" | head -1 | sed 's/.*: //' | tr -d '\r')
    temperature=$(echo "$battery_dump" | grep "temperature:" | head -1 | sed 's/.*: //' | tr -d '\r')

    local status_str="Unknown"
    case "${status:-0}" in
        2) status_str="${GREEN}Charging${RESET}" ;;
        3) status_str="${YELLOW}Discharging${RESET}" ;;
        4) status_str="Not charging" ;;
        5) status_str="${GREEN}Full${RESET}" ;;
    esac

    local temp_str="N/A"
    if [[ -n "$temperature" && "$temperature" != "N/A" ]]; then
        local temp_c temp_f
        temp_c=$(awk "BEGIN {printf \"%.1f\", ${temperature} / 10}")
        temp_f=$(awk "BEGIN {printf \"%.1f\", (${temperature} / 10) * 9/5 + 32}")
        temp_str="${temp_c}°C / ${temp_f}°F"
    fi

    local level_color="$RESET"
    if [[ -n "$level" ]]; then
        if (( level <= 15 )); then
            level_color="$RED"
        elif (( level <= 40 )); then
            level_color="$YELLOW"
        else
            level_color="$GREEN"
        fi
    fi

    print_row "Level" "${level_color}${level:-N/A}%${RESET}"
    echo -e "$(print_row "Status" "$status_str")"
    print_row "Temperature" "$temp_str"

    # --- Storage ---
    print_section "Storage"

    local df_output data_line
    df_output=$(adb shell df -h 2>/dev/null || echo "")

    data_line=$(echo "$df_output" | awk '$NF == "/data" {print $0}' | head -1)
    if [[ -n "$data_line" ]]; then
        local d_size d_used d_avail d_pct
        d_size=$(echo "$data_line" | awk '{print $2}')
        d_used=$(echo "$data_line" | awk '{print $3}')
        d_avail=$(echo "$data_line" | awk '{print $4}')
        d_pct=$(echo "$data_line" | awk '{print $5}')
        print_row "/data (apps)" "${d_used} / ${d_size} (${d_pct} used, ${d_avail} free)"
    fi

    local sdcard_line
    sdcard_line=$(echo "$df_output" | awk '$NF ~ /\/sdcard$|\/storage\/emulated/ {print $0}' | head -1)
    if [[ -n "$sdcard_line" ]]; then
        local s_size s_used s_avail s_pct
        s_size=$(echo "$sdcard_line" | awk '{print $2}')
        s_used=$(echo "$sdcard_line" | awk '{print $3}')
        s_avail=$(echo "$sdcard_line" | awk '{print $4}')
        s_pct=$(echo "$sdcard_line" | awk '{print $5}')
        print_row "/sdcard (shared)" "${s_used} / ${s_size} (${s_pct} used, ${s_avail} free)"
    fi

    # --- Network ---
    print_section "Network"

    local wifi_ssid ip_addr
    wifi_ssid=$(safe_adb_shell dumpsys wifi | grep "mWifiInfo" | grep -o 'SSID: [^,]*' | head -1 | sed 's/SSID: //')
    if [[ -z "$wifi_ssid" || "$wifi_ssid" == "N/A" ]]; then
        wifi_ssid=$(safe_adb_shell cmd wifi status | grep -o 'SSID: [^,]*' | head -1 | sed 's/SSID: //')
    fi

    ip_addr=$(safe_adb_shell ip route | grep "src" | head -1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
    if [[ -z "$ip_addr" || "$ip_addr" == "N/A" ]]; then
        ip_addr=$(safe_adb_prop dhcp.wlan0.ipaddress)
    fi

    local wlan_ip
    wlan_ip=$(safe_adb_shell ifconfig wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | sed 's/addr://')

    print_row "Wi-Fi SSID" "${wifi_ssid:-N/A}"
    print_row "IP Address" "${ip_addr:-N/A}"
    if [[ -n "$wlan_ip" && "$wlan_ip" != "N/A" && "$wlan_ip" != "$ip_addr" ]]; then
        print_row "wlan0 IP" "$wlan_ip"
    fi

    # --- Uptime ---
    print_section "System"

    local uptime_str
    uptime_str=$(safe_adb_shell uptime | sed 's/^.*up /up /' | sed 's/,.*load/ load/')

    local kernel
    kernel=$(safe_adb_shell uname -r)

    print_row "Uptime" "$uptime_str"
    print_row "Kernel" "$kernel"

    # --- ADB Connection ---
    local serial
    serial=$(adb get-serialno 2>/dev/null | tr -d '\r' || echo "N/A")
    print_row "Serial" "$serial"

    echo ""
    echo -e "${BOLD}${CYAN}========================================${RESET}"
}

print_json_info() {
    local model android_ver build_id quest_fw level ip_addr wifi_ssid uptime_str

    model=$(safe_adb_prop ro.product.model)
    android_ver=$(safe_adb_prop ro.build.version.release)
    build_id=$(safe_adb_prop ro.build.display.id)
    quest_fw=$(safe_adb_prop ro.build.version.incremental)
    level=$(adb shell dumpsys battery 2>/dev/null | grep "level:" | head -1 | sed 's/.*: //' | tr -d '\r')
    ip_addr=$(safe_adb_shell ip route | grep "src" | head -1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
    wifi_ssid=$(safe_adb_shell dumpsys wifi | grep "mWifiInfo" | grep -o 'SSID: [^,]*' | head -1 | sed 's/SSID: //')
    uptime_str=$(safe_adb_shell uptime)

    cat <<ENDJSON
{
  "model": "${model}",
  "android_version": "${android_ver}",
  "build_id": "${build_id}",
  "firmware": "${quest_fw}",
  "battery_level": ${level:-0},
  "ip_address": "${ip_addr:-}",
  "wifi_ssid": "${wifi_ssid:-}",
  "uptime": "${uptime_str}"
}
ENDJSON
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            JSON_MODE=true
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

if $JSON_MODE; then
    print_json_info
else
    print_system_info
fi
