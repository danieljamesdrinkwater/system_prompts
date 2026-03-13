#!/bin/bash
# DanielJamesAudio - Quick Start
# Run this script to start the web app locally

cd "$(dirname "$0")"

# Check for .env
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Edit .env to add your ANTHROPIC_API_KEY for Claude features."
fi

# Install dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "  =================================="
echo "  Daniel James Audio"
echo "  =================================="
echo "  Web app:  http://localhost:5000"
echo "  Login:    daniel / changeme"
echo "  =================================="
echo ""

python3 app.py
