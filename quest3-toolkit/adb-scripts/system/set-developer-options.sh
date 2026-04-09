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

Apply useful developer settings to a connected Quest 3 device.

${BOLD}Options:${RESET}
  --reset            Restore all developer settings to defaults
  --show-touches     Also enable "show touches" overlay
  --no-animations    Only disable animations (skip other settings)
  --help             Show this help message

${BOLD}Default behavior (no flags):${RESET}
  Applies all of:
    - Stay awake while charging
    - Disable window animation scale
    - Disable transition animation scale
    - Disable animator duration scale
    - Wi-Fi never sleeps

${BOLD}Examples:${RESET}
  $(basename "$0")                   # Apply all developer settings
  $(basename "$0") --show-touches    # Apply all + show touches
  $(basename "$0") --reset           # Restore defaults
  $(basename "$0") --no-animations   # Only disable animations
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

apply_setting() {
    local namespace="$1"
    local key="$2"
    local value="$3"
    local description="$4"

    echo -ne "  ${description} ... "
    if adb shell settings put "$namespace" "$key" "$value" 2>/dev/null; then
        echo -e "${GREEN}OK${RESET} (${CYAN}${namespace}/${key}=${value}${RESET})"
    else
        echo -e "${RED}FAILED${RESET}"
        return 1
    fi
}

apply_all_settings() {
    local show_touches="$1"
    local count=0

    echo -e "${BOLD}Applying developer settings...${RESET}"
    echo ""

    apply_setting "global" "stay_on_while_plugged_in" "3" \
        "Stay awake while charging (USB + AC + wireless)" && ((count++)) || true

    apply_setting "global" "window_animation_scale" "0.0" \
        "Disable window animation scale" && ((count++)) || true

    apply_setting "global" "transition_animation_scale" "0.0" \
        "Disable transition animation scale" && ((count++)) || true

    apply_setting "global" "animator_duration_scale" "0.0" \
        "Disable animator duration scale" && ((count++)) || true

    apply_setting "global" "wifi_sleep_policy" "2" \
        "Wi-Fi never sleeps" && ((count++)) || true

    if [[ "$show_touches" == "true" ]]; then
        apply_setting "system" "show_touches" "1" \
            "Enable show touches overlay" && ((count++)) || true
    fi

    echo ""
    echo -e "${GREEN}${BOLD}Done.${RESET} Applied ${count} setting(s)."
}

apply_animations_only() {
    local count=0

    echo -e "${BOLD}Disabling animations only...${RESET}"
    echo ""

    apply_setting "global" "window_animation_scale" "0.0" \
        "Disable window animation scale" && ((count++)) || true

    apply_setting "global" "transition_animation_scale" "0.0" \
        "Disable transition animation scale" && ((count++)) || true

    apply_setting "global" "animator_duration_scale" "0.0" \
        "Disable animator duration scale" && ((count++)) || true

    echo ""
    echo -e "${GREEN}${BOLD}Done.${RESET} Applied ${count} setting(s)."
}

reset_settings() {
    local count=0

    echo -e "${BOLD}Restoring developer settings to defaults...${RESET}"
    echo ""

    apply_setting "global" "stay_on_while_plugged_in" "0" \
        "Reset stay awake while charging" && ((count++)) || true

    apply_setting "global" "window_animation_scale" "1.0" \
        "Reset window animation scale" && ((count++)) || true

    apply_setting "global" "transition_animation_scale" "1.0" \
        "Reset transition animation scale" && ((count++)) || true

    apply_setting "global" "animator_duration_scale" "1.0" \
        "Reset animator duration scale" && ((count++)) || true

    apply_setting "global" "wifi_sleep_policy" "0" \
        "Reset Wi-Fi sleep policy" && ((count++)) || true

    apply_setting "system" "show_touches" "0" \
        "Disable show touches overlay" && ((count++)) || true

    echo ""
    echo -e "${GREEN}${BOLD}Done.${RESET} Reset ${count} setting(s) to defaults."
}

# --- Main ---
MODE="apply"
SHOW_TOUCHES="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --reset)
            MODE="reset"
            shift
            ;;
        --show-touches)
            SHOW_TOUCHES="true"
            shift
            ;;
        --no-animations)
            MODE="animations"
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

case "$MODE" in
    apply)
        apply_all_settings "$SHOW_TOUCHES"
        ;;
    reset)
        reset_settings
        ;;
    animations)
        apply_animations_only
        ;;
esac
