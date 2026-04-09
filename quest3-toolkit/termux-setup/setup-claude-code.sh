#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-claude-code.sh - Install and configure Claude Code CLI in Termux
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

PROFILE_FILE="$HOME/.bashrc"
NPM_GLOBAL_DIR="$HOME/.npm-global"
API_KEY="${1:-}"

# ---- Ensure Node.js 20+ is available ----------------------------------------
header "Checking Node.js installation"

if ! command -v node &>/dev/null; then
    warn "Node.js not found. Installing nodejs-lts via pkg ..."
    if pkg install -y nodejs-lts; then
        info "Node.js installed."
    else
        error "Failed to install Node.js. Run setup-base.sh first."
        exit 1
    fi
fi

NODE_MAJOR=$(node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 20 ] 2>/dev/null; then
    error "Node.js 20+ is required (found v${NODE_MAJOR}). Please upgrade."
    error "Try: pkg upgrade nodejs-lts"
    exit 1
fi

info "Node.js $(node --version) is installed and meets the v20+ requirement."

if ! command -v npm &>/dev/null; then
    error "npm is not available. Reinstall nodejs-lts via pkg."
    exit 1
fi

# ---- Configure npm global prefix -------------------------------------------
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
    echo "# npm global bin directory (added by setup-claude-code.sh)" >> "$PROFILE_FILE"
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
        exit 1
    fi
fi

# ---- Create ~/.claude/ directory --------------------------------------------
header "Setting up Claude configuration directory"

if [ -d "$HOME/.claude" ]; then
    info "$HOME/.claude/ already exists."
else
    mkdir -p "$HOME/.claude"
    info "Created $HOME/.claude/ directory."
fi

# ---- Configure alias --------------------------------------------------------
header "Configuring alias"

ALIAS_LINE="alias cc='claude'"
if [ -f "$PROFILE_FILE" ] && grep -qF "alias cc=" "$PROFILE_FILE"; then
    info "Alias 'cc' already defined in $PROFILE_FILE."
else
    echo "" >> "$PROFILE_FILE"
    echo "# Claude Code shortcut (added by setup-claude-code.sh)" >> "$PROFILE_FILE"
    echo "$ALIAS_LINE" >> "$PROFILE_FILE"
    info "Added alias cc='claude' to $PROFILE_FILE."
fi

# ---- Configure API key ------------------------------------------------------
header "Configuring Anthropic API key"

# Check if already set in .bashrc
if [ -f "$PROFILE_FILE" ] && grep -qF 'ANTHROPIC_API_KEY' "$PROFILE_FILE"; then
    info "ANTHROPIC_API_KEY is already exported in $PROFILE_FILE."
    warn "To change it, edit $PROFILE_FILE manually."
elif [ -n "$API_KEY" ]; then
    # Key was provided as argument
    echo "" >> "$PROFILE_FILE"
    echo "# Anthropic API key (added by setup-claude-code.sh)" >> "$PROFILE_FILE"
    echo "export ANTHROPIC_API_KEY=\"${API_KEY}\"" >> "$PROFILE_FILE"
    export ANTHROPIC_API_KEY="$API_KEY"
    info "API key configured from command-line argument."
else
    # Prompt the user interactively
    echo -e "  No API key provided as argument."
    echo -e "  ${YELLOW}Usage: $0 <api-key>${NC}"
    echo ""
    echo -n "  Enter your Anthropic API key (or press Enter to skip): "
    read -r INPUT_KEY
    if [ -n "$INPUT_KEY" ]; then
        echo "" >> "$PROFILE_FILE"
        echo "# Anthropic API key (added by setup-claude-code.sh)" >> "$PROFILE_FILE"
        echo "export ANTHROPIC_API_KEY=\"${INPUT_KEY}\"" >> "$PROFILE_FILE"
        export ANTHROPIC_API_KEY="$INPUT_KEY"
        info "API key configured."
    else
        warn "No API key set. Claude Code will not work without ANTHROPIC_API_KEY."
        warn "Set it later: echo 'export ANTHROPIC_API_KEY=\"sk-...\"' >> ~/.bashrc"
    fi
fi

# ---- Verify installation ----------------------------------------------------
header "Verifying installation"

if command -v claude &>/dev/null; then
    CLAUDE_VER=$(claude --version 2>/dev/null || echo "unknown")
    info "claude --version : $CLAUDE_VER"
else
    error "claude binary not found in PATH after installation."
    warn "Try: source ~/.bashrc && claude --version"
fi

# ---- Version summary --------------------------------------------------------
header "Version summary"

NODE_VER=$(node --version 2>&1)
NPM_VER=$(npm --version 2>&1)

info "Node.js : $NODE_VER"
info "npm     : $NPM_VER"

if command -v claude &>/dev/null; then
    CLAUDE_VER=$(claude --version 2>/dev/null || echo "unknown")
    info "Claude  : $CLAUDE_VER"
fi

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    # Show only the first 8 chars for verification
    KEY_PREFIX="${ANTHROPIC_API_KEY:0:8}"
    info "API key : ${KEY_PREFIX}..."
else
    warn "API key : not set in current session"
fi

echo ""
info "Claude Code setup complete."
warn "Run 'source ~/.bashrc' or open a new terminal for changes to take effect."
echo ""
echo -e "  ${GREEN}Quick start:${NC}"
echo -e "    source ~/.bashrc"
echo -e "    claude          # or 'cc' (alias)"
echo ""
