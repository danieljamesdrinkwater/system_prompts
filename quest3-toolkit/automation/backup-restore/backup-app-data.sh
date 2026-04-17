#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# backup-app-data.sh - Quest 3 App Data Backup (runs from macOS via ADB)
# =============================================================================
# Backs up app data for a single package or all sideloaded apps.
# Saves timestamped backups to ./quest3-backups/
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

PACKAGE=""
ALL_SIDELOADED=false
BACKUP_DIR="./quest3-backups"

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Quest 3 App Data Backup${RESET}

Options:
  --package <name>       Backup a single package (e.g., com.example.app)
  --all-sideloaded       Backup all sideloaded (third-party) apps
  --output <dir>         Output directory (default: ./quest3-backups/)
  -h, --help             Show this help message

Examples:
  $(basename "$0") --package com.example.myapp
  $(basename "$0") --all-sideloaded
  $(basename "$0") --all-sideloaded --output ~/my-backups
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

get_sideloaded_packages() {
    # Third-party packages (not system)
    adb shell pm list packages -3 2>/dev/null | sed 's/package://' | tr -d '\r' | sort
}

backup_single_package() {
    local pkg="$1"
    local backup_subdir="$2"
    local backup_file="${backup_subdir}/${pkg}.ab"

    echo -e "  ${CYAN}Backing up:${RESET} ${pkg}"

    # Check if package exists
    if ! adb shell pm path "$pkg" &>/dev/null; then
        echo -e "  ${YELLOW}Warning:${RESET} Package '$pkg' not found on device, skipping."
        return 1
    fi

    # Try adb backup
    echo -e "  ${DIM}Running adb backup (you may need to confirm on device)...${RESET}"
    if adb backup -f "$backup_file" -noapk "$pkg" 2>/dev/null; then
        # Check if backup file is meaningful (> 50 bytes, not just a header)
        local fsize
        fsize=$(wc -c < "$backup_file" 2>/dev/null || echo "0")
        if (( fsize > 50 )); then
            echo -e "  ${GREEN}Saved:${RESET} ${backup_file} ($(du -h "$backup_file" | awk '{print $1}'))"
        else
            echo -e "  ${YELLOW}Warning:${RESET} Backup may be empty (app may not allow backup)."
            echo -e "  ${DIM}Attempting APK pull as fallback...${RESET}"
            pull_apk "$pkg" "$backup_subdir"
        fi
    else
        echo -e "  ${YELLOW}Warning:${RESET} adb backup failed for ${pkg}."
        echo -e "  ${DIM}Attempting APK pull as fallback...${RESET}"
        pull_apk "$pkg" "$backup_subdir"
    fi

    # Also save package info
    adb shell dumpsys package "$pkg" > "${backup_subdir}/${pkg}.info.txt" 2>/dev/null || true
}

pull_apk() {
    local pkg="$1"
    local dest_dir="$2"

    local apk_path
    apk_path=$(adb shell pm path "$pkg" 2>/dev/null | head -1 | sed 's/package://' | tr -d '\r')
    if [[ -n "$apk_path" ]]; then
        local apk_dest="${dest_dir}/${pkg}.apk"
        if adb pull "$apk_path" "$apk_dest" &>/dev/null; then
            echo -e "  ${GREEN}APK saved:${RESET} ${apk_dest}"
        else
            echo -e "  ${RED}Failed:${RESET} Could not pull APK for ${pkg}"
        fi
    fi
}

run_backup() {
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_subdir="${BACKUP_DIR}/${timestamp}"

    mkdir -p "$backup_subdir"

    echo -e "${BOLD}${CYAN}--- Quest 3 App Data Backup ---${RESET}"
    echo -e "${DIM}$(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "  Backup directory: ${BOLD}${backup_subdir}${RESET}"
    echo ""

    local packages=()

    if [[ -n "$PACKAGE" ]]; then
        packages=("$PACKAGE")
    elif $ALL_SIDELOADED; then
        echo -e "  ${DIM}Discovering sideloaded packages...${RESET}"
        while IFS= read -r pkg; do
            [[ -n "$pkg" ]] && packages+=("$pkg")
        done < <(get_sideloaded_packages)

        if [[ ${#packages[@]} -eq 0 ]]; then
            echo -e "${YELLOW}No sideloaded packages found.${RESET}"
            exit 0
        fi

        echo -e "  Found ${BOLD}${#packages[@]}${RESET} sideloaded packages"
        echo ""
    fi

    # Save the package list
    printf '%s\n' "${packages[@]}" > "${backup_subdir}/package-list.txt"

    local success=0 failed=0
    for pkg in "${packages[@]}"; do
        if backup_single_package "$pkg" "$backup_subdir"; then
            ((success++)) || true
        else
            ((failed++)) || true
        fi
        echo ""
    done

    # Write manifest
    cat > "${backup_subdir}/manifest.txt" <<MANIFEST
Quest 3 Backup Manifest
========================
Date:      $(date '+%Y-%m-%d %H:%M:%S')
Device:    $(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r')
Serial:    $(adb get-serialno 2>/dev/null | tr -d '\r')
Packages:  ${#packages[@]}
Succeeded: ${success}
Failed:    ${failed}
MANIFEST

    echo -e "${BOLD}${CYAN}--- Backup Complete ---${RESET}"
    echo -e "  ${GREEN}Success:${RESET} ${success}  ${RED}Failed:${RESET} ${failed}"
    echo -e "  ${BOLD}Location:${RESET} ${backup_subdir}"
    echo -e "  ${DIM}Manifest:${RESET} ${backup_subdir}/manifest.txt"
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --package)
            PACKAGE="${2:?--package requires a package name}"
            shift 2
            ;;
        --all-sideloaded)
            ALL_SIDELOADED=true
            shift
            ;;
        --output)
            BACKUP_DIR="${2:?--output requires a directory path}"
            shift 2
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

if [[ -z "$PACKAGE" ]] && ! $ALL_SIDELOADED; then
    echo -e "${RED}Error:${RESET} Specify --package <name> or --all-sideloaded" >&2
    usage >&2
    exit 1
fi

# --- Main ---
check_prerequisites
run_backup
