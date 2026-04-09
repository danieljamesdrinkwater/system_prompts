#!/usr/bin/env bash
set -euo pipefail

# Start the Vite HTTPS dev server for Quest 3 WebXR development.
# Automatically generates certs if missing, then launches vite.

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

# Install dependencies if needed
if [[ ! -d "node_modules" ]]; then
    echo -e "${CYAN}Installing dependencies...${NC}"
    npm install
fi

# Get local IP for Quest 3 access
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${GREEN}Starting Spatial Workspace dev server...${NC}"
echo -e "Local:  ${CYAN}https://localhost:5173${NC}"
echo -e "Quest:  ${CYAN}https://${LOCAL_IP}:5173${NC}"
echo ""
echo "Open the Quest URL in your Quest 3 browser to enter XR mode."
echo ""

npx vite --host
