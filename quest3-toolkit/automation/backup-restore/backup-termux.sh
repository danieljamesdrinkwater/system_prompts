#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# =============================================================================
# backup-termux.sh - Termux Environment Backup (runs INSIDE Termux on Quest 3)
# =============================================================================
# Backs up the Termux home directory and installed package list.
# Saves to ~/storage/shared/termux-backups/ with timestamp.
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

BACKUP_BASE="$HOME/storage/shared/termux-backups"

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $(basename "$0") [OPTIONS]

${BOLD}Termux Environment Backup${RESET}

Backs up your Termux home directory and installed packages list.
Saves to ~/storage/shared/termux-backups/ with a timestamp.

Options:
  --output <dir>    Custom backup directory (default: ~/storage/shared/termux-backups/)
  --exclude <pat>   Exclude pattern for tar (can be repeated)
  --dry-run         Show what would be backed up without doing it
  -h, --help        Show this help message

Examples:
  $(basename "$0")
  $(basename "$0") --exclude "*.cache" --exclude "node_modules"
  $(basename "$0") --output /sdcard/my-backups
EOF
}

DRY_RUN=false
EXCLUDES=()

check_prerequisites() {
    # Check storage access
    if [[ ! -d "$HOME/storage/shared" ]]; then
        echo -e "${YELLOW}Warning:${RESET} Shared storage not accessible."
        echo "Run 'termux-setup-storage' first, then retry."
        echo ""
        echo -e "${DIM}Attempting to set up storage...${RESET}"
        if command -v termux-setup-storage &>/dev/null; then
            termux-setup-storage
            sleep 2
        fi
        if [[ ! -d "$HOME/storage/shared" ]]; then
            echo -e "${RED}Error:${RESET} Still cannot access shared storage." >&2
            echo "Please run 'termux-setup-storage' manually and grant permission." >&2
            exit 1
        fi
    fi

    # Check tar is available
    if ! command -v tar &>/dev/null; then
        echo -e "${RED}Error:${RESET} tar not found. Installing..." >&2
        pkg install -y tar
    fi
}

run_backup() {
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_dir="${BACKUP_BASE}/${timestamp}"

    echo -e "${BOLD}${CYAN}--- Termux Environment Backup ---${RESET}"
    echo -e "${DIM}$(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo ""

    if $DRY_RUN; then
        echo -e "  ${YELLOW}DRY RUN MODE${RESET}"
    fi

    echo -e "  ${BOLD}Backup location:${RESET} ${backup_dir}"
    echo ""

    if $DRY_RUN; then
        echo -e "  ${DIM}[dry-run] Would create: ${backup_dir}${RESET}"
    else
        mkdir -p "$backup_dir"
    fi

    # --- Step 1: Export installed packages ---
    echo -e "  ${CYAN}[1/3]${RESET} Exporting installed package list..."

    local pkg_file="${backup_dir}/packages.txt"
    if $DRY_RUN; then
        local pkg_count
        pkg_count=$(pkg list-installed 2>/dev/null | wc -l)
        echo -e "  ${DIM}[dry-run] Would save ${pkg_count} packages to packages.txt${RESET}"
    else
        pkg list-installed 2>/dev/null > "$pkg_file" || dpkg --get-selections > "$pkg_file" 2>/dev/null || true
        local pkg_count
        pkg_count=$(wc -l < "$pkg_file")
        echo -e "  ${GREEN}Saved:${RESET} ${pkg_count} packages listed in packages.txt"
    fi

    # --- Step 2: Tar the home directory ---
    echo -e "  ${CYAN}[2/3]${RESET} Archiving home directory..."

    local tar_file="${backup_dir}/termux-home.tar.gz"
    local exclude_args=()
    for excl in "${EXCLUDES[@]+"${EXCLUDES[@]}"}"; do
        exclude_args+=("--exclude=$excl")
    done
    # Always exclude the backup destination to prevent recursion
    exclude_args+=("--exclude=storage/shared/termux-backups")
    # Exclude common large/cache directories by default
    exclude_args+=("--exclude=.cache")
    exclude_args+=("--exclude=.npm/_cacache")
    exclude_args+=("--exclude=__pycache__")

    if $DRY_RUN; then
        local home_size
        home_size=$(du -sh "$HOME" 2>/dev/null | awk '{print $1}')
        echo -e "  ${DIM}[dry-run] Would archive ~/ (${home_size}) to termux-home.tar.gz${RESET}"
        echo -e "  ${DIM}[dry-run] Excludes: ${exclude_args[*]}${RESET}"
    else
        echo -e "  ${DIM}This may take a moment...${RESET}"
        if tar czf "$tar_file" -C "$HOME" "${exclude_args[@]}" . 2>/dev/null; then
            local tar_size
            tar_size=$(du -h "$tar_file" | awk '{print $1}')
            echo -e "  ${GREEN}Saved:${RESET} termux-home.tar.gz (${tar_size})"
        else
            echo -e "  ${YELLOW}Warning:${RESET} Some files may have been skipped (permission errors are normal)."
            if [[ -f "$tar_file" ]]; then
                local tar_size
                tar_size=$(du -h "$tar_file" | awk '{print $1}')
                echo -e "  ${GREEN}Saved:${RESET} termux-home.tar.gz (${tar_size})"
            fi
        fi
    fi

    # --- Step 3: Save metadata ---
    echo -e "  ${CYAN}[3/3]${RESET} Writing backup metadata..."

    if ! $DRY_RUN; then
        cat > "${backup_dir}/backup-info.txt" <<INFO
Termux Backup
=============
Date:       $(date '+%Y-%m-%d %H:%M:%S')
Timestamp:  ${timestamp}
Termux Ver: $(pkg show termux-tools 2>/dev/null | grep Version | head -1 || echo "unknown")
Arch:       $(uname -m)
Home Size:  $(du -sh "$HOME" 2>/dev/null | awk '{print $1}')
Packages:   $(wc -l < "$pkg_file") installed
Archive:    $(du -h "$tar_file" 2>/dev/null | awk '{print $1}')
INFO
        echo -e "  ${GREEN}Saved:${RESET} backup-info.txt"
    fi

    echo ""
    echo -e "${BOLD}${CYAN}--- Backup Complete ---${RESET}"
    if ! $DRY_RUN; then
        echo -e "  ${BOLD}Location:${RESET} ${backup_dir}"
        echo ""
        echo -e "  ${DIM}Files:${RESET}"
        ls -lh "$backup_dir" | tail -n +2 | while IFS= read -r line; do
            echo -e "    ${DIM}${line}${RESET}"
        done
        echo ""
        echo -e "  ${DIM}To restore: bash restore-termux.sh ${backup_dir}${RESET}"
    fi
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            BACKUP_BASE="${2:?--output requires a directory path}"
            shift 2
            ;;
        --exclude)
            EXCLUDES+=("${2:?--exclude requires a pattern}")
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
        *)
            echo -e "${RED}Error:${RESET} Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# --- Main ---
check_prerequisites
run_backup
