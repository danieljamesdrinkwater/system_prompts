#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# restore-app-data.sh - Quest 3 App Data Restore (runs from macOS via ADB)
# =============================================================================
# Restores app data from a backup created by backup-app-data.sh.
# Accepts a backup directory path as argument.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

BACKUP_PATH=""
PACKAGE=""
DRY_RUN=false

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") <backup-path> [OPTIONS]

${BOLD}Quest 3 App Data Restore${RESET}

Arguments:
  <backup-path>          Path to backup directory (created by backup-app-data.sh)

Options:
  --package <name>       Restore only a specific package from the backup
  --dry-run              Show what would be restored without doing it
  -h, --help             Show this help message

Examples:
  $(basename "$0") ./quest3-backups/20250115_143022
  $(basename "$0") ./quest3-backups/20250115_143022 --package com.example.app
  $(basename "$0") ./quest3-backups/20250115_143022 --dry-run
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

restore_ab_file() {
    local ab_file="$1"
    local pkg_name
    pkg_name=$(basename "$ab_file" .ab)

    echo -e "  ${CYAN}Restoring:${RESET} ${pkg_name}"

    local fsize
    fsize=$(wc -c < "$ab_file" 2>/dev/null || echo "0")
    if (( fsize <= 50 )); then
        echo -e "  ${YELLOW}Warning:${RESET} Backup file appears empty, skipping."
        return 1
    fi

    if $DRY_RUN; then
        echo -e "  ${DIM}[dry-run] Would restore: ${ab_file} ($(du -h "$ab_file" | awk '{print $1}'))${RESET}"
        return 0
    fi

    echo -e "  ${DIM}Running adb restore (you may need to confirm on device)...${RESET}"
    if adb restore "$ab_file" 2>/dev/null; then
        echo -e "  ${GREEN}Restored:${RESET} ${pkg_name}"
    else
        echo -e "  ${RED}Failed:${RESET} adb restore failed for ${pkg_name}"
        return 1
    fi
}

install_apk_file() {
    local apk_file="$1"
    local pkg_name
    pkg_name=$(basename "$apk_file" .apk)

    echo -e "  ${CYAN}Installing APK:${RESET} ${pkg_name}"

    if $DRY_RUN; then
        echo -e "  ${DIM}[dry-run] Would install: ${apk_file} ($(du -h "$apk_file" | awk '{print $1}'))${RESET}"
        return 0
    fi

    if adb install -r "$apk_file" 2>/dev/null; then
        echo -e "  ${GREEN}Installed:${RESET} ${pkg_name}"
    else
        echo -e "  ${RED}Failed:${RESET} Could not install ${pkg_name}"
        return 1
    fi
}

run_restore() {
    echo -e "${BOLD}${CYAN}--- Quest 3 App Data Restore ---${RESET}"
    echo -e "${DIM}$(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "  Backup path: ${BOLD}${BACKUP_PATH}${RESET}"

    if $DRY_RUN; then
        echo -e "  ${YELLOW}DRY RUN MODE${RESET} - no changes will be made"
    fi
    echo ""

    # Show manifest if present
    if [[ -f "${BACKUP_PATH}/manifest.txt" ]]; then
        echo -e "  ${DIM}--- Manifest ---${RESET}"
        while IFS= read -r line; do
            echo -e "  ${DIM}${line}${RESET}"
        done < "${BACKUP_PATH}/manifest.txt"
        echo ""
    fi

    local success=0 failed=0 total=0

    if [[ -n "$PACKAGE" ]]; then
        # Restore a specific package
        ((total++)) || true
        if [[ -f "${BACKUP_PATH}/${PACKAGE}.ab" ]]; then
            if restore_ab_file "${BACKUP_PATH}/${PACKAGE}.ab"; then
                ((success++)) || true
            else
                ((failed++)) || true
            fi
        elif [[ -f "${BACKUP_PATH}/${PACKAGE}.apk" ]]; then
            if install_apk_file "${BACKUP_PATH}/${PACKAGE}.apk"; then
                ((success++)) || true
            else
                ((failed++)) || true
            fi
        else
            echo -e "  ${RED}Error:${RESET} No backup found for '${PACKAGE}' in ${BACKUP_PATH}"
            exit 1
        fi
    else
        # Restore all .ab files
        for ab_file in "${BACKUP_PATH}"/*.ab; do
            [[ -f "$ab_file" ]] || continue
            ((total++)) || true
            echo ""
            if restore_ab_file "$ab_file"; then
                ((success++)) || true
            else
                ((failed++)) || true
            fi
        done

        # Install any standalone APKs (no corresponding .ab)
        for apk_file in "${BACKUP_PATH}"/*.apk; do
            [[ -f "$apk_file" ]] || continue
            local base
            base=$(basename "$apk_file" .apk)
            # Skip if we already restored the .ab for this package
            [[ -f "${BACKUP_PATH}/${base}.ab" ]] && continue
            ((total++)) || true
            echo ""
            if install_apk_file "$apk_file"; then
                ((success++)) || true
            else
                ((failed++)) || true
            fi
        done

        if (( total == 0 )); then
            echo -e "  ${YELLOW}Warning:${RESET} No backup files (.ab or .apk) found in ${BACKUP_PATH}"
            exit 1
        fi
    fi

    echo ""
    echo -e "${BOLD}${CYAN}--- Restore Complete ---${RESET}"
    echo -e "  Total: ${total}  ${GREEN}Success:${RESET} ${success}  ${RED}Failed:${RESET} ${failed}"
    if $DRY_RUN; then
        echo -e "  ${YELLOW}(dry run - no changes were made)${RESET}"
    fi
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --package)
            PACKAGE="${2:?--package requires a package name}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
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
            if [[ -z "$BACKUP_PATH" ]]; then
                BACKUP_PATH="$1"
            else
                echo -e "${RED}Error:${RESET} Unexpected argument: $1" >&2
                usage >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$BACKUP_PATH" ]]; then
    echo -e "${RED}Error:${RESET} Backup path is required." >&2
    usage >&2
    exit 1
fi

if [[ ! -d "$BACKUP_PATH" ]]; then
    echo -e "${RED}Error:${RESET} Backup directory not found: ${BACKUP_PATH}" >&2
    exit 1
fi

# --- Main ---
check_prerequisites
run_restore
