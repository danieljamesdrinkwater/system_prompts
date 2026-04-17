#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# screenshot.sh - Quest 3 Screenshot Capture (runs from macOS via ADB)
# =============================================================================
# Captures a screenshot from Quest 3, pulls it to the local machine with a
# timestamped filename, cleans up the device, and optionally opens it.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

OUTPUT_DIR="."
NO_OPEN=false
NO_CLEANUP=false

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Quest 3 Screenshot Capture${RESET}

Captures a screenshot from the Quest 3 via ADB, pulls it to your local
machine with a timestamped filename, and optionally opens it.

Options:
  -o, --output <dir>   Save to this directory (default: current directory)
  --no-open            Do not auto-open the screenshot on macOS
  --no-cleanup         Do not delete the screenshot from the device
  -h, --help           Show this help message

Examples:
  $(basename "$0")                          # Capture and open
  $(basename "$0") -o ~/Screenshots         # Save to specific dir
  $(basename "$0") --no-open                # Capture without opening
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

take_screenshot() {
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local device_path="/sdcard/screenshot_${timestamp}.png"
    local local_filename="quest3_screenshot_${timestamp}.png"
    local local_path="${OUTPUT_DIR}/${local_filename}"

    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"

    echo -e "${BOLD}${CYAN}--- Quest 3 Screenshot ---${RESET}"
    echo ""

    # Step 1: Capture screenshot on device
    echo -e "  ${CYAN}[1/3]${RESET} Capturing screenshot on device..."
    if ! adb shell screencap "$device_path" 2>/dev/null; then
        echo -e "  ${RED}Error:${RESET} Failed to capture screenshot." >&2
        exit 1
    fi
    echo -e "  ${GREEN}Captured:${RESET} ${device_path}"

    # Step 2: Pull to local machine
    echo -e "  ${CYAN}[2/3]${RESET} Pulling to local machine..."
    if ! adb pull "$device_path" "$local_path" 2>/dev/null; then
        echo -e "  ${RED}Error:${RESET} Failed to pull screenshot." >&2
        echo -e "  ${DIM}Device file: ${device_path}${RESET}" >&2
        exit 1
    fi

    local file_size
    file_size=$(du -h "$local_path" | awk '{print $1}')
    echo -e "  ${GREEN}Saved:${RESET} ${local_path} (${file_size})"

    # Step 3: Cleanup device
    if ! $NO_CLEANUP; then
        echo -e "  ${CYAN}[3/3]${RESET} Cleaning up device..."
        if adb shell rm "$device_path" 2>/dev/null; then
            echo -e "  ${GREEN}Removed:${RESET} ${device_path} from device"
        else
            echo -e "  ${YELLOW}Warning:${RESET} Could not remove ${device_path} from device"
        fi
    else
        echo -e "  ${DIM}[3/3] Skipping device cleanup (--no-cleanup)${RESET}"
    fi

    echo ""

    # Open on macOS if available
    if ! $NO_OPEN; then
        if command -v open &>/dev/null; then
            echo -e "  ${DIM}Opening screenshot...${RESET}"
            open "$local_path"
        elif command -v xdg-open &>/dev/null; then
            echo -e "  ${DIM}Opening screenshot...${RESET}"
            xdg-open "$local_path" &>/dev/null &
        else
            echo -e "  ${DIM}No viewer found to auto-open the screenshot.${RESET}"
        fi
    fi

    echo -e "${BOLD}${CYAN}--------------------------${RESET}"
    echo -e "  ${BOLD}File:${RESET} ${local_path}"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            OUTPUT_DIR="${2:?--output requires a directory path}"
            shift 2
            ;;
        --no-open)
            NO_OPEN=true
            shift
            ;;
        --no-cleanup)
            NO_CLEANUP=true
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
take_screenshot
