#!/usr/bin/env bash
set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") <ACTION> [ARGUMENTS]

Manage sideloaded (third-party) apps on a connected Quest 3 device.

${BOLD}Actions:${RESET}
  --list                     List all sideloaded apps
  --uninstall <package>      Uninstall a sideloaded app
  --clear <package>          Clear app data and cache
  --info <package>           Show detailed app info (version, paths, size)

${BOLD}Options:${RESET}
  --help                     Show this help message

${BOLD}Examples:${RESET}
  $(basename "$0") --list
  $(basename "$0") --info com.example.myapp
  $(basename "$0") --uninstall com.example.myapp
  $(basename "$0") --clear com.example.myapp
EOF
}

validate_adb() {
    if ! command -v adb &>/dev/null; then
        echo -e "${RED}Error: adb is not installed or not in PATH.${RESET}" >&2
        exit 1
    fi
}

validate_device() {
    local devices
    devices="$(adb devices 2>/dev/null | tail -n +2 | grep -w 'device' || true)"
    if [[ -z "$devices" ]]; then
        echo -e "${RED}Error: No Quest 3 device connected or not authorized.${RESET}" >&2
        echo -e "${YELLOW}Tip: Check USB connection and confirm the authorization prompt in your headset.${RESET}" >&2
        exit 1
    fi
    echo -e "${GREEN}Device connected.${RESET}"
}

list_sideloaded() {
    echo -e "${BOLD}Sideloaded (third-party) apps:${RESET}"
    echo ""

    local packages
    packages="$(adb shell pm list packages -3 2>/dev/null | sed 's/^package://' | sort)"

    if [[ -z "$packages" ]]; then
        echo -e "  ${YELLOW}No sideloaded apps found.${RESET}"
        return
    fi

    local count=0
    while IFS= read -r pkg; do
        [[ -z "$pkg" ]] && continue
        echo -e "  ${CYAN}${pkg}${RESET}"
        ((count++)) || true
    done <<< "$packages"

    echo ""
    echo -e "${GREEN}${BOLD}Total: ${count} sideloaded app(s).${RESET}"
}

uninstall_app() {
    local pkg="$1"

    echo -e "${BOLD}Uninstalling ${CYAN}${pkg}${RESET}${BOLD}...${RESET}"

    # Verify the package exists
    if ! adb shell pm list packages 2>/dev/null | grep -q "^package:${pkg}$"; then
        echo -e "${RED}Error: Package '${pkg}' not found on device.${RESET}" >&2
        exit 1
    fi

    echo -ne "  Removing ${CYAN}${pkg}${RESET} ... "
    local output
    if output="$(adb uninstall "$pkg" 2>&1)"; then
        if echo "$output" | grep -qi "success"; then
            echo -e "${GREEN}SUCCESS${RESET}"
        else
            echo -e "${YELLOW}Done${RESET} (${output})"
        fi
    else
        echo -e "${RED}FAILED${RESET}"
        echo -e "  ${RED}${output}${RESET}" >&2
        exit 1
    fi
}

clear_app_data() {
    local pkg="$1"

    echo -e "${BOLD}Clearing data for ${CYAN}${pkg}${RESET}${BOLD}...${RESET}"

    # Verify the package exists
    if ! adb shell pm list packages 2>/dev/null | grep -q "^package:${pkg}$"; then
        echo -e "${RED}Error: Package '${pkg}' not found on device.${RESET}" >&2
        exit 1
    fi

    echo -ne "  Clearing data for ${CYAN}${pkg}${RESET} ... "
    local output
    if output="$(adb shell pm clear "$pkg" 2>&1)"; then
        if echo "$output" | grep -qi "success"; then
            echo -e "${GREEN}SUCCESS${RESET}"
        else
            echo -e "${YELLOW}Done${RESET} (${output})"
        fi
    else
        echo -e "${RED}FAILED${RESET}"
        echo -e "  ${RED}${output}${RESET}" >&2
        exit 1
    fi
}

