#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-nodejs.sh - Configure Node.js & install Claude Code in Termux
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

NPM_GLOBAL_DIR="$HOME/.npm-global"
PROFILE_FILE="$HOME/.bashrc"

# ---- Validate Node.js ------------------------------------------------------
header "Validating Node.js installation"

if ! command -v node &>/dev/null; then
    error "Node.js is not installed. Run setup-base.sh first."
    exit 1
fi

if node -e "console.log('ok')" 2>/dev/null | grep -q "ok"; then
    info "Node.js runtime is functional."
else
    error "Node.js is installed but 'node -e' test failed."
    exit 1
fi

if ! command -v npm &>/dev/null; then
    error "npm is not available. Reinstall nodejs-lts via pkg."
    exit 1
fi

# ---- Configure npm global directory ----------------------------------------
header "Configuring npm global prefix"

mkdir -p "$NPM_GLOBAL_DIR"

CURRENT_PREFIX=$(npm config get prefix 2>/dev/null || echo "")
if [ "$CURRENT_PREFIX" = "$NPM_GLOBAL_DIR" ]; then
    info "npm global prefix already set to $NPM_GLOBAL_DIR."
else
    npm config set prefix "$NPM_GLOBAL_DIR"
    info "Set npm global prefix to $NPM_GLOBAL_DIR."
fi

# Add to PATH in .bashrc if not already present
PATH_LINE='export PATH="$HOME/.npm-global/bin:$PATH"'
if [ -f "$PROFILE_FILE" ] && grep -qF '.npm-global/bin' "$PROFILE_FILE"; then
    info "PATH entry for .npm-global/bin already in $PROFILE_FILE."
else
    echo "" >> "$PROFILE_FILE"
    echo "# npm global bin directory (added by setup-nodejs.sh)" >> "$PROFILE_FILE"
    echo "$PATH_LINE" >> "$PROFILE_FILE"
    info "Added .npm-global/bin to PATH in $PROFILE_FILE."
fi

# Make sure the current session has it too
export PATH="$NPM_GLOBAL_DIR/bin:$PATH"

# ---- Install Claude Code ---------------------------------------------------
header "Installing @anthropic-ai/claude-code"

warn "Claude Code on Quest 3 (ARM64/Android) is EXPERIMENTAL."
warn "Some native modules may not compile. This is best-effort."

if command -v claude &>/dev/null; then
    info "claude-code is already installed ($(claude --version 2>/dev/null || echo 'unknown version'))."
    warn "To upgrade, run: npm update -g @anthropic-ai/claude-code"
else
    echo -e "  Installing ${YELLOW}@anthropic-ai/claude-code${NC} globally ..."
    if npm install -g @anthropic-ai/claude-code; then
        info "claude-code installed successfully."
    else
        error "claude-code installation failed."
        warn "This is expected on some Quest 3 Termux setups."
        warn "You can retry manually: npm install -g @anthropic-ai/claude-code"
    fi
fi

# ---- Print version info -----------------------------------------------------
header "Version summary"

NODE_VER=$(node --version 2>&1)
NPM_VER=$(npm --version 2>&1)

info "Node.js : $NODE_VER"
info "npm     : $NPM_VER"

if command -v claude &>/dev/null; then
    CLAUDE_VER=$(claude --version 2>/dev/null || echo "unknown")
    info "Claude  : $CLAUDE_VER"
fi

echo ""
info "Node.js setup complete."
warn "Run 'source ~/.bashrc' or open a new terminal for PATH changes to take effect."
