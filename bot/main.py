import httpx
from bot.utils.config import get_settings
from bot.utils.logger import logger
from bot.utils.prompts import HELP_MESSAGE, START_MESSAGE, CONNECT_MESSAGE, RESTART_MESSAGE
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LoginUrl
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ApplicationBuilder,
    CallbackQueryHandler,
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
        """Handle /start command and deep links"""
        
        
        await update.message.reply_text(START_MESSAGE)


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(HELP_MESSAGE)

    async def get_user_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.message.from_user.id
            response = await self.http_client.get(
                f"{settings.API_BASE_URL}/threads/user_account",
                params={"user_id": user_id}
            )
            account_data = response.json()
            
            if account_data.get("status") == "error":
                await update.message.reply_text(f"Error: {account_data.get('message')}")
                return
                
            # Format the account data into a readable message
            logger.info(f"Account data: {account_data}")
            
            message = f"**Threads Account Info**\nUsername: @{account_data.get('username')}\nBio:\n{account_data.get('biography', 'No bio')}"
            
            await update.message.reply_photo(
                photo=account_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in get_user_account: {str(e)}")
            await update.message.reply_text("Sorry, there was an error getting your account information.")

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with inline buttons for platform connection."""
        user_id = update.message.from_user.id
        
        is_threads_connected = await self.http_client.get(settings.API_BASE_URL + "/auth/threads/is_connected", params={"user_id": user_id})
        is_twitter_connected = False
        
        threads_auth_url = None
        twitter_auth_url = None
        
        if not is_threads_connected:
            threads_auth_url = await self.http_client.get(settings.API_BASE_URL + "/auth/threads/connect", params={"user_id": user_id})
            if threads_auth_url.json().get("url"):
                context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url.json().get("url")
        else:
            threads_auth_url = settings.API_BASE_URL + "/auth/threads/disconnect"
            context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url

        if not is_twitter_connected:
            twitter_auth_url = "https://x.com/login"
            if twitter_auth_url:
                context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url
        else:
            twitter_auth_url = "https://x.com/login"
            if twitter_auth_url:
                context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url
        
        keyboard = [
            [
                InlineKeyboardButton("🔗 Connect Threads", callback_data=f"connect_threads_{user_id}") if not is_threads_connected else InlineKeyboardButton("⛓️‍💥‍ Disconnect Threads", callback_data=f"disconnect_threads_{user_id}"),
                InlineKeyboardButton("🔗 Connect Twitter", callback_data=f"connect_twitter_{user_id}") if not is_twitter_connected else InlineKeyboardButton("⛓️‍💥 Disconnect Twitter", callback_data=f"disconnect_twitter_{user_id}"),
            ],
        ]


        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(CONNECT_MESSAGE, reply_markup=reply_markup)

    async def connect_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks from inline keyboard."""
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state
        
        # Extract action and user_id from callback_data
        action, platform, user_id = query.data.split('_')
        auth_url = context.user_data.get(f'{platform}_auth_url_{user_id}')
        
        keyboard = [
            [
                InlineKeyboardButton("🔐 Authenticate", url=auth_url, callback_data=f"authenticate_{user_id}")
            ],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if platform == "threads":
            # Open auth URL in browser
            await query.delete_message()
            # Redirect user to auth URL
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Click here to connect your Threads account:",
                connect_timeout=120,
                reply_markup=reply_markup
            )
        elif platform == "twitter":
            # Open auth URL in browser
            await query.delete_message()
            # Redirect user to auth URL
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Click here to connect your X/Twitter account:",
                connect_timeout=120,
                reply_markup=reply_markup
            )
        
        del context.user_data[f'{platform}_auth_url_{user_id}']
        
    async def disconnect_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks from inline keyboard."""
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state
        
        # Extract action and user_id from callback_data
        action, platform, user_id = query.data.split('_')
        auth_url = context.user_data.get(f'{platform}_auth_url_{user_id}')
        
        keyboard = [
            [
                InlineKeyboardButton("🔐 Confirm", url=auth_url, callback_data=f"disconnect_{user_id}")
            ],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if platform == "threads":
            # Open auth URL in browser
            await query.delete_message()
            # Redirect user to auth URL
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Click here to disconnect your Threads account:",
                connect_timeout=120,
                reply_markup=reply_markup
            )
        elif platform == "twitter":
            # Open auth URL in browser
            await query.delete_message()
            # Redirect user to auth URL
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Click here to disconnect your X/Twitter account:",
                connect_timeout=120,
                reply_markup=reply_markup
            )
        
        del context.user_data[f'{platform}_auth_url_{user_id}']
            

    async def authorize_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle authentication callback after successful login."""
        logger.info(f"Callback received: {update.message.text}")
        
        # Get the full command text
        command_text = update.message.text
        if not command_text:
            return
            
        # Extract the auth parameter (everything after &)
        auth_param = command_text.split('&')[-1] if '&' in command_text else None
        if not auth_param:
            return
            
        user_id = None
        
        if auth_param.startswith('auth_success_'):
            user_id = auth_param.split('_')[-1]
            if str(update.effective_user.id) == user_id:
                # Get account info to show in success message
                try:
                    response = await self.http_client.get(
                        f"{settings.API_BASE_URL}/threads/user_account",
                        params={"user_id": user_id}
                    )
                    account_data = response.json()
                    
                    if account_data.get("status") != "error":
                        success_message = (
                            "✅ Successfully connected your Threads account!\n\n"
                            f"*Connected Account*\n"
                            f"Username: @{account_data.get('username')}\n"
                        )
                        
                        # Send success message with profile picture
                        await update.message.reply_photo(
                            photo=account_data.get("profile_picture_url"),
                            caption=success_message,
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text("✅ Successfully connected your Threads account!")
                except Exception as e:
                    logger.error(f"Error fetching account info: {str(e)}")
                    await update.message.reply_text("✅ Successfully connected your Threads account!")
                
                # Clean up any previous connection messages
                if 'last_connect_message_id' in context.user_data:
                    try:
                        await context.bot.edit_message_reply_markup(
                            chat_id=update.effective_chat.id,
                            message_id=context.user_data['last_connect_message_id'],
                            reply_markup=None
                        )
                    except Exception as e:
                        logger.error(f"Error cleaning up messages: {str(e)}")
                return
                
        elif auth_param.startswith('auth_error_'):
            user_id = auth_param.split('_')[-1]
            if str(update.effective_user.id) == user_id:
                error_message = (
                    "❌ Failed to connect your Threads account.\n"
                    "Please try again using the /connect command."
                )
                if auth_param == 'auth_error_invalid_state':
                    error_message = (
                        "❌ Authentication session expired or invalid.\n"
                        "Please try again using the /connect command."
                    )
                await update.message.reply_text(error_message)
                return

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
            
    async def post_thread(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Post a thread to Threads and read the query params
        logger.info(f"Posting thread to Threads for user {update.message.from_user.id}")
        logger.info(f"Message: {update.message}")
        try:
            user_id = update.message.from_user.id
            message = update.message.text.replace("/post ", "")
            if update.message.photo:
                image_url = update.message.photo[-1].file_id
            else:
                image_url = None
            
            response = await self.http_client.post(
                f"{settings.API_BASE_URL}/threads/post",
                params={"user_id": user_id, "message": message, "image_url": image_url},
                timeout=30
            )
            
            if response.json().get("status") == "success":
                await update.message.reply_text("✅ Thread posted successfully!")
            else:
                await update.message.reply_text("❌ Failed to post thread. Please try again.")
        except Exception as e:
            logger.error(f"Error posting thread: {str(e)}")
            await update.message.reply_text("❌ Failed to post thread. Please try again.")


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
            CallbackQueryHandler(self.connect_callback, pattern="^connect_")
        )
        self.application.add_handler(
            CommandHandler("connect_callback", self.authorize_callback, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CallbackQueryHandler(self.disconnect_callback, pattern="^disconnect_")
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
            CommandHandler("post", self.post_thread, filters=allowed_users_filter)
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
