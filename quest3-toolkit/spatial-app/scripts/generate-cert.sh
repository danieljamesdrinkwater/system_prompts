#!/usr/bin/env bash
set -euo pipefail

# Generate self-signed certificates for WebXR HTTPS development.
# Quest 3 browser requires HTTPS for WebXR API access.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/../certs"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/cert.pem" && -f "$CERT_DIR/key.pem" ]]; then
    echo -e "${YELLOW}Certificates already exist at $CERT_DIR${NC}"
    echo "Delete them first if you want to regenerate."
    exit 0
fi

echo "Generating self-signed certificate for WebXR development..."

openssl req -x509 \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -days 365 \
    -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:0.0.0.0"

echo -e "${GREEN}Certificates generated at:${NC}"
echo "  $CERT_DIR/cert.pem"
echo "  $CERT_DIR/key.pem"
echo ""
echo "When opening the dev server on Quest 3 browser, you'll need to"
echo "accept the self-signed certificate warning once."
