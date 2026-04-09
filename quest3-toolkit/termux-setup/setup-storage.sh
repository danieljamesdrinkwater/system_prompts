#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-storage.sh - Configure Termux shared storage access on Quest 3
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

STORAGE_DIR="$HOME/storage/shared"
PROJECTS_DIR="$HOME/storage/shared/projects"
DOWNLOAD_DIR="$HOME/storage/shared/Download"

# ---- Request storage permission --------------------------------------------
header "Setting up Termux storage access"

if [ -d "$STORAGE_DIR" ]; then
    info "Storage already accessible at $STORAGE_DIR — skipping permission request."
else
    warn "Requesting storage permission. A system dialog may appear — please grant access."
    termux-setup-storage

    # Wait for the user to grant permission (up to 30 seconds)
    MAX_WAIT=30
    WAITED=0
    while [ ! -d "$STORAGE_DIR" ] && [ "$WAITED" -lt "$MAX_WAIT" ]; do
        sleep 1
        WAITED=$((WAITED + 1))
    done

    if [ -d "$STORAGE_DIR" ]; then
        info "Storage permission granted."
    else
        error "Timed out waiting for storage permission (${MAX_WAIT}s)."
        error "Please grant the storage permission in the dialog and re-run this script."
        exit 1
    fi
fi

# ---- Validate storage directory --------------------------------------------
header "Validating storage"

if [ -d "$STORAGE_DIR" ]; then
    info "$STORAGE_DIR exists and is accessible."
else
    error "$STORAGE_DIR does not exist. Storage setup failed."
    exit 1
fi

# ---- Create projects directory on shared storage ---------------------------
header "Creating projects directory"

if [ -d "$PROJECTS_DIR" ]; then
    info "$PROJECTS_DIR already exists."
else
    mkdir -p "$PROJECTS_DIR"
    info "Created $PROJECTS_DIR."
fi

# ---- Create convenience symlinks -------------------------------------------
header "Creating convenience symlinks"

# ~/projects -> ~/storage/shared/projects
if [ -L "$HOME/projects" ]; then
    CURRENT_TARGET=$(readlink "$HOME/projects")
    if [ "$CURRENT_TARGET" = "$PROJECTS_DIR" ]; then
        info "~/projects symlink already points to $PROJECTS_DIR."
    else
        warn "~/projects points to $CURRENT_TARGET — updating to $PROJECTS_DIR."
        ln -sfn "$PROJECTS_DIR" "$HOME/projects"
        info "Updated ~/projects symlink."
    fi
elif [ -e "$HOME/projects" ]; then
    warn "~/projects exists but is not a symlink. Skipping to avoid data loss."
    warn "Remove or rename it manually, then re-run this script."
else
    ln -s "$PROJECTS_DIR" "$HOME/projects"
    info "Created symlink ~/projects -> $PROJECTS_DIR"
fi

# ~/downloads -> ~/storage/shared/Download
if [ -L "$HOME/downloads" ]; then
    CURRENT_TARGET=$(readlink "$HOME/downloads")
    if [ "$CURRENT_TARGET" = "$DOWNLOAD_DIR" ]; then
        info "~/downloads symlink already points to $DOWNLOAD_DIR."
    else
        warn "~/downloads points to $CURRENT_TARGET — updating to $DOWNLOAD_DIR."
        ln -sfn "$DOWNLOAD_DIR" "$HOME/downloads"
        info "Updated ~/downloads symlink."
    fi
elif [ -e "$HOME/downloads" ]; then
    warn "~/downloads exists but is not a symlink. Skipping to avoid data loss."
else
    ln -s "$DOWNLOAD_DIR" "$HOME/downloads"
    info "Created symlink ~/downloads -> $DOWNLOAD_DIR"
fi

# ---- Summary ---------------------------------------------------------------
echo ""
info "Storage setup complete."
echo -e "  ${GREEN}~/projects${NC}  -> $PROJECTS_DIR"
echo -e "  ${GREEN}~/downloads${NC} -> $DOWNLOAD_DIR"
