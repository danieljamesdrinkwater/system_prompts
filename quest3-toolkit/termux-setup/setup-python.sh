#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-python.sh - Configure Python, pip, and a default venv in Termux
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

VENV_DIR="$HOME/venvs/default"
VENV_PACKAGES=(requests flask)

# ---- Validate Python -------------------------------------------------------
header "Validating Python installation"

if ! command -v python &>/dev/null; then
    error "Python is not installed. Run setup-base.sh first."
    exit 1
fi

if python -c "print('ok')" 2>/dev/null | grep -q "ok"; then
    info "Python runtime is functional."
else
    error "Python is installed but runtime test failed."
    exit 1
fi

# ---- Install / upgrade pip -------------------------------------------------
header "Setting up pip"

if python -m pip --version &>/dev/null; then
    info "pip is already available."
else
    warn "pip not found — installing via ensurepip."
    if python -m ensurepip --upgrade; then
        info "pip installed via ensurepip."
    else
        error "Failed to install pip. Try: pkg install python-pip"
        exit 1
    fi
fi

echo -e "  Upgrading pip to latest version ..."
if python -m pip install --upgrade pip 2>&1 | tail -n1; then
    info "pip is up to date."
else
    warn "pip upgrade encountered issues (continuing with current version)."
fi

# ---- Create default virtual environment ------------------------------------
header "Creating default virtual environment"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
    info "Virtual environment already exists at $VENV_DIR."
else
    mkdir -p "$(dirname "$VENV_DIR")"
    echo -e "  Creating venv at ${YELLOW}${VENV_DIR}${NC} ..."
    python -m venv "$VENV_DIR"
    info "Virtual environment created at $VENV_DIR."
fi

# ---- Install common packages in the venv -----------------------------------
header "Installing packages in venv"

# Activate the venv for this section
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

for pkg in "${VENV_PACKAGES[@]}"; do
    if python -m pip show "$pkg" &>/dev/null; then
        info "$pkg is already installed in venv."
    else
        echo -e "  Installing ${YELLOW}${pkg}${NC} ..."
        if python -m pip install "$pkg"; then
            info "$pkg installed."
        else
            error "Failed to install $pkg."
        fi
    fi
done

# Deactivate the venv
deactivate

# ---- Print version info -----------------------------------------------------
header "Version summary"

PY_VER=$(python --version 2>&1)
PIP_VER=$(python -m pip --version 2>&1)

info "Python : $PY_VER"
info "pip    : $PIP_VER"
echo ""

info "Default venv : $VENV_DIR"
info "Activate with: source $VENV_DIR/bin/activate"

echo ""
echo -e "  Packages in venv:"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
for pkg in "${VENV_PACKAGES[@]}"; do
    ver=$(python -m pip show "$pkg" 2>/dev/null | grep "^Version:" | cut -d' ' -f2)
    if [ -n "$ver" ]; then
        echo -e "    ${GREEN}${pkg}${NC} == ${ver}"
    else
        echo -e "    ${RED}${pkg}${NC}  (not found)"
    fi
done
deactivate

echo ""
info "Python setup complete."
