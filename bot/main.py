import httpx
import telegram
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
import json
from bot.utils.exceptions import APIError, ConnectionError, ExpiredCredentialsError

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the Telegram Bot."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            if isinstance(context.error, httpx.RequestError):
                await update.effective_message.reply_text(
                    "❌ Network error occurred. Please try again later.",
                    parse_mode='Markdown'
                )
            elif isinstance(context.error, httpx.TimeoutException):
                await update.effective_message.reply_text(
                    "⏳ Request timed out. Please try again.",
                    parse_mode='Markdown'
                )
            elif isinstance(context.error, telegram.error.NetworkError):
                await update.effective_message.reply_text(
                    "📡 Telegram network error. Please try again later.",
                    parse_mode='Markdown'
                )
            elif isinstance(context.error, telegram.error.Forbidden):
                await update.effective_message.reply_text(
                    "🔒 Bot authentication failed. Please contact the administrator.",
                    parse_mode='Markdown'
                )
            else:
                await update.effective_message.reply_text(
                    "❌ An unexpected error occurred. Please try again later or contact support.",
                    parse_mode='Markdown'
                )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")


class TelegramBot:
    def __init__(self):
        logger.info("Starting up bot...")
        self.application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
        self.API_PUBLIC_URL = settings.API_PUBLIC_URL
        api_host = settings.API_PUBLIC_URL.split("://")[1]
        logger.info(f"API host: {api_host}")
        self.http_client = httpx.AsyncClient(
            headers={
                settings.API_KEY_HEADER_NAME.strip('"'): settings.API_KEY,
                "Host": api_host,
                "User-Agent": "TelegramBot/1.0"
            },
            timeout=httpx.Timeout(
                connect=5.0, 
                read=30.0,   
                write=30.0,  
                pool=30.0      
            ),
            verify=True
        )
        logger.info(f"Allowed users: {settings.ALLOWED_USERS}")
        logger.info("✅ Bot initialized")
        
    async def get(self, endpoint: str, params: dict = None):
        response = await self.http_client.get(self.API_PUBLIC_URL + endpoint, params=params)
        return response
    

    async def post(self, endpoint: str, params: dict = None):
        response = await self.http_client.post(self.API_PUBLIC_URL + endpoint, params=params)
        return response
        

    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /health command.
        
        Description:
            This method checks the health of the bot and the backend.
        
        Args:
            update: Update object
            context: Context object
        """
        logger.info("Health check started")
        logger.info(context)
        logger.info(update)
        try:
            bot_response = await context.bot.get_me()
            api_response = await self.get("/health")
            
            if api_response.status_code != 200:
                await update.message.reply_text(
                    f"Bot check passed: {bot_response}.\n\n❌ Backend check failed: {api_response.status_code} - {api_response.text}", 
                    parse_mode='Markdown'
                )
                return
                
            api_data = api_response.json()
            await update.message.reply_text(
                f"✅ Bot check passed: {bot_response}.\n\n✅ Backend check passed: {api_data}", 
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            await update.message.reply_text("An error occurred during the health check. Please try again later.", parse_mode='Markdown')
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /start command and deep links
        
        Description:
            This method sends a start message to the user.
        
        Args:
            update: Update object
            context: Context object
        """
        await update.message.reply_text(START_MESSAGE, parse_mode='Markdown')

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.", parse_mode='Markdown')


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /help command.
        
        Description:
            This method sends a help message to the user.
        
        Args:
            update: Update object
            context: Context object
        """
        await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')

    async def get_user_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /account command.
        
        Description:
            This method gets the user's account information from Threads and Twitter.
        
        Args:
            update: Update object
            context: Context object
        """
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
            response = await self.get("/threads/user_account", params={"user_id": user_id})
            response_data = await self.handle_api_response(response, "Threads")
            
            logger.info(f"Threads account data: {response_data}")
            
            threads_data = response_data.get("data")
            
            # Format the account data into a readable message
            message = THREADS_ACCOUNT_INFO_MESSAGE.format(
                username=threads_data.get("username"),
                bio=threads_data.get("biography", "No bio"),
                followers_count=threads_data.get("followers_count", 0),
                likes=threads_data.get("likes", 0),
                replies=threads_data.get("replies", 0),
                reposts=threads_data.get("reposts", 0),
                quotes=threads_data.get("quotes", 0),

            )
            
            await update.message.reply_photo(
                photo=threads_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
        
        except ConnectionError as e:
            logger.info(f"User not connected to {e.platform}: {e.message}")
            await update.message.reply_text(
                f"❌ User not connected to {e.platform}. Please connect using /connect",
                parse_mode='Markdown'
            )
            

        except ExpiredCredentialsError as e:
            logger.warning(f"Expired credentials for {e.platform}: {e.message}")
            await update.message.reply_text(
                f"⚠️ Your {e.platform} connection has expired. Please reconnect using /connect",
                parse_mode='Markdown'
            )
            
        except APIError as e:
            logger.error(f"API Error: {e.message}", extra={"details": e.details})
            await update.message.reply_text(
                f"❌ Error with {e.platform}: {e.message}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later.",
                parse_mode='Markdown'
            )
            
        try:
            # Get Twitter account data
            response = await self.get("/twitter/user_account", params={"user_id": user_id})
            response_data = await self.handle_api_response(response, "Twitter")
            
            logger.info(f"Twitter account data: {response_data}")
            
            twitter_data = response_data.get("data")

            # If verified_type is "blue", add a verified badge
            verified_type = twitter_data.get("verified_type")
            verified_badge = "✅" if verified_type == "blue" else ""
            
            # Format the account data into a readable message
            message = TWITTER_ACCOUNT_INFO_MESSAGE.format(
                name=twitter_data.get("name"),
                username=twitter_data.get("username"),
                
                verified_badge=verified_badge,
                # verified_type=verified_type,
                
                location=twitter_data.get("location"),
                protected=twitter_data.get("protected"),
                created_at=twitter_data.get("created_at"),
                
                bio=twitter_data.get("biography", "No bio"),
                
                followers_count=twitter_data.get("metrics").get("followers_count"),
                following_count=twitter_data.get("metrics").get("following_count"),
                tweet_count=twitter_data.get("metrics").get("tweet_count"),
                listed_count=twitter_data.get("metrics").get("listed_count"),
                like_count=twitter_data.get("metrics").get("like_count"),
                media_count=twitter_data.get("metrics").get("media_count")
            )
            
            await update.message.reply_photo(
                photo=twitter_data.get("profile_picture_url"),
                caption=message,
                parse_mode='Markdown'
            )
            
        except ConnectionError as e:
            logger.info(f"User not connected to {e.platform}: {e.message}")
            await update.message.reply_text(
                f"❌ User not connected to {e.platform}. Please connect using /connect",
                parse_mode='Markdown'
            )
            

        except ExpiredCredentialsError as e:
            logger.warning(f"Expired credentials for {e.platform}: {e.message}")
            await update.message.reply_text(
                f"⚠️ Your {e.platform} connection has expired. Please reconnect using /connect",
                parse_mode='Markdown'
            )
            
        except APIError as e:
            logger.error(f"API Error: {e.message}", extra={"details": e.details})

            await update.message.reply_text(
                f"❌ Error with {e.platform}: {e.message}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later.",
                parse_mode='Markdown'
            )

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /connect command.
        
        Description:
            This method sends a message with inline buttons for platform connection.
        
        Args:
            update: Update object
            context: Context object
        """
        user_id = update.message.from_user.id
        
        if not user_id:
            await update.message.reply_text("❌ An error occurred while connecting your account. Please try again.", parse_mode='Markdown')
            return
        
        is_threads_connected = False
        is_twitter_connected = False
        threads_auth_url = None
        twitter_auth_url = None
        
        keyboard = [[]]
        
        try:
            threads_response = await self.get("/auth/threads/is_connected", params={"user_id": user_id})
            logger.info(f"Threads response status: {threads_response.status_code}")
            
           
            logger.info(f"Threads response text: {threads_response.text}")
            threads_response.raise_for_status()
            logger.info(f"Is threads connected: {threads_response.json()}")
            is_threads_connected = threads_response.json()
            
            if not is_threads_connected:
                threads_auth_url = await self.get("/auth/threads/connect", params={"user_id": user_id})
                if threads_auth_url.json().get("url"):
                    context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url.json().get("url")
            else:
                threads_auth_url = f"{self.API_PUBLIC_URL}/auth/threads/disconnect?user_id={user_id}"
                context.user_data[f'threads_auth_url_{user_id}'] = threads_auth_url
                
            keyboard[0].append(InlineKeyboardButton(
                "🔗 Connect Threads", 
                callback_data=f"connect_threads_{user_id}"
            ) if not is_threads_connected else InlineKeyboardButton(
                "⛓️‍💥‍ Disconnect Threads", 
                callback_data=f"disconnect_threads_{user_id}"
            ))
            
        except Exception as e:
            logger.error(f"Error in connect_command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while connecting your account. Please try again.", parse_mode='Markdown')
            
        try:
            twitter_response = await self.get("/auth/twitter/is_connected", params={"user_id": user_id})
            logger.info(f"Twitter response status: {twitter_response.status_code}")
            
            logger.info(f"Twitter response text: {twitter_response.text}")
            twitter_response.raise_for_status()
            logger.info(f"Is twitter connected: {twitter_response.json()}")
            is_twitter_connected = twitter_response.json()
            
            if not is_twitter_connected:
                twitter_auth_url = await self.get("/auth/twitter/connect", params={"user_id": user_id})
                if twitter_auth_url.json().get("url"):
                    context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url.json().get("url")
            else:
                twitter_auth_url = f"{self.API_PUBLIC_URL}/auth/twitter/disconnect?user_id={user_id}"
                context.user_data[f'twitter_auth_url_{user_id}'] = twitter_auth_url
                
            keyboard[0].append(InlineKeyboardButton(
                "🔗 Connect Twitter", 
                callback_data=f"connect_twitter_{user_id}"
            ) if not is_twitter_connected else InlineKeyboardButton(
                "⛓️‍💥 Disconnect Twitter", 
                callback_data=f"disconnect_twitter_{user_id}"
            ))
                
        except Exception as e:
            logger.error(f"Error in connect_command: {str(e)}")

            await update.message.reply_text("❌ An error occurred while connecting your account. Please try again.", parse_mode='Markdown')


        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(CONNECT_MESSAGE, reply_markup=reply_markup, parse_mode='Markdown')

    async def connect_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /connect callback.
        
        Description:
            This method first generates the auth URL for the platform and then sends it to the user via inline keyboard.
        
        Args:
            update: Update object
            context: Context object
        """
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
        """
        Handle /disconnect callback.
        
        Description:
            This method disconnects the user from the platform. This is trigered by the inline keyboard button.
        
        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state
        
        # Extract action and user_id from callback_data
        action, platform, user_id = query.data.split('_')
        
        try:
            if platform == "threads":
                # Make direct HTTP request to disconnect endpoint
                response = await self.post("/auth/threads/disconnect", params={"user_id": user_id})
                
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
                response = await self.post("/auth/twitter/disconnect", params={"user_id": user_id})
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
        """
        Handle authentication callback after successful login.
        
        Description:
            This method is triggered after the user has successfully authenticated with the platform.
            It extracts the auth parameter from the callback and then sends the user a success message.
        
        Args:
            update: Update object
            context: Context object
        """
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
                    response = await self.get("/threads/user_account", params={"user_id": user_id})
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
        """
        Handle /restart command.
        
        Description:
            This method sends a restart message to the user.
        
        Args:
            update: Update object
            context: Context object
        """
        await update.message.reply_text(RESTART_MESSAGE, parse_mode='Markdown')
        

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages and route them to appropriate handlers."""
        try:
            # Check if user is allowed
            user_id = update.message.from_user.id
            if str(user_id) not in settings.ALLOWED_USERS:
                await update.message.reply_text(
                    "❌ You are not authorized to use this bot. Please contact the administrator.",
                    parse_mode='Markdown'
                )
                return

            # Get message content and type
            content, content_type = get_message_content(update.message)
            if not content:
                await update.message.reply_text(
                    "❌ Unsupported message type. Please send text or media.",
                    parse_mode='Markdown'
                )
                return

            try:
                # Make API request
                response = await handle_response(content, content_type, user_id)
                
                if response.status_code == 404:
                    error_data = response.json()
                    if "not connected" in error_data.get("message", "").lower():
                        # Guide user to connect their accounts
                        await update.message.reply_text(
                            "🔗 Please connect your social media accounts first using the /connect command.",
                            parse_mode='Markdown'
                        )
                        return
                        
                elif response.status_code == 401:
                    error_data = response.json()
                    if "expired" in error_data.get("message", "").lower():
                        # Guide user to reconnect their accounts
                        await update.message.reply_text(
                            "⚠️ Your account connection has expired. Please reconnect using the /connect command.",
                            parse_mode='Markdown'
                        )
                        return

                elif response.status_code != 200:
                    error_data = response.json()
                    error_message = error_data.get("message", "Unknown error occurred")
                    await update.message.reply_text(
                        f"❌ Error: {error_message}\n\nPlease try again or use /help for assistance.",
                        parse_mode='Markdown'
                    )
                    return

                # Handle successful response
                response_data = response.json()
                
                if response_data.get("status") == "success":
                    tweet_data = response_data.get("data", {}).get("tweet", {})
                    thread_data = response_data.get("data", {}).get("thread", {})
                    
                    # Format success messages for each platform
                    success_messages = []
                    
                    if tweet_data:
                        tweet_url = tweet_data.get("permalink")
                        tweet_timestamp = tweet_data.get("timestamp")
                        success_messages.append(
                            POST_SUCCESS_MESSAGE.format(
                                platform="Twitter",
                                post_url=tweet_url,
                                timestamp=tweet_timestamp
                            )
                        )
                    
                    if thread_data:
                        thread_url = thread_data.get("permalink")
                        thread_timestamp = thread_data.get("timestamp")
                        success_messages.append(
                            POST_SUCCESS_MESSAGE.format(
                                platform="Threads",
                                post_url=thread_url,
                                timestamp=thread_timestamp
                            )
                        )
                    
                    if success_messages:
                        await update.message.reply_text(
                            "\n\n".join(success_messages),
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            "✅ Message processed successfully, but no posts were created.",
                            parse_mode='Markdown'
                        )

            except httpx.RequestError as e:
                logger.error(f"HTTP Request Error: {str(e)}")
                await update.message.reply_text(
                    "❌ Network error occurred. Please try again later.",
                    parse_mode='Markdown'
                )
            except httpx.TimeoutException:
                logger.error("Request timed out")
                await update.message.reply_text(
                    "⏳ Request timed out. Please try again.",
                    parse_mode='Markdown'
                )
            except json.JSONDecodeError:
                logger.error("Invalid JSON response")
                await update.message.reply_text(
                    "❌ Error processing server response. Please try again.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Unexpected error in handle_message: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later or contact support.",
                parse_mode='Markdown'
            )

    async def post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /post command.
        
        Description:
            This method posts a message to Threads and Twitter.
        
        Args:
            update: Update object
            context: Context object
        """
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
        
        #! TODO: Parallelize the requests to Threads and Twitter
        try:
            is_connected = await self.get("/threads/is_connected", params={"user_id": user_id})
            logger.info(f"Is connected: {is_connected}")
            
            if is_connected:
                response = await self.post("/threads/post", params={"user_id": user_id, "message": message, "image_url": image_url}, timeout=30)
                
                logger.info(f"Response: {response.json()}")
                await self.handle_api_response(response, "Threads")
                
                if response.json().get("status") == "success":
                    thread_url = response.json().get("thread").get("permalink")
                    # Parse 2025-01-04T11:39:58+0000 to 2025-01-04 11:39:58
                    thread_timestamp = response.json().get("thread").get("timestamp").replace("T", " ").replace("+0000", "")
                    logger.info(f"Thread URL: {thread_url}")
                    
                    success_message = POST_SUCCESS_MESSAGE.format(post_url=thread_url, timestamp=thread_timestamp, platform="Threads")
                    await update.message.reply_text(success_message, parse_mode='Markdown')
                elif response.json().get("status") == "missing":
                    # await update.message.reply_text("❌ User not connected to Threads", parse_mode='Markdown')
                    pass
                else:
                    await update.message.reply_text("❌ Failed to post a thread. Please try again.", parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error posting thread: {str(e)}")
            await update.message.reply_text("❌ Failed to post a thread. Please try again.", parse_mode='Markdown')
            
        logger.info(f"Begin postting a message to Twitter for user {update.message.from_user.id}")
        try:
            # Check if user is connected to Twitter
            is_connected = await self.get("/twitter/is_connected", params={"user_id": user_id})
            logger.info(f"Is connected: {is_connected}")
            
            await self.handle_api_response(response, "Twitter")

            if is_connected:
                response = await self.post("/twitter/post", params={"user_id": user_id, "message": message, "image_url": image_url}, timeout=30)
                
                if response.status_code != 200 or response.json().get("status") == "error":
                    await update.message.reply_text("❌ Failed to post a tweet. Please try again.", parse_mode='Markdown')
                    return
                
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
                    # await update.message.reply_text("❌ User not connected to Twitter", parse_mode='Markdown')
                    pass
                else:
                    await update.message.reply_text("❌ Failed to post a tweet. Please try again.", parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            await update.message.reply_text("❌ Failed to post a tweet. Please try again.", parse_mode='Markdown')

    async def handle_api_response(self, response, platform: str):
        """Handle API response and raise appropriate exceptions"""
        try:
            if response.status_code == 404:
                error_data = response.json()
                raise ConnectionError(
                    message=f"Not connected to {platform}",
                    status_code=404,
                    platform=platform,
                    details=error_data
                )
            elif response.status_code == 401:
                error_data = response.json()
                raise ExpiredCredentialsError(
                    message=f"{platform} credentials expired",
                    status_code=401,
                    platform=platform,
                    details=error_data
                )
            elif response.status_code != 200:

                error_data = response.json()
                raise APIError(
                    message=error_data.get("message", f"Error with {platform} API"),
                    status_code=response.status_code,
                    platform=platform,
                    details=error_data
                )
            

            return response.json()
        
        except json.JSONDecodeError:
            raise APIError(
                message=f"Invalid response from {platform} API",
                status_code=response.status_code,
                platform=platform,
                details={"raw_response": response.text}
            )


    # Bot Handlers
    def add_handlers(self):
        # Commands with user restriction
        if not settings.ALLOWED_USERS or settings.ALLOWED_USERS[0] == "all":
            allowed_users_filter = filters.ALL
        else:
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
