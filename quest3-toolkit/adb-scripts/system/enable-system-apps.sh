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
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS] [PACKAGE ...]

Re-enable previously disabled system apps on a connected Quest 3 device.

${BOLD}Options:${RESET}
  --all-disabled    Re-enable all currently disabled packages
  --dry-run         Show what would be re-enabled without making changes
  --help            Show this help message

${BOLD}Arguments:${RESET}
  PACKAGE ...       One or more package names to re-enable
                    (e.g. com.oculus.socialplatform)

${BOLD}Examples:${RESET}
  $(basename "$0") --all-disabled
  $(basename "$0") com.oculus.helpcenter com.oculus.explore
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

get_disabled_packages() {
    adb shell pm list packages -d 2>/dev/null | sed 's/^package://' | sort
}

enable_package() {
    local pkg="$1"
    local dry_run="$2"

    if [[ "$dry_run" == "true" ]]; then
        echo -e "  ${YELLOW}[dry-run]${RESET} Would re-enable: ${CYAN}${pkg}${RESET}"
        return 0
    fi

    echo -ne "  Enabling ${CYAN}${pkg}${RESET} ... "
    local output
    if output="$(adb shell pm enable "$pkg" 2>&1)"; then
        if echo "$output" | grep -qi "enabled"; then
            echo -e "${GREEN}OK${RESET}"
        elif echo "$output" | grep -qi "new state"; then
            echo -e "${GREEN}OK${RESET} (${output})"
        else
            echo -e "${YELLOW}Done${RESET} (${output})"
        fi
    else
        echo -e "${RED}FAILED${RESET}"
        echo -e "    ${RED}${output}${RESET}" >&2
        return 1
    fi
}

# --- Main ---
DRY_RUN="false"
MODE=""
PACKAGES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --all-disabled)
            MODE="all"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        -*)
            echo -e "${RED}Error: Unknown option: $1${RESET}" >&2
            usage >&2
            exit 1
            ;;
        *)
            PACKAGES+=("$1")
            shift
            ;;
    esac
done

validate_adb
validate_device

if [[ "$MODE" == "all" ]]; then
    echo -e "${BOLD}Querying disabled packages...${RESET}"
    mapfile -t PACKAGES < <(get_disabled_packages)

    if [[ ${#PACKAGES[@]} -eq 0 ]]; then
        echo -e "${GREEN}No disabled packages found. Nothing to do.${RESET}"
        exit 0
    fi

    echo -e "Found ${CYAN}${#PACKAGES[@]}${RESET} disabled package(s)."
    echo -e "${BOLD}Re-enabling all disabled packages...${RESET}"
elif [[ ${#PACKAGES[@]} -eq 0 ]]; then
    echo -e "${RED}Error: No packages specified. Use --all-disabled or provide package names.${RESET}" >&2
    usage >&2
    exit 1
else
    echo -e "${BOLD}Re-enabling specified packages...${RESET}"
fi

enabled_count=0
failed_count=0

for pkg in "${PACKAGES[@]}"; do
    if enable_package "$pkg" "$DRY_RUN"; then
        ((enabled_count++)) || true
    else
        ((failed_count++)) || true
    fi
done

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}Dry run complete. No changes were made.${RESET}"
else
    echo -e "${GREEN}${BOLD}Done.${RESET} Re-enabled ${enabled_count} package(s)."
    if [[ $failed_count -gt 0 ]]; then
        echo -e "${RED}${failed_count} package(s) could not be re-enabled.${RESET}"
    fi
fi
