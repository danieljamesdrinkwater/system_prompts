#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# process-monitor.sh - Quest 3 Process Monitor (runs from macOS via ADB)
# =============================================================================
# Shows top processes by CPU/memory usage on the Quest 3 device.
# Supports filtering by name and limiting the number of results.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

TOP_N=10
FILTER=""
SORT_BY="cpu"  # cpu or mem
WATCH_MODE=false
POLL_INTERVAL=5

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Quest 3 Process Monitor${RESET}

Options:
  --top N              Show top N processes (default: 10)
  --filter <name>      Filter by process name (substring match)
  --sort cpu|mem       Sort by CPU or memory (default: cpu)
  --watch [N]          Poll every N seconds (default: 5)
  -h, --help           Show this help message

Examples:
  $(basename "$0")                          # Top 10 by CPU
  $(basename "$0") --top 20 --sort mem      # Top 20 by memory
  $(basename "$0") --filter oculus          # Filter for Oculus processes
  $(basename "$0") --watch 3               # Watch mode, 3s interval
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

print_process_report() {
    local top_output
    top_output=$(adb shell top -bn1 -o "%CPU,%MEM,PID,NAME" 2>/dev/null || true)

    if [[ -z "$top_output" ]]; then
        # Fallback: use ps if top fails
        echo -e "${DIM}(top unavailable, falling back to ps)${RESET}"
        local ps_output
        ps_output=$(adb shell ps -A -o PID,USER,%CPU,%MEM,NAME 2>/dev/null || \
                    adb shell ps -A 2>/dev/null)

        if [[ -z "$ps_output" ]]; then
            echo -e "${RED}Error:${RESET} Failed to read process data." >&2
            return 1
        fi

        local timestamp
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')

        echo -e "${DIM}${timestamp}${RESET}"
        echo -e "${BOLD}${CYAN}--- Quest 3 Process List (ps) ---${RESET}"
        echo ""

        if [[ -n "$FILTER" ]]; then
            echo -e "  ${DIM}Filter: ${FILTER}${RESET}"
            echo "$ps_output" | head -1
            echo "$ps_output" | tail -n +2 | grep -i "$FILTER" | head -"$TOP_N"
        else
            echo "$ps_output" | head -$(( TOP_N + 1 ))
        fi
        return
    fi

    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Clear screen in watch mode for clean updates
    if $WATCH_MODE; then
        printf '\033[2J\033[H'
    fi

    echo -e "${DIM}${timestamp}${RESET}"
    echo -e "${BOLD}${CYAN}--- Quest 3 Process Monitor ---${RESET}"

    if [[ -n "$FILTER" ]]; then
        echo -e "  ${DIM}Filter: \"${FILTER}\"${RESET}"
    fi
    echo -e "  ${DIM}Showing top ${TOP_N} by ${SORT_BY}${RESET}"
    echo ""

    # Parse top output - extract the process table portion
    # top output has a header section then a table
    local table_started=false
    local header_line=""
    local lines=()

    while IFS= read -r line; do
        # Look for the PID header line that starts the process table
        if [[ "$line" =~ ^[[:space:]]*PID ]] || [[ "$line" =~ ^[[:space:]]*%CPU ]]; then
            table_started=true
            header_line="$line"
            continue
        fi
        if $table_started && [[ -n "$line" ]]; then
            # Apply filter if set
            if [[ -n "$FILTER" ]]; then
                if echo "$line" | grep -qi "$FILTER"; then
                    lines+=("$line")
                fi
            else
                lines+=("$line")
            fi
        fi
    done <<< "$top_output"

    # Print formatted table header
    printf "  ${BOLD}%-8s  %-6s  %-6s  %s${RESET}\n" "PID" "%CPU" "%MEM" "PROCESS"
    echo -e "  ${DIM}$(printf '%.0s-' {1..60})${RESET}"

    # Sort and display
    local sort_col
    if [[ "$SORT_BY" == "mem" ]]; then
        sort_col=2
    else
        sort_col=1
    fi

    local count=0
    # Re-parse lines to extract fields and sort
    (
        for line in "${lines[@]}"; do
            # Attempt to parse: PID USER ... %CPU %MEM ... NAME
            # top output format varies; try to extract key fields
            local pid cpu mem name
            pid=$(echo "$line" | awk '{print $1}')
            # Try to find CPU and MEM percentages
            cpu=$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.?[0-9]*$/ && i>1) {print $i; exit}}')
            mem=$(echo "$line" | awk '{n=0; for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.?[0-9]*$/ && i>1) {n++; if(n==2){print $i; exit}}}')
            name=$(echo "$line" | awk '{print $NF}')

            if [[ -n "$pid" && -n "$name" ]]; then
                printf "%s\t%s\t%s\t%s\n" "${cpu:-0}" "${mem:-0}" "$pid" "$name"
            fi
        done
    ) | sort -t$'\t' -k"$sort_col" -rn | head -"$TOP_N" | while IFS=$'\t' read -r cpu mem pid name; do
        # Colorize high CPU/mem
        local cpu_color="$RESET" mem_color="$RESET"
        local cpu_int="${cpu%%.*}"
        local mem_int="${mem%%.*}"

        if (( cpu_int >= 50 )); then
            cpu_color="$RED"
        elif (( cpu_int >= 20 )); then
            cpu_color="$YELLOW"
        fi

        if (( mem_int >= 20 )); then
            mem_color="$RED"
        elif (( mem_int >= 10 )); then
            mem_color="$YELLOW"
        fi

        printf "  %-8s  ${cpu_color}%5s%%${RESET}  ${mem_color}%5s%%${RESET}  %s\n" \
            "$pid" "$cpu" "$mem" "$name"
    done

    echo ""
    echo -e "${BOLD}${CYAN}--------------------------------${RESET}"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --top)
            TOP_N="${2:?--top requires a number}"
            shift 2
            ;;
        --filter)
            FILTER="${2:?--filter requires a name}"
            shift 2
            ;;
        --sort)
            SORT_BY="${2:?--sort requires cpu or mem}"
            if [[ "$SORT_BY" != "cpu" && "$SORT_BY" != "mem" ]]; then
                echo -e "${RED}Error:${RESET} --sort must be 'cpu' or 'mem'" >&2
                exit 1
            fi
            shift 2
            ;;
        --watch)
            WATCH_MODE=true
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
                POLL_INTERVAL="$2"
                shift
            fi
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

if $WATCH_MODE; then
    echo -e "${BOLD}Watching processes every ${POLL_INTERVAL}s${RESET} (Ctrl+C to stop)"
    while true; do
        print_process_report
        sleep "$POLL_INTERVAL"
    done
else
    print_process_report
fi
