#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# =============================================================================
# restore-termux.sh - Termux Environment Restore (runs INSIDE Termux on Quest 3)
# =============================================================================
# Restores a backup created by backup-termux.sh.
# Extracts home directory archive and reinstalls packages.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

BACKUP_PATH=""
SKIP_PACKAGES=false
SKIP_FILES=false
DRY_RUN=false

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") <backup-path> [OPTIONS]

${BOLD}Termux Environment Restore${RESET}

Restores a Termux backup created by backup-termux.sh.

Arguments:
  <backup-path>          Path to backup directory

Options:
  --skip-packages        Skip package reinstallation
  --skip-files           Skip home directory restore
  --dry-run              Show what would be restored without doing it
  -h, --help             Show this help message

Examples:
  $(basename "$0") ~/storage/shared/termux-backups/20250115_143022
  $(basename "$0") ~/storage/shared/termux-backups/20250115_143022 --skip-packages
  $(basename "$0") /sdcard/termux-backups/20250115_143022 --dry-run
EOF
}

check_prerequisites() {
    if ! command -v tar &>/dev/null; then
        echo -e "${RED}Error:${RESET} tar not found. Installing..." >&2
        pkg install -y tar
    fi
}

run_restore() {
    echo -e "${BOLD}${CYAN}--- Termux Environment Restore ---${RESET}"
    echo -e "${DIM}$(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "  Backup: ${BOLD}${BACKUP_PATH}${RESET}"

    if $DRY_RUN; then
        echo -e "  ${YELLOW}DRY RUN MODE${RESET}"
    fi
    echo ""

    # Show backup info if available
    if [[ -f "${BACKUP_PATH}/backup-info.txt" ]]; then
        echo -e "  ${DIM}--- Backup Info ---${RESET}"
        while IFS= read -r line; do
            echo -e "  ${DIM}  ${line}${RESET}"
        done < "${BACKUP_PATH}/backup-info.txt"
        echo ""
    fi

    # --- Step 1: Reinstall packages ---
    if ! $SKIP_PACKAGES; then
        local pkg_file="${BACKUP_PATH}/packages.txt"
        if [[ -f "$pkg_file" ]]; then
            echo -e "  ${CYAN}[1/2]${RESET} Reinstalling packages..."

            # Parse package names from pkg list-installed or dpkg format
            local packages=()
            while IFS= read -r line; do
                # pkg list-installed format: "name/stable,now 1.2.3 aarch64 [installed]"
                # dpkg --get-selections format: "name    install"
                local pkg_name
                pkg_name=$(echo "$line" | awk -F'[/ \t]' '{print $1}')
                if [[ -n "$pkg_name" && "$pkg_name" != "Listing..." ]]; then
                    packages+=("$pkg_name")
                fi
            done < "$pkg_file"

            local pkg_count=${#packages[@]}
            echo -e "  ${DIM}Found ${pkg_count} packages to install${RESET}"

            if $DRY_RUN; then
                echo -e "  ${DIM}[dry-run] Would install: ${packages[*]:0:20}...${RESET}"
            else
                # Update package index first
                echo -e "  ${DIM}Updating package index...${RESET}"
                pkg update -y 2>/dev/null || apt-get update -y 2>/dev/null || true

                local installed=0 pkg_failed=0
                for pkg_name in "${packages[@]}"; do
                    # Skip base packages that are always present
                    if [[ "$pkg_name" == "apt" || "$pkg_name" == "dpkg" || "$pkg_name" == "bash" ]]; then
                        continue
                    fi
                    echo -ne "  ${DIM}Installing ${pkg_name}...${RESET}\r"
                    if pkg install -y "$pkg_name" &>/dev/null; then
                        ((installed++)) || true
                    else
                        ((pkg_failed++)) || true
                        echo -e "  ${YELLOW}Warning:${RESET} Failed to install: ${pkg_name}"
                    fi
                done
                echo -e "  ${GREEN}Packages:${RESET} ${installed} installed, ${pkg_failed} failed"
            fi
        else
            echo -e "  ${YELLOW}Warning:${RESET} packages.txt not found, skipping package restore."
        fi
    else
        echo -e "  ${DIM}[skipped] Package reinstallation${RESET}"
    fi

    echo ""

    # --- Step 2: Extract home directory ---
    if ! $SKIP_FILES; then
        local tar_file="${BACKUP_PATH}/termux-home.tar.gz"
        if [[ -f "$tar_file" ]]; then
            echo -e "  ${CYAN}[2/2]${RESET} Restoring home directory..."

            local tar_size
            tar_size=$(du -h "$tar_file" | awk '{print $1}')
            echo -e "  ${DIM}Archive size: ${tar_size}${RESET}"

            if $DRY_RUN; then
                echo -e "  ${DIM}[dry-run] Would extract to: ${HOME}${RESET}"
                echo -e "  ${DIM}[dry-run] Archive contents:${RESET}"
                tar tzf "$tar_file" 2>/dev/null | head -20 | while IFS= read -r f; do
                    echo -e "    ${DIM}${f}${RESET}"
                done
                echo -e "    ${DIM}...${RESET}"
            else
                echo -e "  ${DIM}Extracting to ${HOME}...${RESET}"
                echo -e "  ${YELLOW}Note:${RESET} Existing files will be overwritten."

                if tar xzf "$tar_file" -C "$HOME" 2>/dev/null; then
                    echo -e "  ${GREEN}Home directory restored successfully.${RESET}"
                else
                    echo -e "  ${YELLOW}Warning:${RESET} Some files may have failed to extract (permission errors are normal)."
                    echo -e "  ${GREEN}Most files should be restored.${RESET}"
                fi
            fi
        else
            echo -e "  ${YELLOW}Warning:${RESET} termux-home.tar.gz not found, skipping file restore."
        fi
    else
        echo -e "  ${DIM}[skipped] Home directory restore${RESET}"
    fi

    echo ""
    echo -e "${BOLD}${CYAN}--- Restore Complete ---${RESET}"
    if $DRY_RUN; then
        echo -e "  ${YELLOW}(dry run - no changes were made)${RESET}"
    else
        echo -e "  ${DIM}You may want to restart Termux for all changes to take effect.${RESET}"
    fi
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-packages)
            SKIP_PACKAGES=true
            shift
            ;;
        --skip-files)
            SKIP_FILES=true
            shift
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
