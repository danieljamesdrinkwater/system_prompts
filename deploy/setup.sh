#!/bin/bash
# HGV-ADAS deployment script for Raspberry Pi
# Run as: sudo bash setup.sh
set -euo pipefail

INSTALL_DIR="/home/pi/hgv-adas"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== HGV-ADAS Deployment ==="

# ── System packages ──────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3-pip python3-venv \
    hostapd dnsmasq \
    espeak-ng \
    libopencv-dev python3-opencv \
    bluetooth bluez

# ── WiFi Access Point ────────────────────────────────────────
echo "[2/6] Configuring WiFi access point..."

# Static IP for wlan0
cat > /etc/network/interfaces.d/wlan0 <<'EOF'
auto wlan0
iface wlan0 inet static
    address 192.168.4.1
    netmask 255.255.255.0
    nohook wpa_supplicant
EOF

cp "$SCRIPT_DIR/hostapd.conf" /etc/hostapd/hostapd.conf
cp "$SCRIPT_DIR/dnsmasq.conf" /etc/dnsmasq.d/hgv-adas.conf

# Point hostapd to its config
sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || true

systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

# ── Application ──────────────────────────────────────────────
echo "[3/6] Installing application..."

mkdir -p "$INSTALL_DIR"
cp -r "$REPO_DIR/pi/"* "$INSTALL_DIR/"

# Python virtual environment
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q

chown -R pi:pi "$INSTALL_DIR"

# ── YOLOv8 model ─────────────────────────────────────────────
echo "[4/6] Downloading YOLOv8 model..."
mkdir -p "$INSTALL_DIR/models"
if [ ! -f "$INSTALL_DIR/models/yolov8n.pt" ]; then
    "$INSTALL_DIR/venv/bin/python" -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true
    cp -f yolov8n.pt "$INSTALL_DIR/models/" 2>/dev/null || true
fi

# ── systemd service ──────────────────────────────────────────
echo "[5/6] Installing systemd service..."
cp "$SCRIPT_DIR/hgv-adas.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable hgv-adas

# ── Summary ──────────────────────────────────────────────────
echo "[6/6] Done."
echo ""
echo "  WiFi AP:  HGV-ADAS (192.168.4.1)"
echo "  Service:  sudo systemctl start hgv-adas"
echo "  Logs:     journalctl -u hgv-adas -f"
echo "  Reboot to activate the WiFi AP."
