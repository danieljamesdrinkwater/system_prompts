#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-ollama.sh - Configure Ollama client on Quest 3 (server on Mac)
# ---------------------------------------------------------------------------
# Ollama cannot run natively on Quest 3 due to ARM64/Android limitations.
# This script sets up the Quest as an Ollama CLIENT, connecting to a Mac
# (or other host) running the Ollama server on the local network.
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
DEFAULT_HOST="http://192.168.1.35:11434"
OLLAMA_HOST="${1:-$DEFAULT_HOST}"
MODEL="phi3:mini"

# ---- Detect environment ------------------------------------------------------
header "Detecting environment"

IS_TERMUX=false
IS_MAC=false

if [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=true
    info "Running on Termux (Quest 3)."
elif [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
    info "Running on macOS."
else
    warn "Unknown environment: $(uname). Proceeding with best-effort setup."
fi

# ---- Mac-side setup (install Ollama server) ----------------------------------
if [ "$IS_MAC" = true ]; then
    header "Setting up Ollama server (macOS)"

    if command -v ollama &>/dev/null; then
        OLLAMA_VER=$(ollama --version 2>&1 || echo "unknown")
        info "Ollama is already installed: $OLLAMA_VER"
    else
        echo -e "  Installing ${YELLOW}ollama${NC} via Homebrew ..."
        if command -v brew &>/dev/null; then
            if brew install ollama; then
                info "Ollama installed via Homebrew."
            else
                error "Failed to install Ollama via Homebrew."
                warn "Install manually from https://ollama.ai"
                exit 1
            fi
        else
            error "Homebrew not found. Install Ollama manually from https://ollama.ai"
            exit 1
        fi
    fi

    # Pull the model
    header "Pulling model: $MODEL"

    echo -e "  Pulling ${YELLOW}${MODEL}${NC} (this may take a few minutes) ..."
    if ollama pull "$MODEL"; then
        info "Model $MODEL pulled successfully."
    else
        error "Failed to pull model $MODEL."
        warn "Ensure Ollama is running: ollama serve"
        exit 1
    fi

    # Check if Ollama is serving
    header "Checking Ollama server"

    if curl -s --max-time 5 "http://localhost:11434/api/tags" &>/dev/null; then
        info "Ollama server is running on localhost:11434."
    else
        warn "Ollama server is not running."
        warn "Start it with: ollama serve"
        warn "Or run a model directly: ollama run $MODEL"
    fi

    # Remind about network binding
    echo ""
    warn "For Quest 3 to connect, Ollama must listen on all interfaces."
    warn "Set this before starting the server:"
    echo -e "    ${YELLOW}export OLLAMA_HOST=0.0.0.0:11434${NC}"
    echo -e "    ${YELLOW}ollama serve${NC}"
    echo ""
    warn "Also ensure your firewall allows port 11434 from local network."

    # Show the Mac's local IP for Quest configuration
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")
    if [ "$LOCAL_IP" != "unknown" ]; then
        echo ""
        info "Mac local IP (en0): $LOCAL_IP"
        echo -e "  On Quest 3, set: ${YELLOW}export OLLAMA_HOST=http://${LOCAL_IP}:11434${NC}"
    fi

    echo ""
    info "Mac-side Ollama setup complete."
    exit 0
fi

# ---- Quest-side setup (client only) -----------------------------------------
header "Configuring Ollama client (Quest 3)"

warn "Ollama cannot run natively on Quest 3."
warn "This configures the Quest as a CLIENT connecting to: $OLLAMA_HOST"

# ---- Install curl if missing ------------------------------------------------
if ! command -v curl &>/dev/null; then
    echo -e "  Installing ${YELLOW}curl${NC} ..."
    if pkg install -y curl; then
        info "curl installed."
    else
        error "Failed to install curl."
        exit 1
    fi
fi

# ---- Export OLLAMA_HOST in .bashrc ------------------------------------------
header "Setting OLLAMA_HOST"

EXPORT_LINE="export OLLAMA_HOST=\"${OLLAMA_HOST}\""

if [ -f "$PROFILE_FILE" ] && grep -qF 'OLLAMA_HOST' "$PROFILE_FILE"; then
    CURRENT_HOST=$(grep 'OLLAMA_HOST' "$PROFILE_FILE" | head -n1 | cut -d'"' -f2)
    if [ "$CURRENT_HOST" = "$OLLAMA_HOST" ]; then
        info "OLLAMA_HOST already set to $OLLAMA_HOST in $PROFILE_FILE."
    else
        warn "OLLAMA_HOST is set to $CURRENT_HOST — updating to $OLLAMA_HOST."
        # Replace the existing line
        sed -i "s|export OLLAMA_HOST=.*|${EXPORT_LINE}|" "$PROFILE_FILE"
        info "Updated OLLAMA_HOST in $PROFILE_FILE."
    fi
else
    echo "" >> "$PROFILE_FILE"
    echo "# Ollama server host (added by setup-ollama.sh)" >> "$PROFILE_FILE"
    echo "$EXPORT_LINE" >> "$PROFILE_FILE"
    info "Added OLLAMA_HOST=$OLLAMA_HOST to $PROFILE_FILE."
fi

# Export for current session
export OLLAMA_HOST="$OLLAMA_HOST"

# ---- Create helper alias ----------------------------------------------------
header "Creating helper alias"

ALIAS_LINE="alias ollama-test='curl -s \$OLLAMA_HOST/api/tags | python -m json.tool 2>/dev/null || echo \"Cannot reach Ollama server\"'"

if [ -f "$PROFILE_FILE" ] && grep -qF 'alias ollama-test' "$PROFILE_FILE"; then
    info "Alias 'ollama-test' already defined in $PROFILE_FILE."
else
    echo "" >> "$PROFILE_FILE"
    echo "# Ollama connectivity test (added by setup-ollama.sh)" >> "$PROFILE_FILE"
    echo "$ALIAS_LINE" >> "$PROFILE_FILE"
    info "Added alias 'ollama-test' to $PROFILE_FILE."
fi

# ---- Test connectivity to Mac -----------------------------------------------
header "Testing connectivity to Ollama server"

echo -e "  Connecting to ${YELLOW}${OLLAMA_HOST}${NC} ..."

if curl -s --max-time 10 "${OLLAMA_HOST}/api/tags" &>/dev/null; then
    info "Successfully connected to Ollama server at $OLLAMA_HOST."

    # List available models
    MODELS=$(curl -s --max-time 10 "${OLLAMA_HOST}/api/tags" 2>/dev/null)
    if [ -n "$MODELS" ] && command -v python &>/dev/null; then
        echo ""
        echo -e "  ${GREEN}Available models:${NC}"
        echo "$MODELS" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        name = m.get('name', 'unknown')
        size = m.get('size', 0)
        size_gb = size / (1024**3)
        print(f'    {name}  ({size_gb:.1f} GB)')
except Exception:
    print('    (could not parse model list)')
" 2>/dev/null || echo "    (could not parse model list)"
    fi

    # Quick inference test
    echo ""
    echo -e "  Running quick inference test with ${YELLOW}${MODEL}${NC} ..."
    RESPONSE=$(curl -s --max-time 30 "${OLLAMA_HOST}/api/generate" \
        -d "{\"model\":\"${MODEL}\",\"prompt\":\"Say hello in exactly 5 words.\",\"stream\":false}" \
        2>/dev/null)

    if [ -n "$RESPONSE" ] && command -v python &>/dev/null; then
        ANSWER=$(echo "$RESPONSE" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('response', 'No response'))
except Exception:
    print('Could not parse response')
" 2>/dev/null || echo "Could not parse response")
        info "Inference test response: $ANSWER"
    else
        warn "Inference test did not return a parseable response."
        warn "Ensure model '$MODEL' is pulled on the server: ollama pull $MODEL"
    fi
else
    error "Cannot reach Ollama server at $OLLAMA_HOST."
    echo ""
    echo -e "  ${YELLOW}Troubleshooting:${NC}"
    echo -e "    1. Ensure the Mac is on the same Wi-Fi network as Quest 3."
    echo -e "    2. Start Ollama on Mac: OLLAMA_HOST=0.0.0.0:11434 ollama serve"
    echo -e "    3. Check firewall allows port 11434 from local network."
    echo -e "    4. Verify the IP address: $OLLAMA_HOST"
    echo -e "    5. Re-run with correct IP: $0 http://<mac-ip>:11434"
    echo ""
    warn "Setup saved — connectivity test can be retried later with: ollama-test"
fi

# ---- Summary ----------------------------------------------------------------
header "Summary"

echo -e "  OLLAMA_HOST : ${GREEN}${OLLAMA_HOST}${NC}"
echo -e "  Model       : ${GREEN}${MODEL}${NC}"
echo -e "  Test alias  : ${GREEN}ollama-test${NC}"
echo ""
info "Ollama client setup complete."
warn "Run 'source ~/.bashrc' or open a new terminal for changes to take effect."
echo ""
echo -e "  ${GREEN}Usage with voice assistant:${NC}"
echo -e "    source ~/.bashrc"
echo -e "    ~/voice-assistant/start.sh   # will auto-detect OLLAMA_HOST"
echo ""
