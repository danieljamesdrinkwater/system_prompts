# Setting Up Telegram Notifications

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. "Workshop Finder")
4. Choose a username (e.g. "workshop_finder_bot")
5. BotFather will give you a **bot token** like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
6. Copy this token into `config.yaml` under `telegram.bot_token`

## Step 2: Get Your Chat ID

1. Open your new bot in Telegram and send it any message (e.g. "hello")
2. Open this URL in your browser (replace TOKEN with your bot token):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
3. Look for `"chat":{"id":123456789}` in the response
4. Copy that number into `config.yaml` under `telegram.chat_id`

## Step 3: Test It

```bash
python monitor.py --test-telegram
```

You should receive a test message in Telegram. If not, double-check your token and chat ID.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Edit config with your Telegram credentials
nano config.yaml

# Test Telegram connection
python monitor.py --test-telegram

# Do a dry run (prints results, no notifications)
python monitor.py --test

# Run once (with notifications)
python monitor.py

# Run continuously (every hour)
python monitor.py --loop

# See recent finds
python monitor.py --recent
```

## Running in the Background

### Option A: tmux/screen
```bash
tmux new -s workshop
python monitor.py --loop
# Press Ctrl+B then D to detach
```

### Option B: Cron job (runs every hour)
```bash
crontab -e
# Add this line:
0 * * * * cd /path/to/workshop-monitor && python3 monitor.py >> monitor.log 2>&1
```

### Option C: systemd service
Create `/etc/systemd/system/workshop-monitor.service`:
```ini
[Unit]
Description=Workshop Listing Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/workshop-monitor
ExecStart=/usr/bin/python3 monitor.py --loop
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable workshop-monitor
sudo systemctl start workshop-monitor
```
