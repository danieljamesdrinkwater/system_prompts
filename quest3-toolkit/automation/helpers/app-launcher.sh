#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# app-launcher.sh - Quest 3 App Launcher (runs from macOS via ADB)
# =============================================================================
# Launch apps on Quest 3 by package name. Includes common shortcuts for
# browser, settings, and Termux. Can list launchable activities.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

PACKAGE=""
ACTIVITY=""
LIST_MODE=false

# Common Quest 3 shortcuts
declare -A SHORTCUTS=(
    [browser]="com.oculus.browser"
    [settings]="com.android.settings"
    [termux]="com.termux"
    [files]="com.oculus.filemanager"
    [home]="com.oculus.shellenv"
    [store]="com.oculus.store"
    [tv]="com.oculus.tv"
    [explore]="com.oculus.explore"
)

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS] [PACKAGE]

${BOLD}Quest 3 App Launcher${RESET}

Arguments:
  PACKAGE                Package name to launch (e.g., com.example.app)

Options:
  --list                 List launchable activities for the package
  --activity <name>      Specify exact activity to launch
  --browser              Launch Oculus Browser
  --settings             Launch Android Settings
  --termux               Launch Termux
  --files                Launch File Manager
  --home                 Launch Quest Home
  --store                Launch Meta Store
  --shortcuts            Show all available shortcuts
  -h, --help             Show this help message

Examples:
  $(basename "$0") com.example.myapp          # Launch app
  $(basename "$0") --browser                   # Launch browser
  $(basename "$0") --list com.termux           # List Termux activities
  $(basename "$0") com.example.app --activity .MainActivity
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

show_shortcuts() {
    echo -e "${BOLD}${CYAN}Available Shortcuts:${RESET}"
    echo ""
    for key in $(echo "${!SHORTCUTS[@]}" | tr ' ' '\n' | sort); do
        printf "  ${BOLD}--%-12s${RESET} %s\n" "$key" "${SHORTCUTS[$key]}"
    done
    echo ""
}

get_launch_activity() {
    local pkg="$1"

    # Get the main launcher activity via resolve-activity
    local activity
    activity=$(adb shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "$pkg" 2>/dev/null | tail -1 | tr -d '\r')

    if [[ -n "$activity" && "$activity" != *"No activity"* && "$activity" =~ / ]]; then
        echo "$activity"
        return
    fi

    # Fallback: parse dumpsys package for MAIN/LAUNCHER
    activity=$(adb shell dumpsys package "$pkg" 2>/dev/null | \
        grep -A 5 "android.intent.action.MAIN" | \
        grep -B 1 "android.intent.category.LAUNCHER" | \
        grep "$pkg" | \
        head -1 | \
        awk '{print $2}' | \
        tr -d '\r')

    echo "$activity"
}

list_activities() {
    local pkg="$1"

    echo -e "${BOLD}${CYAN}Activities for ${pkg}:${RESET}"
    echo ""

    # Check package exists
    if ! adb shell pm path "$pkg" &>/dev/null; then
        echo -e "  ${RED}Error:${RESET} Package '${pkg}' not found on device."
        exit 1
    fi

    # Get all activities from the package
    local activities
    activities=$(adb shell dumpsys package "$pkg" 2>/dev/null | \
        grep -E "^\s+[a-f0-9]+ ${pkg}" | \
        awk '{print $2}' | \
        tr -d '\r' | \
        sort -u)

    if [[ -z "$activities" ]]; then
        # Alternate parsing: look for component lines
        activities=$(adb shell dumpsys package "$pkg" 2>/dev/null | \
            grep -oE "${pkg}/[A-Za-z._]+" | \
            sort -u)
    fi

    if [[ -z "$activities" ]]; then
        echo -e "  ${YELLOW}No activities found.${RESET}"
        echo -e "  ${DIM}The package may use a non-standard activity naming.${RESET}"
    else
        # Highlight the launcher activity
        local launcher
        launcher=$(get_launch_activity "$pkg")

        while IFS= read -r act; do
            if [[ "$act" == "$launcher" ]]; then
                echo -e "  ${GREEN}${act}${RESET} ${BOLD}(launcher)${RESET}"
            else
                echo -e "  ${DIM}${act}${RESET}"
            fi
        done <<< "$activities"
    fi

    echo ""
}

launch_app() {
    local pkg="$1"
    local activity="${2:-}"

    # Check package exists
    if ! adb shell pm path "$pkg" &>/dev/null; then
        echo -e "${RED}Error:${RESET} Package '${pkg}' not found on device." >&2
        echo -e "${DIM}Check the package name or install the app first.${RESET}" >&2
        exit 1
    fi

    if [[ -n "$activity" ]]; then
        # If activity doesn't contain a slash, prefix with package
        if [[ "$activity" != */* ]]; then
            activity="${pkg}/${activity}"
        fi
        echo -e "${CYAN}Launching:${RESET} ${BOLD}${activity}${RESET}"
        local result
        result=$(adb shell am start -n "$activity" 2>&1)

        if echo "$result" | grep -qi "error\|exception"; then
            echo -e "${RED}Failed:${RESET} ${result}" >&2
            exit 1
        else
            echo -e "${GREEN}Launched successfully.${RESET}"
            echo -e "${DIM}${result}${RESET}"
        fi
    else
        # Auto-discover launch activity
        echo -e "${DIM}Discovering launch activity for ${pkg}...${RESET}"
        local discovered
        discovered=$(get_launch_activity "$pkg")

        if [[ -n "$discovered" && "$discovered" =~ / ]]; then
            echo -e "${CYAN}Launching:${RESET} ${BOLD}${discovered}${RESET}"
            local result
            result=$(adb shell am start -n "$discovered" 2>&1)

            if echo "$result" | grep -qi "error\|exception"; then
                echo -e "${RED}Failed:${RESET} ${result}" >&2
                exit 1
            else
                echo -e "${GREEN}Launched successfully.${RESET}"
                echo -e "${DIM}${result}${RESET}"
            fi
        else
            # Fallback: use monkey to launch
            echo -e "${DIM}No specific activity found, using monkey launcher...${RESET}"
            local result
            result=$(adb shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 2>&1)

            if echo "$result" | grep -q "Events injected: 1"; then
                echo -e "${GREEN}Launched ${pkg} successfully.${RESET}"
            else
                echo -e "${RED}Failed to launch ${pkg}.${RESET}" >&2
                echo -e "${DIM}${result}${RESET}" >&2
                exit 1
            fi
        fi
    fi
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            LIST_MODE=true
            shift
            ;;
        --activity)
            ACTIVITY="${2:?--activity requires an activity name}"
            shift 2
            ;;
        --shortcuts)
            show_shortcuts
            exit 0
            ;;
        --browser|--settings|--termux|--files|--home|--store|--tv|--explore)
            local_key="${1#--}"
            PACKAGE="${SHORTCUTS[$local_key]}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Error:${RESET} Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            PACKAGE="$1"
            shift
            ;;
    esac
done

if [[ -z "$PACKAGE" ]]; then
    echo -e "${RED}Error:${RESET} No package specified." >&2
    echo ""
    usage >&2
    exit 1
fi

# --- Main ---
check_prerequisites

if $LIST_MODE; then
    list_activities "$PACKAGE"
else
    launch_app "$PACKAGE" "$ACTIVITY"
fi
