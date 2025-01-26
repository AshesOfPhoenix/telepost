import httpx
from bot.utils.config import get_settings
from bot.utils.logger import logger
from bot.utils.prompts import HELP_MESSAGE, POST_SUCCESS_MESSAGE, START_MESSAGE, CONNECT_MESSAGE, RESTART_MESSAGE, THREADS_ACCOUNT_INFO_MESSAGE, NO_ACCOUNT_MESSAGE, TWITTER_ACCOUNT_INFO_MESSAGE
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
        self.API_PUBLIC_URL = settings.API_PUBLIC_URL
        self.http_client = httpx.AsyncClient(
            headers={
                settings.API_KEY_HEADER_NAME.strip('"'): settings.API_KEY,
                "Host": settings.API_PUBLIC_URL.split("://")[1],
                "User-Agent": "TelegramBot/1.0"
            },
            timeout=30,
            verify=True
        )
        logger.info("✅ Bot initialized")
        
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Health check started")
        logger.info(context)
        logger.info(update)
        try:
            bot_response = await context.bot.get_me()
            api_response = await self.http_client.get(settings.API_PUBLIC_URL + "/health")
            logger.info(f"API response: {api_response}")
            await update.message.reply_text(f"Bot check passed: {bot_response}.\n\nBackend check passed: {api_response.json()}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            await update.message.reply_text("An error occurred during the health check. Please try again later.", parse_mode='Markdown')
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command and deep links"""
        await update.message.reply_text(START_MESSAGE, parse_mode='Markdown')

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.", parse_mode='Markdown')


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')

    async def get_user_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.message.from_user.id
            if not user_id:
                raise Exception("User ID is required")
        except Exception as e:
            logger.error(f"Error in get_user_account: {str(e)}")
            await update.message.reply_text("Sorry, there was an error getting your account information.", parse_mode='Markdown')
            return
        
        try:
            
            # Get Threads account data
            threads_response = await self.http_client.get(
                f"{settings.API_PUBLIC_URL}/threads/user_account",
                params={"user_id": user_id}
            )
            threads_account_data = threads_response.json()
            
            if threads_response.status_code != 200:
                raise Exception(threads_response.text, threads_response.status_code)
            
            if threads_account_data.get("status") == "missing":
                raise Exception("User not connected to Threads")
                
            # Format the account data into a readable message
            logger.info(f"Threads account data: {threads_account_data}")
            
            message = THREADS_ACCOUNT_INFO_MESSAGE.format(
                username=threads_account_data.get("username"),
                bio=threads_account_data.get("biography", "No bio"),
                followers_count=threads_account_data.get("followers_count"),
                likes=threads_account_data.get("likes"),
                replies=threads_account_data.get("replies"),
                reposts=threads_account_data.get("reposts"),
                quotes=threads_account_data.get("quotes"),
            )
            
            await update.message.reply_photo(
                photo=threads_account_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
        
        except Exception as e:
            if str(e) == "User not connected to Threads":
                await update.message.reply_text(NO_ACCOUNT_MESSAGE.format(platform="Threads"), parse_mode='Markdown')
            else:
                logger.error(f"Error in get_user_account: {str(e)}")
                await update.message.reply_text("Sorry, there was an error getting your Threads account information.", parse_mode='Markdown')
            
        try:
            # Get Twitter account data
            twitter_response = await self.http_client.get(
                f"{settings.API_PUBLIC_URL}/twitter/user_account",
                params={"user_id": user_id}
            )
            twitter_account_data = twitter_response.json()
            logger.info(f"Twitter account data: {twitter_account_data}")
            
            if twitter_response.status_code != 200:
                raise Exception(twitter_response.text, twitter_response.status_code)
            
            if twitter_account_data.get("status") == "missing":
                raise Exception("User not connected to Twitter")
            
            if twitter_account_data.get("status") == "error":
                raise Exception(twitter_account_data.get("message"))
            
            logger.info(f"Twitter account data: {twitter_account_data}")
            
            # If verified_type is "blue", add a verified badge
            verified_type = twitter_account_data.get("verified_type")
            verified_badge = "✅" if verified_type == "blue" else ""
            
            # Format the account data into a readable message
            message = TWITTER_ACCOUNT_INFO_MESSAGE.format(
                name=twitter_account_data.get("name"),
                username=twitter_account_data.get("username"),
                
                verified_badge=verified_badge,
                # verified_type=verified_type,
                
                location=twitter_account_data.get("location"),
                protected=twitter_account_data.get("protected"),
                created_at=twitter_account_data.get("created_at"),
                
                bio=twitter_account_data.get("biography", "No bio"),
                
                followers_count=twitter_account_data.get("metrics").get("followers_count"),
                following_count=twitter_account_data.get("metrics").get("following_count"),
                tweet_count=twitter_account_data.get("metrics").get("tweet_count"),
                listed_count=twitter_account_data.get("metrics").get("listed_count"),
                like_count=twitter_account_data.get("metrics").get("like_count"),
                media_count=twitter_account_data.get("metrics").get("media_count")
            )
            
            await update.message.reply_photo(
                photo=twitter_account_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in get_user_account: {str(e)}")
            if str(e) == "User not connected to Twitter":
                await update.message.reply_text(NO_ACCOUNT_MESSAGE.format(platform="Twitter"), parse_mode='Markdown')
            else:
                await update.message.reply_text("Sorry, there was an error getting your Twitter account information.", parse_mode='Markdown')

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with inline buttons for platform connection."""
        user_id = update.message.from_user.id
        
        if not user_id:
            await update.message.reply_text("❌ An error occurred while connecting your account. Please try again.", parse_mode='Markdown')
            return
        
        is_threads_connected = False
        is_twitter_connected = False
        threads_auth_url = None
        twitter_auth_url = None
        
        try:
            threads_response = await self.http_client.get(settings.API_PUBLIC_URL + "/auth/threads/is_connected", params={"user_id": user_id})
            logger.info(f"Threads response status: {threads_response.status_code}")
            logger.info(f"Threads response text: {threads_response.text}")
            threads_response.raise_for_status()
            logger.info(f"Is threads connected: {threads_response.json()}")
            is_threads_connected = threads_response.json()
            
            twitter_response = await self.http_client.get(settings.API_PUBLIC_URL + "/auth/twitter/is_connected", params={"user_id": user_id})
            logger.info(f"Twitter response status: {twitter_response.status_code}")
            logger.info(f"Twitter response text: {twitter_response.text}")
            twitter_response.raise_for_status()
            logger.info(f"Is twitter connected: {twitter_response.json()}")
            is_twitter_connected = twitter_response.json()
            
            if not is_threads_connected:
                threads_auth_url = await self.http_client.get(settings.API_PUBLIC_URL + "/auth/threads/connect", params={"user_id": user_id})
                if threads_auth_url.json().get("url"):
                    context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url.json().get("url")
            else:
                threads_auth_url = f"{settings.API_PUBLIC_URL}/auth/threads/disconnect?user_id={user_id}"
                context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url

            if not is_twitter_connected:
                twitter_auth_url = await self.http_client.get(settings.API_PUBLIC_URL + "/auth/twitter/connect", params={"user_id": user_id})
                if twitter_auth_url.json().get("url"):
                    context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url.json().get("url")
            else:
                twitter_auth_url = f"{settings.API_PUBLIC_URL}/auth/twitter/disconnect?user_id={user_id}"
                context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url
                
        except Exception as e:
            logger.error(f"Error in connect_command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while connecting your account. Please try again.", parse_mode='Markdown')
            return
            
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔗 Connect Threads", 
                    callback_data=f"connect_threads_{user_id}"
                ) if not is_threads_connected else InlineKeyboardButton(
                    "⛓️‍💥‍ Disconnect Threads", 
                    callback_data=f"disconnect_threads_{user_id}"
                ),
                InlineKeyboardButton(
                    "🔗 Connect Twitter", 
                    callback_data=f"connect_twitter_{user_id}"
                ) if not is_twitter_connected else InlineKeyboardButton(
                    "⛓️‍💥 Disconnect Twitter", 
                    callback_data=f"disconnect_twitter_{user_id}"
                ),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(CONNECT_MESSAGE, reply_markup=reply_markup, parse_mode='Markdown')

    async def connect_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks from inline keyboard."""
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state
        
        logger.info(f"Callback data: {query.data}")
        
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
        
        try:
            if platform == "threads":
                # Make direct HTTP request to disconnect endpoint
                response = await self.http_client.post(
                    f"{settings.API_PUBLIC_URL}/auth/threads/disconnect",
                    params={"user_id": user_id}
                )
                
                if response.status_code == 200:
                    # Delete the original message with the keyboard
                    await query.delete_message()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="✅ Successfully disconnected your Threads account!"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="❌ Failed to disconnect your account. Please try again."
                    )
                    
            elif platform == "twitter":
                # Handle Twitter disconnect similarly
                response = await self.http_client.post(
                    f"{settings.API_PUBLIC_URL}/auth/twitter/disconnect",
                    params={"user_id": user_id}
                )
                logger.info(f"Twitter disconnect response: {response.json()}")
                
                if response.status_code == 200:
                    await query.delete_message()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="✅ Successfully disconnected your Twitter account!"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="❌ Failed to disconnect your account. Please try again."
                    )
    

        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ An error occurred while disconnecting your account. Please try again."
            )
            

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
                        f"{settings.API_PUBLIC_URL}/threads/user_account",
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
                        await update.message.reply_text("✅ Successfully connected your Threads account!", parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Error fetching account info: {str(e)}")
                    await update.message.reply_text("❌ Failed to connect your Threads account.", parse_mode='Markdown')
                
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
                await update.message.reply_text(error_message, parse_mode='Markdown')
                return

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(RESTART_MESSAGE, parse_mode='Markdown')
        

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        user = update.effective_user
        message_id = message.message_id

        logger.info(f"User {user.username} ({user.id}) sent a message with id {message_id} and content {message.text}.")

        content, content_type = get_message_content(message)

        if content_type == "unknown":
            await message.reply_text("Sorry, I can't process this type of message yet.", parse_mode='Markdown')
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
            
    async def post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Post a thread to Threads and read the query params
        logger.info(f"Begin postting a message to Threads for user {update.message.from_user.id}")
        user_id = update.message.from_user.id
        message = " ".join(context.args) # Get the message from the command args - Does not correctly handle spaces and new lines
        message = update.message.text_markdown.replace("/post", "") # Get the message from the command text
        
        message = message.strip()
        is_message_empty = len(message) == 0 or message == None
        
        if len(update.message.photo) > 0:
            image_url = update.message.photo
        else:
            image_url = None
            
        logger.info(f"Message: {message} - Message Empty: {is_message_empty} - Message Length: {len(message)}. Photo: {update.message.photo} - {image_url}")
            
        if is_message_empty and not image_url:
            await update.message.reply_text("❌ Please provide an text or image to post.", parse_mode='Markdown')
            return
        
        try:
            response = await self.http_client.post(
                f"{settings.API_PUBLIC_URL}/threads/post",
                params={"user_id": user_id, "message": message, "image_url": image_url},
                timeout=30
            )
            logger.info(f"Response: {response.json()}")
            
            if response.json().get("status") == "success":
                thread_url = response.json().get("thread").get("permalink")
                # Parse 2025-01-04T11:39:58+0000 to 2025-01-04 11:39:58
                thread_timestamp = response.json().get("thread").get("timestamp").replace("T", " ").replace("+0000", "")
                logger.info(f"Thread URL: {thread_url}")
                
                success_message = POST_SUCCESS_MESSAGE.format(post_url=thread_url, timestamp=thread_timestamp, platform="Threads")
                await update.message.reply_text(success_message, parse_mode='Markdown')
            elif response.json().get("status") == "missing":
                await update.message.reply_text("❌ User not connected to Threads", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to post a thread. Please try again.", parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error posting thread: {str(e)}")
            await update.message.reply_text("❌ Failed to post a thread. Please try again.", parse_mode='Markdown')
            
        logger.info(f"Begin postting a message to Twitter for user {update.message.from_user.id}")
        try:
            response = await self.http_client.post(
                f"{settings.API_PUBLIC_URL}/twitter/post",
                params={"user_id": user_id, "message": message, "image_url": image_url},
                timeout=30
            )
            
            if response.json().get("status") == "success":
                # {'edit_history_tweet_ids': ['1875842406307737626'], 'id': '1875842406307737626', 'text': 'yolo'}
                logger.info(f"Response: {response.json()}")
                
                tweet = response.json().get("tweet")
                tweet_id = tweet.get("id")
                tweet_text = tweet.get("text")
                tweet_url = tweet.get("permalink")
                tweet_timestamp = tweet.get("timestamp")
                
                success_message = POST_SUCCESS_MESSAGE.format(post_url=tweet_url, timestamp=tweet_timestamp, platform="Twitter")
                await update.message.reply_text(success_message, parse_mode='Markdown')
            elif response.json().get("status") == "missing":
                await update.message.reply_text("❌ User not connected to Twitter", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to post a tweet. Please try again.", parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            await update.message.reply_text("❌ Failed to post a tweet. Please try again.", parse_mode='Markdown')


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
            CommandHandler("callback", self.authorize_callback, filters=allowed_users_filter)
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
            CommandHandler("post", self.post, filters=allowed_users_filter)
        )
        self.application.add_handler(
            MessageHandler(filters.ALL & allowed_users_filter, self.handle_message)
        )
        self.application.add_handler(
            CommandHandler("unknown", self.unknown, filters=filters.COMMAND)
        )

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
