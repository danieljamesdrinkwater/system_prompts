#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-base.sh - Install core packages in Termux on Quest 3
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

PACKAGES=(
    git
    python
    nodejs-lts
    build-essential
    openssh
    wget
    curl
    clang
    make
)

# Map package name -> binary used to verify installation
declare -A PKG_BIN=(
    [git]=git
    [python]=python
    [nodejs-lts]=node
    [build-essential]=cc
    [openssh]=ssh
    [wget]=wget
    [curl]=curl
    [clang]=clang
    [make]=make
)

# Map package name -> version flag (most use --version)
declare -A PKG_VER_FLAG=(
    [git]="--version"
    [python]="--version"
    [nodejs-lts]="--version"
    [build-essential]="--version"
    [openssh]="-V"
    [wget]="--version"
    [curl]="--version"
    [clang]="--version"
    [make]="--version"
)

FAILED=()

# ---- Update package index & upgrade existing packages ----------------------
header "Updating package repositories"
if pkg update -y && pkg upgrade -y; then
    info "Package repositories updated and existing packages upgraded."
else
    warn "Package update/upgrade encountered warnings (continuing anyway)."
fi

# ---- Install each package --------------------------------------------------
header "Installing packages"
for pkg in "${PACKAGES[@]}"; do
    bin="${PKG_BIN[$pkg]}"

    # Idempotency: skip if the binary already exists
    if command -v "$bin" &>/dev/null; then
        info "$pkg is already installed — skipping."
    else
        echo -e "  Installing ${YELLOW}${pkg}${NC} ..."
        if pkg install -y "$pkg"; then
            info "$pkg installed."
        else
            error "Failed to install $pkg."
            FAILED+=("$pkg")
            continue
        fi
    fi
done

# ---- Validate installations & print versions --------------------------------
header "Validating installations"
for pkg in "${PACKAGES[@]}"; do
    bin="${PKG_BIN[$pkg]}"
    flag="${PKG_VER_FLAG[$pkg]}"

    if command -v "$bin" &>/dev/null; then
        ver=$("$bin" "$flag" 2>&1 | head -n1)
        info "$pkg  ->  $ver"
    else
        error "$pkg binary '$bin' not found after install."
        FAILED+=("$pkg")
    fi
done

# ---- Summary ---------------------------------------------------------------
echo ""
if [ ${#FAILED[@]} -eq 0 ]; then
    info "All packages installed and verified successfully."
else
    error "The following packages had issues: ${FAILED[*]}"
    exit 1
fi
