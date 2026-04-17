#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# storage-monitor.sh - Quest 3 Storage Monitor (runs from macOS via ADB)
# =============================================================================
# Shows storage usage for main Quest 3 partitions via "adb shell df -h".
# Highlights /data (apps/games) and /sdcard (shared storage) usage.
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

${BOLD}Quest 3 Storage Monitor${RESET}

Options:
  --all          Show all mounted partitions (not just key ones)
  -h, --help     Show this help message

Examples:
  $(basename "$0")          # Show key partition summary
  $(basename "$0") --all    # Show all partitions
EOF
}

SHOW_ALL=false

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

usage_bar() {
    local percent=$1
    local width=25
    # Strip the % sign if present
    percent="${percent//%/}"
    # Handle non-numeric gracefully
    if ! [[ "$percent" =~ ^[0-9]+$ ]]; then
        printf "[%-${width}s]" "?"
        return
    fi

    local filled=$(( percent * width / 100 ))
    local empty=$(( width - filled ))
    local color="$GREEN"

    if (( percent >= 90 )); then
        color="$RED"
    elif (( percent >= 70 )); then
        color="$YELLOW"
    fi

    printf "${color}["
    printf '%0.s#' $(seq 1 "$filled" 2>/dev/null) || true
    printf '%0.s-' $(seq 1 "$empty" 2>/dev/null) || true
    printf "]${RESET}"
}

print_partition_row() {
    local mount="$1" size="$2" used="$3" avail="$4" pct="$5"
    local pct_num="${pct//%/}"

    printf "  %-20s " "$mount"
    usage_bar "$pct_num"
    printf "  %5s  %6s / %6s  (%s)\n" "$pct" "$used" "$size" "$avail free"
}

print_storage_report() {
    local df_output
    df_output=$(adb shell df -h 2>/dev/null)

    if [[ -z "$df_output" ]]; then
        echo -e "${RED}Error:${RESET} Failed to read storage data." >&2
        return 1
    fi

    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo -e "${DIM}${timestamp}${RESET}"
    echo -e "${BOLD}${CYAN}--- Quest 3 Storage Report ---${RESET}"
    echo ""

    # Key partitions to highlight
    local key_partitions=("/data" "/sdcard" "/storage/emulated" "/system" "/vendor" "/product")

    echo -e "${BOLD}  Partition              Usage                       Pct    Used / Total   (Free)${RESET}"
    echo -e "  ${DIM}$(printf '%.0s-' {1..80})${RESET}"

    local data_line="" sdcard_line=""
    local found_data=false found_sdcard=false

    # Parse /data
    data_line=$(echo "$df_output" | awk '$NF == "/data" {print $0}' | head -1)
    if [[ -n "$data_line" ]]; then
        found_data=true
        local d_size d_used d_avail d_pct
        d_size=$(echo "$data_line" | awk '{print $2}')
        d_used=$(echo "$data_line" | awk '{print $3}')
        d_avail=$(echo "$data_line" | awk '{print $4}')
        d_pct=$(echo "$data_line" | awk '{print $5}')
        echo -e "${BOLD}"
        print_partition_row "/data (apps/games)" "$d_size" "$d_used" "$d_avail" "$d_pct"
        echo -e "${RESET}"
    fi

    # Parse /sdcard or /storage/emulated
    sdcard_line=$(echo "$df_output" | awk '$NF ~ /\/sdcard$|\/storage\/emulated$|\/storage\/emulated\/0$/ {print $0}' | head -1)
    if [[ -n "$sdcard_line" ]]; then
        found_sdcard=true
        local s_size s_used s_avail s_pct
        s_size=$(echo "$sdcard_line" | awk '{print $2}')
        s_used=$(echo "$sdcard_line" | awk '{print $3}')
        s_avail=$(echo "$sdcard_line" | awk '{print $4}')
        s_pct=$(echo "$sdcard_line" | awk '{print $5}')
        echo -e "${BOLD}"
        print_partition_row "/sdcard (shared)" "$s_size" "$s_used" "$s_avail" "$s_pct"
        echo -e "${RESET}"
    fi

    if $found_data || $found_sdcard; then
        echo ""
    fi

    if $SHOW_ALL; then
        echo -e "  ${BOLD}All Partitions:${RESET}"
        echo -e "  ${DIM}$(printf '%.0s-' {1..80})${RESET}"
        # Skip header line and tmpfs/proc/devpts mounts
        echo "$df_output" | tail -n +2 | grep -v -E '^\s*$' | while IFS= read -r line; do
            local mount size used avail pct
            mount=$(echo "$line" | awk '{print $NF}')
            size=$(echo "$line" | awk '{print $2}')
            used=$(echo "$line" | awk '{print $3}')
            avail=$(echo "$line" | awk '{print $4}')
            pct=$(echo "$line" | awk '{print $5}')
            print_partition_row "$mount" "$size" "$used" "$avail" "$pct"
        done
        echo ""
    else
        # Show other notable partitions
        echo -e "  ${DIM}Other partitions:${RESET}"
        for part in "/system" "/vendor" "/product"; do
            local pline
            pline=$(echo "$df_output" | awk -v p="$part" '$NF == p {print $0}' | head -1)
            if [[ -n "$pline" ]]; then
                local p_size p_used p_avail p_pct
                p_size=$(echo "$pline" | awk '{print $2}')
                p_used=$(echo "$pline" | awk '{print $3}')
                p_avail=$(echo "$pline" | awk '{print $4}')
                p_pct=$(echo "$pline" | awk '{print $5}')
                print_partition_row "$part" "$p_size" "$p_used" "$p_avail" "$p_pct"
            fi
        done
    fi

    echo ""
    echo -e "${BOLD}${CYAN}------------------------------${RESET}"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            SHOW_ALL=true
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
print_storage_report
