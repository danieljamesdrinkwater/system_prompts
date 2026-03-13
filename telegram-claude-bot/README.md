# Telegram Claude Bot

Chat with Claude through Telegram via [@api_coder_bot](https://t.me/api_coder_bot).

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   - `TELEGRAM_BOT_TOKEN` – from BotFather
   - `ANTHROPIC_API_KEY` – from console.anthropic.com

3. Run:
   ```bash
   python bot.py
   ```

## Commands

| Command  | Description                    |
|----------|--------------------------------|
| `/start` | Welcome message                |
| `/new`   | Clear conversation history     |
| `/model` | Show current Claude model      |

## Environment Variables

| Variable            | Default                        | Description              |
|---------------------|--------------------------------|--------------------------|
| `TELEGRAM_BOT_TOKEN`| *(required)*                   | Telegram bot token       |
| `ANTHROPIC_API_KEY` | *(required)*                   | Anthropic API key        |
| `CLAUDE_MODEL`      | `claude-sonnet-4-20250514`     | Claude model to use      |
| `MAX_HISTORY`       | `20`                           | Max messages to keep     |
