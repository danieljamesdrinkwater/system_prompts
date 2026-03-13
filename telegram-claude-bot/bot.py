#!/usr/bin/env python3
"""Telegram bot that lets you chat with Claude (Anthropic API)."""

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import anthropic

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Per-chat conversation history: {chat_id: [{"role": ..., "content": ...}, ...]}
conversations: dict[int, list[dict]] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Hello! I'm a bot powered by Claude. Send me any message and I'll respond.\n\n"
        "Commands:\n"
        "/new - Start a fresh conversation\n"
        "/model - Show current model\n"
    )


async def new_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - clear conversation history."""
    chat_id = update.effective_chat.id
    conversations.pop(chat_id, None)
    await update.message.reply_text("Conversation cleared. Send a new message to start fresh.")


async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /model command."""
    await update.message.reply_text(f"Current model: {MODEL}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward user messages to Claude and reply with the response."""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if not user_text:
        return

    # Build conversation history
    history = conversations.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})

    # Trim to keep history manageable
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    # Send typing indicator
    await update.message.chat.send_action("typing")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=history,
        )
        assistant_text = response.content[0].text
        history.append({"role": "assistant", "content": assistant_text})

        # Telegram has a 4096-char message limit; split if needed
        for i in range(0, len(assistant_text), 4096):
            await update.message.reply_text(assistant_text[i : i + 4096])

    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        await update.message.reply_text(f"API error: {e.message}")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        await update.message.reply_text("Something went wrong. Please try again.")


def main() -> None:
    """Start the bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_conversation))
    app.add_handler(CommandHandler("model", show_model))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
