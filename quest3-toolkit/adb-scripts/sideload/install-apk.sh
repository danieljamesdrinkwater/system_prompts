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
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS] <APK_FILE> [APK_FILE ...]

Install one or more APK files to a connected Quest 3 device.

${BOLD}Options:${RESET}
  --downgrade, -d   Allow version downgrade (adds -d flag)
  --grant, -g       Grant all runtime permissions on install
  --help            Show this help message

${BOLD}Arguments:${RESET}
  APK_FILE          Path to one or more .apk files to install

${BOLD}Examples:${RESET}
  $(basename "$0") MyApp.apk
  $(basename "$0") game1.apk game2.apk game3.apk
  $(basename "$0") --grant --downgrade MyApp.apk
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
EXTRA_FLAGS=""
APK_FILES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --downgrade|-d)
            EXTRA_FLAGS="${EXTRA_FLAGS} -d"
            shift
            ;;
        --grant|-g)
            EXTRA_FLAGS="${EXTRA_FLAGS} -g"
            shift
            ;;
        -*)
            echo -e "${RED}Error: Unknown option: $1${RESET}" >&2
            usage >&2
            exit 1
            ;;
        *)
            APK_FILES+=("$1")
            shift
            ;;
    esac
done

if [[ ${#APK_FILES[@]} -eq 0 ]]; then
    echo -e "${RED}Error: No APK files specified.${RESET}" >&2
    usage >&2
    exit 1
fi

# Validate all APK files before starting installation
echo -e "${BOLD}Validating APK files...${RESET}"
validation_failed="false"
for apk in "${APK_FILES[@]}"; do
    if [[ ! -f "$apk" ]]; then
        echo -e "  ${RED}Not found:${RESET} ${apk}"
        validation_failed="true"
    elif [[ "${apk,,}" != *.apk ]]; then
        echo -e "  ${RED}Not an APK:${RESET} ${apk}"
        validation_failed="true"
    else
        local_size="$(du -h "$apk" 2>/dev/null | cut -f1 || echo "?")"
        echo -e "  ${GREEN}OK${RESET} ${CYAN}${apk}${RESET} (${local_size})"
    fi
done

if [[ "$validation_failed" == "true" ]]; then
    echo -e "\n${RED}Validation failed. Fix the above issues and try again.${RESET}" >&2
    exit 1
fi

validate_adb
validate_device

echo ""
echo -e "${BOLD}Installing APKs...${RESET}"
echo ""

success_count=0
fail_count=0

for apk in "${APK_FILES[@]}"; do
    basename_apk="$(basename "$apk")"
    echo -ne "  Installing ${CYAN}${basename_apk}${RESET} ... "

    # shellcheck disable=SC2086
    if output="$(adb install -r ${EXTRA_FLAGS} "$apk" 2>&1)"; then
        if echo "$output" | grep -qi "success"; then
            echo -e "${GREEN}SUCCESS${RESET}"
            ((success_count++)) || true
        else
            echo -e "${YELLOW}Done${RESET} (${output})"
            ((success_count++)) || true
        fi
    else
        echo -e "${RED}FAILED${RESET}"
        # Extract the failure reason from ADB output
        failure_reason="$(echo "$output" | grep -i "failure\|error" | head -1 || echo "$output")"
        echo -e "    ${RED}${failure_reason}${RESET}" >&2
        ((fail_count++)) || true
    fi
done

echo ""
echo -e "${BOLD}Installation summary:${RESET}"
echo -e "  ${GREEN}Succeeded: ${success_count}${RESET}"
if [[ $fail_count -gt 0 ]]; then
    echo -e "  ${RED}Failed:    ${fail_count}${RESET}"
fi
echo -e "  Total:    ${#APK_FILES[@]}"
