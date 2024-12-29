import httpx
from bot.config import get_settings
from bot.utils.logger import logger
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

def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    
class TelegramBot:
    def __init__(self):
        logger.info("Starting up bot...")
        self.application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
        self.api_base_url = settings.API_BASE_URL
        self.http_client = httpx.AsyncClient()
        logger.info("Bot initialized")
        
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Health check started")
        logger.info(context)
        logger.info(update)
        try:
            bot_response = await context.bot.get_me()
            api_response = await self.http_client.get(settings.API_BASE_URL + "/health")
            logger.info(f"API response: {api_response}")
            await update.message.reply_text(f"Bot check passed: {bot_response}.\n\nBackend check passed: {api_response.json()}")
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            await update.message.reply_text("An error occurred during the health check. Please try again later.")
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(START_MESSAGE)


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(HELP_MESSAGE)

    async def get_user_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.message.from_user.id
            response = await self.http_client.get(
                f"{settings.API_BASE_URL}/threads/get_user_account",
                params={"user_id": user_id}
            )
            account_data = response.json()
            
            if account_data.get("status") == "error":
                await update.message.reply_text(f"Error: {account_data.get('message')}")
                return
                
            # Format the account data into a readable message
            logger.info(f"Account data: {account_data}")
            message = (
                f"*Threads Account Info*\n"
                f"Username: @{account_data.get('username')}\n"
                f"Bio:\n{account_data.get('biography', 'No bio')}"
            )
            
            await update.message.reply_photo(
                photo=account_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in get_user_account: {str(e)}")
            await update.message.reply_text("Sorry, there was an error getting your account information.")

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        auth_url = await self.http_client.get(settings.API_BASE_URL + "/auth/threads/connect", params={"user_id": user_id})
        logger.info(f"Auth URL: {auth_url.json()}")
        await update.message.reply_text(CONNECT_MESSAGE.format(auth_url=auth_url.json().get("url")))


    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(RESTART_MESSAGE)
        

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        user = update.effective_user
        message_id = message.message_id

        logger.info(f"User {user.username} ({user.id}) sent a message.")

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


    # Bot Handlers
    def add_handlers(self):
        # Commands with user restriction
        allowed_users_filter = filters.User(username=settings.ALLOWED_USERS)
        self.application.add_handler(
            CommandHandler("start", self.start_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("help", self.help_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("connect", self.connect_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("restart", self.restart_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("account", self.get_user_account, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("health", self.health_check, filters=allowed_users_filter)
        )
        self.application.add_handler(
            MessageHandler(filters.ALL & allowed_users_filter, self.handle_message)
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