show_app_info() {
    local pkg="$1"

    echo -e "${BOLD}App info for ${CYAN}${pkg}${RESET}${BOLD}:${RESET}"
    echo ""

    # Verify the package exists
    if ! adb shell pm list packages 2>/dev/null | grep -q "^package:${pkg}$"; then
        echo -e "${RED}Error: Package '${pkg}' not found on device.${RESET}" >&2
        exit 1
    fi

    # Get the full dumpsys output once
    local dump
    dump="$(adb shell dumpsys package "$pkg" 2>/dev/null)"

    # Version info
    local version_name version_code
    version_name="$(echo "$dump" | grep -m1 "versionName=" | sed 's/.*versionName=//' | tr -d '[:space:]')" || true
    version_code="$(echo "$dump" | grep -m1 "versionCode=" | sed 's/.*versionCode=\([^ ]*\).*/\1/' | tr -d '[:space:]')" || true
    echo -e "  ${BOLD}Version:${RESET}      ${version_name:-unknown} (code: ${version_code:-unknown})"

    # Install path
    local install_path
    install_path="$(echo "$dump" | grep -m1 "codePath=" | sed 's/.*codePath=//' | tr -d '[:space:]')" || true
    echo -e "  ${BOLD}Install path:${RESET} ${install_path:-unknown}"

    # Data directory
    local data_dir
    data_dir="$(echo "$dump" | grep -m1 "dataDir=" | sed 's/.*dataDir=//' | tr -d '[:space:]')" || true
    echo -e "  ${BOLD}Data dir:${RESET}     ${data_dir:-unknown}"

    # First install time
    local first_install
    first_install="$(echo "$dump" | grep -m1 "firstInstallTime=" | sed 's/.*firstInstallTime=//' | xargs)" || true
    echo -e "  ${BOLD}Installed:${RESET}    ${first_install:-unknown}"

    # Last update time
    local last_update
    last_update="$(echo "$dump" | grep -m1 "lastUpdateTime=" | sed 's/.*lastUpdateTime=//' | xargs)" || true
    echo -e "  ${BOLD}Updated:${RESET}      ${last_update:-unknown}"

    # Target SDK
    local target_sdk
    target_sdk="$(echo "$dump" | grep -m1 "targetSdk=" | sed 's/.*targetSdk=//' | tr -d '[:space:]')" || true
    echo -e "  ${BOLD}Target SDK:${RESET}   ${target_sdk:-unknown}"

    # APK size on device
    if [[ -n "$install_path" && "$install_path" != "unknown" ]]; then
        local apk_size
        apk_size="$(adb shell du -sh "${install_path}" 2>/dev/null | cut -f1 || echo "unknown")"
        echo -e "  ${BOLD}APK size:${RESET}     ${apk_size}"
    fi

    # Enabled/disabled status
    local enabled_state
    enabled_state="$(echo "$dump" | grep -m1 "enabled=" | sed 's/.*enabled=//' | cut -d' ' -f1 | tr -d '[:space:]')" || true
    if [[ "$enabled_state" == "0" ]]; then
        echo -e "  ${BOLD}Status:${RESET}       ${GREEN}Enabled${RESET}"
    elif [[ "$enabled_state" == "1" || "$enabled_state" == "2" || "$enabled_state" == "3" ]]; then
        echo -e "  ${BOLD}Status:${RESET}       ${RED}Disabled${RESET}"
    else
        echo -e "  ${BOLD}Status:${RESET}       ${enabled_state:-unknown}"
    fi

    echo ""
}

# --- Main ---
ACTION=""
TARGET_PACKAGE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --list)
            ACTION="list"
            shift
            ;;
        --uninstall)
            ACTION="uninstall"
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}Error: --uninstall requires a package name.${RESET}" >&2
                exit 1
            fi
            TARGET_PACKAGE="$2"
            shift 2
            ;;
        --clear)
            ACTION="clear"
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}Error: --clear requires a package name.${RESET}" >&2
                exit 1
            fi
            TARGET_PACKAGE="$2"
            shift 2
            ;;
        --info)
            ACTION="info"
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}Error: --info requires a package name.${RESET}" >&2
                exit 1
            fi
            TARGET_PACKAGE="$2"
            shift 2
            ;;
        -*)
            echo -e "${RED}Error: Unknown option: $1${RESET}" >&2
            usage >&2
            exit 1
            ;;
        *)
            echo -e "${RED}Error: Unexpected argument: $1${RESET}" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$ACTION" ]]; then
    echo -e "${RED}Error: No action specified.${RESET}" >&2
    usage >&2
    exit 1
fi

validate_adb
validate_device

case "$ACTION" in
    list)
        list_sideloaded
        ;;
    uninstall)
        uninstall_app "$TARGET_PACKAGE"
        ;;
    clear)
        clear_app_data "$TARGET_PACKAGE"
        ;;
    info)
        show_app_info "$TARGET_PACKAGE"
        ;;
esac
