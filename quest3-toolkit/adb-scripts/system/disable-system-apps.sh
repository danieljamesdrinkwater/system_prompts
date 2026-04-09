#!/usr/bin/env bash
set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# --- Curated list of safe-to-disable Quest 3 bloatware ---
# These are non-critical packages that do not affect core VR functionality.
RECOMMENDED_PACKAGES=(
    "com.oculus.socialplatform"
    "com.oculus.helpcenter"
    "com.oculus.systemresource"
    "com.oculus.explore"
    "com.oculus.socialstore"
    "com.facebook.arvr.quillplayer"
    "com.oculus.firsttimenux"
    "com.oculus.vrshell.desktop"
)

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS] [PACKAGE ...]

Disable system apps on a connected Quest 3 device.

${BOLD}Options:${RESET}
  --recommended       Disable a curated list of safe-to-disable bloatware
  --list-candidates   List all packages that can potentially be disabled
  --dry-run           Show what would be disabled without making changes
  --help              Show this help message

${BOLD}Arguments:${RESET}
  PACKAGE ...         One or more package names to disable
                      (e.g. com.oculus.socialplatform)

${BOLD}Examples:${RESET}
  $(basename "$0") --recommended
  $(basename "$0") com.oculus.helpcenter com.oculus.explore
  $(basename "$0") --list-candidates
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

list_candidates() {
    echo -e "${CYAN}${BOLD}Packages that can potentially be disabled:${RESET}"
    echo -e "${YELLOW}(Use with caution -- disabling critical packages may cause instability)${RESET}"
    echo ""
    adb shell pm list packages -e | sed 's/^package://' | sort | while IFS= read -r pkg; do
        echo -e "  ${CYAN}${pkg}${RESET}"
    done
}

disable_package() {
    local pkg="$1"
    local dry_run="$2"

    if [[ "$dry_run" == "true" ]]; then
        echo -e "  ${YELLOW}[dry-run]${RESET} Would disable: ${CYAN}${pkg}${RESET}"
        return 0
    fi

    echo -ne "  Disabling ${CYAN}${pkg}${RESET} ... "
    local output
    if output="$(adb shell pm disable-user --user 0 "$pkg" 2>&1)"; then
        if echo "$output" | grep -qi "disabled"; then
            echo -e "${GREEN}OK${RESET}"
        elif echo "$output" | grep -qi "new state"; then
            echo -e "${GREEN}OK${RESET} (${output})"
        else
            echo -e "${YELLOW}Done${RESET} (${output})"
        fi
    else
        echo -e "${RED}FAILED${RESET}"
        echo -e "    ${RED}${output}${RESET}" >&2
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
        --recommended)
            MODE="recommended"
            shift
            ;;
        --list-candidates)
            MODE="list"
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

if [[ "$MODE" == "list" ]]; then
    list_candidates
    exit 0
fi

if [[ "$MODE" == "recommended" ]]; then
    PACKAGES=("${RECOMMENDED_PACKAGES[@]}")
    echo -e "${BOLD}Disabling recommended bloatware packages...${RESET}"
elif [[ ${#PACKAGES[@]} -eq 0 ]]; then
    echo -e "${RED}Error: No packages specified. Use --recommended or provide package names.${RESET}" >&2
    usage >&2
    exit 1
else
    echo -e "${BOLD}Disabling specified packages...${RESET}"
fi

disabled_count=0
failed_count=0

for pkg in "${PACKAGES[@]}"; do
    if disable_package "$pkg" "$DRY_RUN"; then
        ((disabled_count++)) || true
    else
        ((failed_count++)) || true
    fi
done

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}Dry run complete. No changes were made.${RESET}"
else
    echo -e "${GREEN}${BOLD}Done.${RESET} Processed ${disabled_count} package(s)."
    if [[ $failed_count -gt 0 ]]; then
        echo -e "${RED}${failed_count} package(s) could not be disabled (may be protected).${RESET}"
    fi
fi
