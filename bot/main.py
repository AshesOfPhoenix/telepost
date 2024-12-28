import httpx
import logging
from bot.config import get_settings

from bot.prompts import HELP_MESSAGE, START_MESSAGE, CONNECT_MESSAGE, RESTART_MESSAGE
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ApplicationBuilder,
    filters,
)

settings = get_settings()

from bot.handlers.gpt_message_handler import handle_response

print("Starting up bot...")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def get_message_content(message):
    if message.text:
        return message.text, "text"
    elif message.photo:
        return message.photo[-1].file_id, "photo"
    elif message.document:
        return message.document.file_id, "document"
    elif message.voice:
        return message.voice.file_id, "voice"
    elif message.audio:
        return message.audio.file_id, "audio"
    elif message.video:
        return message.video.file_id, "video"
    else:
        return None, "unknown"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CONNECT_MESSAGE)


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(RESTART_MESSAGE)
    

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    message_id = message.message_id

    logging.info(f"User {user.username} ({user.id}) sent a message.")

    content, content_type = get_message_content(message)

    if content_type == "unknown":
        await message.reply_text("Sorry, I can't process this type of message yet.")
        return

    if content_type == "text":
        response = await handle_response(content, user, message_id, content_type)
    else:
        # For media files, download the file
        file = await context.bot.get_file(content)
        file_path = await file.download_to_drive()
        # Pass the file path to handle_response
        response = await handle_response(file_path, user, message_id, content_type)

    if type(response) == str and len(response) > 1000:
        file_name = f"result.md"
        with open(file_name, "w") as file:
            file.write(response)
        await message.reply_document(file_name)

    if type(response) == str:
        await message.reply_markdown(response)
    else:
        await message.reply_markdown(response)


def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    
    
class TelegramBot:
    def __init__(self):
        self.application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
        self.api_base_url = settings.API_BASE_URL
        self.http_client = httpx.AsyncClient()
        
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot_response = await context.bot.get_me()
        api_response = await self.http_client.get(settings.API_BASE_URL + "/health")
        logging.info(f"API response: {api_response}")
        await update.message.reply_text(f"Bot check passed: {bot_response}.\n\nBackend check passed: {api_response.json()}")

    # Bot Handlers
    def add_handlers(self):
        # Commands with user restriction
        allowed_users_filter = filters.User(username=settings.ALLOWED_USERS)
        self.application.add_handler(
            CommandHandler("start", start_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("help", help_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("connect", connect_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("restart", restart_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("health", self.health_check, filters=allowed_users_filter)
        )
        self.application.add_handler(
            MessageHandler(filters.ALL & allowed_users_filter, handle_message)
        )
        
    # API Calls
    async def auth_threads(self):
        response = await self.http_client.post(
            self.api_base_url + "/auth/threads",
            json={"username": "kikoems", "password": "123456"},
        )
        return response.json()

# Main
async def start_bot():
    bot = TelegramBot()
    bot.add_handlers()
    bot.application.add_error_handler(error_handler)
    bot.application.run_polling()

# Run
if __name__ == "__main__":
    bot = TelegramBot()
    bot.add_handlers()
    bot.application.add_error_handler(error_handler)
    bot.application.run_polling()
