import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Define project root and construct path to .env file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
dotenv_path = PROJECT_ROOT / 'config' / 'config.env'
load_dotenv(dotenv_path=dotenv_path)

# --- Custom Color Formatter ---
class ColorFormatter(logging.Formatter):
    """A custom formatter to add color to command logs."""
    COLORS = {
        'BLUE': '\033[94m',
        'RESET': '\033[0m'
    }

    def format(self, record):
        log_message = super().format(record)
        # Add color if the log is for a command action
        if "started the bot" in record.msg or "used the /done command" in record.msg:
            return f"{self.COLORS['BLUE']}{log_message}{self.COLORS['RESET']}"
        return log_message

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Apply the color formatter
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.propagate = False  # Prevent duplicate logs to the root logger

# Silence httpx logger to filter out "200 OK" messages
logging.getLogger("httpx").setLevel(logging.WARNING)

# Get bot token from environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in config.env!")
    exit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot.")
    # Create inline keyboard with Dropbox upload link
    keyboard = [
        [InlineKeyboardButton("📤 Upload", url="https://drive.google.com/drive/folders/1OK3RL0Zh7CxaxJs8WkFYMp12WE7JEw1H?usp=drive_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send first message with upload button
    await update.message.reply_text(
        "Upload your video here!",
        reply_markup=reply_markup
    )
    
    # Send second message with clickable /Done text
    await update.message.reply_text("Click here after uploading video 👉 /Done ✅")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) used the /done command.")
    await update.message.reply_text("⚙️ Your video is being processed, you will hear from us shortly!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log any text message sent by the user."""
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"User {user.id} ({user.username}) sent message: \"{message_text}\"")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()  # Answer the callback query
    
    # Get the callback data from the button
    callback_data = query.data
    
    if callback_data == "done":
        logger.info(f"User {user.id} ({user.username}) clicked the 'Done' button.")
        await query.edit_message_text("⚙️ Your video is being processed, you will hear from us shortly!")

def main():
    logger.info("Starting Telegram bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done_command))
    # Add a handler for all other text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Bot is running and ready to receive messages!")
    app.run_polling()

if __name__ == "__main__":
    main()
