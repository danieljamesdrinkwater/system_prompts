#!/usr/bin/env bash
# Install the Friday 8:57 AM cron job for the property automation.
# Usage: bash setup_cron.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(which python3)"
CRON_CMD="57 8 * * 5 cd ${SCRIPT_DIR}/.. && ${PYTHON} ${SCRIPT_DIR}/friday_property_bot.py >> ${SCRIPT_DIR}/logs/cron.log 2>&1"

# Add to crontab without duplicating
(crontab -l 2>/dev/null | grep -v 'friday_property_bot'; echo "$CRON_CMD") | crontab -

echo "Cron job installed:"
crontab -l | grep friday_property_bot
echo ""
echo "The script will run every Friday at 8:57 AM."
echo "It logs in by ~9:00 AM and refreshes for 5 minutes."
