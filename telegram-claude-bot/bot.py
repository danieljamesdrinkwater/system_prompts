#!/usr/bin/env python3
"""Telegram bot that lets you chat with an AI via OpenRouter."""

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
from openai import OpenAI

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-r1:free")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Per-chat conversation history: {chat_id: [{"role": ..., "content": ...}, ...]}
conversations: dict[int, list[dict]] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Hello! I'm a bot powered by AI. Send me any message and I'll respond.\n\n"
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
    """Forward user messages to AI and reply with the response."""
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
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=history,
        )
        assistant_text = response.choices[0].message.content or ""

        # Strip <think>...</think> blocks from reasoning models
        import re
        assistant_text = re.sub(r"<think>.*?</think>", "", assistant_text, flags=re.DOTALL).strip()

        history.append({"role": "assistant", "content": assistant_text})

        # Telegram has a 4096-char message limit; split if needed
        for i in range(0, len(assistant_text), 4096):
            await update.message.reply_text(assistant_text[i : i + 4096])

    except Exception as e:
        logger.error("API error: %s", e)
        await update.message.reply_text(f"API error: {e}")


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
