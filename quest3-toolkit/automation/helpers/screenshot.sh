#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# screenshot.sh - Capture Quest 3 screenshots via ADB
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

OUTPUT_DIR="."
OPEN_AFTER=false

usage() {
    cat <<EOF
${CYAN}Usage:${NC} $(basename "$0") [OPTIONS]

Capture a screenshot from Quest 3 via ADB.

Options:
  -o, --output <dir>   Save directory (default: current directory)
  --open               Open screenshot after capture (macOS only)
  -h, --help           Show this help

Examples:
  $(basename "$0")
  $(basename "$0") -o ~/Pictures --open
EOF
}

check_adb() {
    if ! command -v adb &>/dev/null; then
        echo -e "${RED}Error:${NC} ADB not found." >&2
        exit 1
    fi
    if ! adb get-state &>/dev/null 2>&1; then
        echo -e "${RED}Error:${NC} No device connected." >&2
        exit 1
    fi
}

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            OUTPUT_DIR="${2:?--output requires a directory}"
            shift 2
            ;;
        --open)
            OPEN_AFTER=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error:${NC} Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

check_adb

# Generate filename with timestamp
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
FILENAME="quest3_screenshot_${TIMESTAMP}.png"
DEVICE_PATH="/sdcard/screenshot_tmp.png"
LOCAL_PATH="${OUTPUT_DIR}/${FILENAME}"

mkdir -p "$OUTPUT_DIR"

echo -e "${CYAN}Capturing screenshot...${NC}"

# Capture on device
adb shell screencap -p "$DEVICE_PATH"

# Pull to local machine
adb pull "$DEVICE_PATH" "$LOCAL_PATH" 2>/dev/null

# Clean up on device
adb shell rm -f "$DEVICE_PATH"

echo -e "${GREEN}Saved:${NC} ${LOCAL_PATH}"

# Open on macOS if requested
if $OPEN_AFTER && command -v open &>/dev/null; then
    open "$LOCAL_PATH"
fi
