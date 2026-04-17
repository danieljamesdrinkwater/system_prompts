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
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

List packages on a connected Quest 3 device.

${BOLD}Options:${RESET}
  -3, --sideloaded     Show only sideloaded (third-party) packages
  -s, --system         Show only system packages
  --disabled           Show only disabled packages
  --filter <keyword>   Filter results by keyword (case-insensitive)
  --count              Show package count instead of listing
  --help               Show this help message

${BOLD}Examples:${RESET}
  $(basename "$0")                        # List all packages
  $(basename "$0") -3                     # List sideloaded apps
  $(basename "$0") -s --filter oculus     # System packages matching "oculus"
  $(basename "$0") --disabled             # Show disabled packages
  $(basename "$0") -3 --count             # Count sideloaded apps
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

# --- Main ---
PM_FLAGS=""
FILTER=""
SHOW_COUNT="false"
LABEL="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        -3|--sideloaded)
            PM_FLAGS="${PM_FLAGS} -3"
            LABEL="sideloaded (third-party)"
            shift
            ;;
        -s|--system)
            PM_FLAGS="${PM_FLAGS} -s"
            LABEL="system"
            shift
            ;;
        --disabled)
            PM_FLAGS="${PM_FLAGS} -d"
            LABEL="disabled"
            shift
            ;;
        --filter)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}Error: --filter requires a keyword argument.${RESET}" >&2
                exit 1
            fi
            FILTER="$2"
            shift 2
            ;;
        --count)
            SHOW_COUNT="true"
            shift
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

validate_adb
validate_device

echo -e "${BOLD}Listing ${LABEL} packages...${RESET}"
if [[ -n "$FILTER" ]]; then
    echo -e "${YELLOW}Filter: ${FILTER}${RESET}"
fi
echo ""

# Build and execute the command
# shellcheck disable=SC2086
output="$(adb shell pm list packages ${PM_FLAGS} 2>/dev/null | sed 's/^package://' | sort)"

# Apply filter if specified
if [[ -n "$FILTER" ]]; then
    output="$(echo "$output" | grep -i "$FILTER" || true)"
fi

if [[ -z "$output" ]]; then
    echo -e "${YELLOW}No packages found matching the criteria.${RESET}"
    exit 0
fi

if [[ "$SHOW_COUNT" == "true" ]]; then
    count="$(echo "$output" | wc -l | tr -d ' ')"
    echo -e "${CYAN}${BOLD}${count}${RESET} ${LABEL} package(s) found."
else
    pkg_count=0
    while IFS= read -r pkg; do
        [[ -z "$pkg" ]] && continue
        echo -e "  ${CYAN}${pkg}${RESET}"
        ((pkg_count++)) || true
    done <<< "$output"
    echo ""
    echo -e "${GREEN}${BOLD}Total: ${pkg_count} package(s).${RESET}"
fi
