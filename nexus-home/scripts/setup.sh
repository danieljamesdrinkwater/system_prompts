#!/bin/bash
# Nexus Home — First-run setup script
set -e

echo "=== Nexus Home Setup ==="

# Create config from example if not exists
if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo "Created config.yaml from template — edit it with your settings"
fi

# Create data directories
mkdir -p data models

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from template"
fi

# Generate random API key
if grep -q "change-me-to-a-real-key" config.yaml; then
    API_KEY=$(openssl rand -hex 32)
    sed -i "s/change-me-to-a-real-key/$API_KEY/" config.yaml
    echo "Generated API key: $API_KEY"
    echo "Save this key — you'll need it to access the dashboard and API"
fi

# Create storage mount point
sudo mkdir -p /mnt/storage
sudo chown $USER:$USER /mnt/storage

# Start services
echo ""
echo "Starting Docker services..."
docker compose up -d

# Wait for Ollama to be ready
echo "Waiting for Ollama..."
for i in {1..30}; do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Pull default AI model
echo "Pulling Ollama model (llama3.2)..."
docker compose exec ollama ollama pull llama3.2

echo ""
echo "=== Setup Complete ==="
echo "Dashboard: http://localhost:8000"
echo "API Docs:  http://localhost:8000/docs"
echo "API Key:   $API_KEY"
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your MQTT, calendar, mail, and SIP settings"
echo "  2. Configure your Tasmota/ESPHome devices to use MQTT broker at port 1883"
echo "  3. Add cameras via the dashboard or API"
echo "  4. Restart: docker compose restart app"
