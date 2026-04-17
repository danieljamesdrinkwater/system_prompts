#!/usr/bin/env bash
set -euo pipefail

# Build the spatial app and serve it for Quest 3 access over LAN.
# This creates a production build and serves it with a simple HTTPS server.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
CERT_DIR="$PROJECT_DIR/certs"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_DIR"

# Generate certs if missing
if [[ ! -f "$CERT_DIR/cert.pem" || ! -f "$CERT_DIR/key.pem" ]]; then
    echo -e "${YELLOW}No certs found. Generating...${NC}"
    bash "$SCRIPT_DIR/generate-cert.sh"
fi

# Build
echo -e "${CYAN}Building production bundle...${NC}"
npm run build

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${GREEN}Production build complete.${NC}"
echo ""
echo -e "Serving at: ${CYAN}https://${LOCAL_IP}:4173${NC}"
echo "Open this URL in your Quest 3 browser."
echo ""

npx vite preview --host
