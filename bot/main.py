import httpx
import telegram
from bot.utils.config import get_settings
from bot.utils.logger import logger
import io
from bot.utils.utils import transcribe_audio
from bot.utils.prompts import (
    HELP_MESSAGE,
    POST_SUCCESS_MESSAGE,
    START_MESSAGE,
    CONNECT_MESSAGE,
    RESTART_MESSAGE,
    THREADS_ACCOUNT_INFO_MESSAGE,
    NO_ACCOUNT_MESSAGE,
    TWITTER_ACCOUNT_INFO_MESSAGE,
)
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LoginUrl,
    Audio,
    BotCommand,
    constants,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    AIORateLimiter,
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


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the Telegram Bot."""
    logger.error(f"Update {update} caused error {context.error}")

    try:
        if update and update.effective_message:
            if isinstance(context.error, httpx.RequestError):
                await update.effective_message.reply_text(
                    "❌ Network error occurred. Please try again later.",
                    parse_mode="Markdown",
                )
            elif isinstance(context.error, httpx.TimeoutException):
                await update.effective_message.reply_text(
                    "⏳ Request timed out. Please try again.", parse_mode="Markdown"
                )
            elif isinstance(context.error, telegram.error.NetworkError):
                await update.effective_message.reply_text(
                    "📡 Telegram network error. Please try again later.",
                    parse_mode="Markdown",
                )
            elif isinstance(context.error, telegram.error.Forbidden):
                await update.effective_message.reply_text(
                    "🔒 Bot authentication failed. Please contact the administrator.",
                    parse_mode="Markdown",
                )
            else:
                await update.effective_message.reply_text(
                    "❌ An unexpected error occurred. Please try again later or contact support.",
                    parse_mode="Markdown",
                )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")


async def post_init(application: Application):
    await application.bot.set_my_commands(
        [
            BotCommand("/help", "🤔 Show help message"),
            BotCommand("/post", "🚀 Post to connected platforms"),
            BotCommand("/connect", "🔗 Connect to platforms"),
            BotCommand("/disconnect", "🔌 Disconnect from platforms"),
            BotCommand("/account", "👤 Show account information"),
            BotCommand("/health", "🩺 Show health check"),
            BotCommand("/settings", "⚙️ Show settings"),
            BotCommand("/status", "📊 Show status"),
            BotCommand("/restart", "🔄 Restart the bot"),
        ]
    )


class TelegramBot:
    def __init__(self):
        logger.info("Starting up bot...")
        self.application = (
            ApplicationBuilder()
            .token(settings.TELEGRAM_TOKEN)
            .concurrent_updates(True)
            .rate_limiter(AIORateLimiter(max_retries=5))
            .post_init(post_init)
            .build()
        )
        self.API_PUBLIC_URL = settings.API_PUBLIC_URL
        api_host = settings.API_PUBLIC_URL.split("://")[1]
        logger.info(f"API host: {api_host}")
        self.http_client = httpx.AsyncClient(
            headers={
                settings.API_KEY_HEADER_NAME.strip('"'): settings.API_KEY,
                "Host": api_host,
                "User-Agent": "TelegramBot/1.0",
            },
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=30.0),
            verify=True,
        )
        logger.info(f"Allowed users: {settings.ALLOWED_USERS}")
        logger.info("✅ Bot initialized")

    async def api_get(
        self, endpoint: str, params: dict = None, timeout: int = 30, **kwargs
    ):
        response = await self.http_client.get(
            self.API_PUBLIC_URL + endpoint, params=params, timeout=timeout, **kwargs
        )
        return response

    async def api_post(
        self,
        endpoint: str,
        params: dict = None,
        body: dict = None,
        data: dict = None,
        files: dict = None,
        timeout: int = 30,
        **kwargs,
    ):
        response = await self.http_client.post(
            self.API_PUBLIC_URL + endpoint,
            params=params,
            json=body,
            data=data,
            files=files,
            timeout=timeout,
            **kwargs,
        )
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
            api_response = await self.api_get("/health")

            if api_response.status_code != 200:
                await update.message.reply_text(
                    f"Bot check passed: {bot_response}.\n\n❌ Backend check failed: {api_response.status_code} - {api_response.text}",
                    parse_mode="Markdown",
                )
                return

            api_data = api_response.json()
            await update.message.reply_text(
                f"✅ Bot check passed: {bot_response}.\n\n✅ Backend check passed: {api_data}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            await update.message.reply_text(
                "An error occurred during the health check. Please try again later.",
                parse_mode="Markdown",
            )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /start command and deep links

        Description:
            This method sends a start message to the user.

        Args:
            update: Update object
            context: Context object
        """
        await update.message.reply_text(START_MESSAGE, parse_mode="Markdown")

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I didn't understand that command.",
            parse_mode="Markdown",
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /help command.

        Description:
            This method sends a help message to the user.

        Args:
            update: Update object
            context: Context object
        """
        await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")

    async def get_user_account(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
            await update.message.reply_text(
                "Sorry, there was an error getting your account information.",
                parse_mode="Markdown",
            )
            return

        try:

            # Get Threads account data
            response = await self.api_get(
                "/threads/user_account", params={"user_id": user_id}
            )
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
                parse_mode="Markdown",
            )

        except ConnectionError as e:
            logger.info(f"User not connected to {e.platform}: {e.message}")
            await update.message.reply_text(
                f"❌ User not connected to {e.platform}. Please connect using /connect",
                parse_mode="Markdown",
            )

        except ExpiredCredentialsError as e:
            logger.warning(f"Expired credentials for {e.platform}: {e.message}")
            await update.message.reply_text(
                f"⚠️ Your {e.platform} connection has expired. Please reconnect using /connect",
                parse_mode="Markdown",
            )

        except APIError as e:
            logger.error(f"API Error: {e.message}", extra={"details": e.details})
            await update.message.reply_text(
                f"❌ Error with {e.platform}: {e.message}", parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later.",
                parse_mode="Markdown",
            )

        try:
            # Get Twitter account data
            response = await self.api_get(
                "/twitter/user_account", params={"user_id": user_id}
            )
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
                media_count=twitter_data.get("metrics").get("media_count"),
            )

            await update.message.reply_photo(
                photo=twitter_data.get("profile_picture_url"),
                caption=message,
                parse_mode="Markdown",
            )

        except ConnectionError as e:
            logger.info(f"User not connected to {e.platform}: {e.message}")
            await update.message.reply_text(
                f"❌ User not connected to {e.platform}. Please connect using /connect",
                parse_mode="Markdown",
            )

        except ExpiredCredentialsError as e:
            logger.warning(f"Expired credentials for {e.platform}: {e.message}")
            await update.message.reply_text(
                f"⚠️ Your {e.platform} connection has expired. Please reconnect using /connect",
                parse_mode="Markdown",
            )

        except APIError as e:
            logger.error(f"API Error: {e.message}", extra={"details": e.details})

            await update.message.reply_text(
                f"❌ Error with {e.platform}: {e.message}", parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later.",
                parse_mode="Markdown",
            )

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /connect command.

        Description:
            This method sends a message with inline buttons for platform connection.
            General flow is:
            - Check if user is connected to any platform
            - If not, generate auth url
            - Send auth url to user via inline keyboard
            - If user clicks on auth url, open browser to auth url
            - If user is connected, show disconnect button


        Args:
            update: Update object
            context: Context object
        """
        user_id = update.message.from_user.id

        if not user_id:
            await update.message.reply_text(
                "❌ An error occurred while connecting your account. Please try again.",
                parse_mode="Markdown",
            )
            return

        # First send a "processing" message
        progress_message = await update.message.reply_text(
            "🔄 Checking your account connections...", parse_mode="Markdown"
        )

        is_threads_connected = False
        is_twitter_connected = False
        threads_auth_url = None
        twitter_auth_url = None

        # Create a visual guide for connection options
        connection_guide = (
            "📱 *Connect Your Social Accounts*\n\n"
            "Connect your accounts to enable cross-posting:\n\n"
        )

        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            logger.info(f"Threads response status: {threads_response.status_code}")

            logger.info(f"Threads response text: {threads_response.text}")
            threads_response.raise_for_status()
            logger.info(f"Is threads connected: {threads_response.json()}")
            is_threads_connected = threads_response.json()

            connection_guide += f"🧵 *Threads*: {('✅ Connected' if is_threads_connected else '❌ Not connected')}\n"

            if not is_threads_connected:
                threads_auth_url = await self.api_get(
                    "/auth/threads/connect", params={"user_id": user_id}
                )
                if threads_auth_url.json().get("url"):
                    context.user_data[f"threads_auth_url_{user_id}"] = (
                        threads_auth_url.json().get("url")
                    )
            else:
                # If connected, try to get username
                try:
                    account_response = await self.api_get(
                        "/threads/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            connection_guide += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Threads account info: {str(e)}")

                threads_auth_url = (
                    f"{self.API_PUBLIC_URL}/auth/threads/disconnect?user_id={user_id}"
                )
                context.user_data[f"threads_auth_url_{user_id}"] = threads_auth_url

        except Exception as e:
            logger.error(f"Error in connect_command: {str(e)}")
            connection_guide += f"🧵 *Threads*: ❓ Status unknown\n"

        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            logger.info(f"Twitter response status: {twitter_response.status_code}")

            logger.info(f"Twitter response text: {twitter_response.text}")
            twitter_response.raise_for_status()
            logger.info(f"Is twitter connected: {twitter_response.json()}")
            is_twitter_connected = twitter_response.json()

            connection_guide += f"🐦 *Twitter*: {('✅ Connected' if is_twitter_connected else '❌ Not connected')}\n"

            if not is_twitter_connected:
                twitter_auth_url = await self.api_get(
                    "/auth/twitter/connect", params={"user_id": user_id}
                )
                if twitter_auth_url.json().get("url"):
                    context.user_data[f"twitter_auth_url_{user_id}"] = (
                        twitter_auth_url.json().get("url")
                    )
            else:
                # If connected, try to get username
                try:
                    account_response = await self.api_get(
                        "/twitter/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            connection_guide += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Twitter account info: {str(e)}")

                twitter_auth_url = (
                    f"{self.API_PUBLIC_URL}/auth/twitter/disconnect?user_id={user_id}"
                )
                context.user_data[f"twitter_auth_url_{user_id}"] = twitter_auth_url

        except Exception as e:
            logger.error(f"Error in connect_command: {str(e)}")
            connection_guide += f"🐦 *Twitter*: ❓ Status unknown\n"

        connection_guide += "\nSelect an option below to manage your connections:"

        # Create multi-step keyboard
        keyboard = []

        # Add platform-specific connection buttons
        threads_row = []
        twitter_row = []

        if is_threads_connected:
            threads_row.append(
                InlineKeyboardButton(
                    "⛓️‍💥 Disconnect Threads",
                    callback_data=f"disconnect_threads_{user_id}",
                )
            )
        else:
            threads_row.append(
                InlineKeyboardButton(
                    "🔗 Connect Threads", callback_data=f"connect_threads_{user_id}"
                )
            )

        if is_twitter_connected:
            twitter_row.append(
                InlineKeyboardButton(
                    "⛓️‍💥 Disconnect Twitter",
                    callback_data=f"disconnect_twitter_{user_id}",
                )
            )
        else:
            twitter_row.append(
                InlineKeyboardButton(
                    "🔗 Connect Twitter", callback_data=f"connect_twitter_{user_id}"
                )
            )

        keyboard.append(threads_row)
        keyboard.append(twitter_row)

        # Add a "Done" button
        keyboard.append(
            [
                InlineKeyboardButton(
                    "✅ Done", callback_data=f"connection_done_{user_id}"
                )
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update the progress message with the connection guide
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=progress_message.message_id,
            text=connection_guide,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def connect_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        action, platform, user_id = query.data.split("_")
        auth_url = context.user_data.get(f"{platform}_auth_url_{user_id}")

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔐 Authenticate",
                    url=auth_url,
                    callback_data=f"authenticate_{user_id}",
                )
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
                reply_markup=reply_markup,
            )
        elif platform == "twitter":
            # Open auth URL in browser
            await query.delete_message()
            # Redirect user to auth URL
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Click here to connect your X/Twitter account:",
                connect_timeout=120,
                reply_markup=reply_markup,
            )

        del context.user_data[f"{platform}_auth_url_{user_id}"]

    async def disconnect_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        action, platform, user_id = query.data.split("_")

        try:
            if platform == "threads":
                # Make direct HTTP request to disconnect endpoint
                response = await self.api_post(
                    "/auth/threads/disconnect", params={"user_id": user_id}
                )

                if response.status_code == 200:
                    # Delete the original message with the keyboard
                    await query.delete_message()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="✅ Successfully disconnected your Threads account!",
                    )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="❌ Failed to disconnect your account. Please try again.",
                    )

            elif platform == "twitter":
                # Handle Twitter disconnect similarly
                response = await self.api_post(
                    "/auth/twitter/disconnect", params={"user_id": user_id}
                )
                logger.info(f"Twitter disconnect response: {response.json()}")

                if response.status_code == 200:
                    await query.delete_message()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="✅ Successfully disconnected your Twitter account!",
                    )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="❌ Failed to disconnect your account. Please try again.",
                    )

        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ An error occurred while disconnecting your account. Please try again.",
            )

    async def authorize_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        auth_param = command_text.split("&")[-1] if "&" in command_text else None
        if not auth_param:
            return

        user_id = None

        if auth_param.startswith("auth_success_"):
            user_id = auth_param.split("_")[-1]
            if str(update.effective_user.id) == user_id:
                # Get account info to show in success message
                try:
                    response = await self.api_get(
                        "/threads/user_account", params={"user_id": user_id}
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
                            parse_mode="Markdown",
                        )
                    else:
                        await update.message.reply_text(
                            "✅ Successfully connected your Threads account!",
                            parse_mode="Markdown",
                        )
                except Exception as e:
                    logger.error(f"Error fetching account info: {str(e)}")
                    await update.message.reply_text(
                        "❌ Failed to connect your Threads account.",
                        parse_mode="Markdown",
                    )

                # Clean up any previous connection messages
                if "last_connect_message_id" in context.user_data:
                    try:
                        await context.bot.edit_message_reply_markup(
                            chat_id=update.effective_chat.id,
                            message_id=context.user_data["last_connect_message_id"],
                            reply_markup=None,
                        )
                    except Exception as e:
                        logger.error(f"Error cleaning up messages: {str(e)}")
                return

        elif auth_param.startswith("auth_error_"):
            user_id = auth_param.split("_")[-1]
            if str(update.effective_user.id) == user_id:
                error_message = (
                    "❌ Failed to connect your Threads account.\n"
                    "Please try again using the /connect command."
                )
                if auth_param == "auth_error_invalid_state":
                    error_message = (
                        "❌ Authentication session expired or invalid.\n"
                        "Please try again using the /connect command."
                    )
                await update.message.reply_text(error_message, parse_mode="Markdown")
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
        await update.message.reply_text(RESTART_MESSAGE, parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming non-text, non-command messages."""
        try:
            # Auth check is handled by filter in add_handlers
            user_id = update.message.from_user.id  # Keep for logging maybe?
            logger.info(f"Handling non-text message from user_id: {user_id}")

            # Get message content and type
            content, content_type = get_message_content(update.message)

            # If content_type is 'unknown' or content is None (get_message_content handles this)
            if not content:
                await update.message.reply_text(
                    "❌ Unsupported message type. I can currently only process text messages for chat.",
                    parse_mode="Markdown",
                )
                return

            # Placeholder for future handling of other types if needed
            logger.warning(
                f"Received unhandled message type '{content_type}' from user {user_id}"
            )
            await update.message.reply_text(
                f"🤖 I received a {content_type} message, but I can only chat using text for now.",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Unexpected error in handle_message: {str(e)}")
            await update.message.reply_text(
                "❌ An unexpected error occurred processing this message type.",
                parse_mode="Markdown",
            )

    async def post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /post command.

        Description:
            This method posts a message to Threads and Twitter with platform selection.

        Args:
            update: Update object
            context: Context object
        """
        user_id = update.message.from_user.id

        # Check if message is a reply to the platform selection
        if (
            "platform_selection" in context.user_data
            and update.message.reply_to_message
        ):
            if (
                update.message.reply_to_message.message_id
                == context.user_data["platform_selection"]["message_id"]
            ):
                # This is content to post after platform selection
                platforms = context.user_data["platform_selection"]["platforms"]
                await self.process_post(update, context, platforms)
                del context.user_data["platform_selection"]
                return

        # Get message content
        message = update.message.text_markdown.replace("/post", "").strip()
        has_media = (
            len(update.message.photo) > 0
            or update.message.document
            or update.message.video
        )

        # First send a "processing" message
        progress_message = await update.message.reply_text(
            "🔄 Checking your account connections...", parse_mode="Markdown"
        )

        # Check connections first
        threads_connected = False
        twitter_connected = False

        try:
            # Check Threads connection
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            threads_connected = (
                threads_response.json()
                if threads_response.status_code == 200
                else False
            )

            # Check Twitter connection
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            twitter_connected = (
                twitter_response.json()
                if twitter_response.status_code == 200
                else False
            )

            # If no platforms connected, guide user
            if not threads_connected and not twitter_connected:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=progress_message.message_id,
                    text="❌ You don't have any social media accounts connected. Use /connect to link your accounts first.",
                    parse_mode="Markdown",
                )
                return

            # Create platform selection message
            platform_message = "📱 *New Post*\n\n" "Select where you'd like to post:"

            # Create platform selection keyboard
            keyboard = []
            if threads_connected and twitter_connected:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🧵 Threads",
                            callback_data=f"post_platform_threads_{user_id}",
                        ),
                        InlineKeyboardButton(
                            "🐦 Twitter",
                            callback_data=f"post_platform_twitter_{user_id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🔄 Both Platforms",
                            callback_data=f"post_platform_both_{user_id}",
                        )
                    ],
                ]
            elif threads_connected:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🧵 Post to Threads",
                            callback_data=f"post_platform_threads_{user_id}",
                        )
                    ]
                ]
            elif twitter_connected:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🐦 Post to Twitter",
                            callback_data=f"post_platform_twitter_{user_id}",
                        )
                    ]
                ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Check if there's already content in the command
            if message or has_media:
                # Content already provided with command
                platform_message += "\n\nYour content is ready to post."

                # Store the message with content
                context.user_data["pending_post"] = {
                    "message": message,
                    "has_media": has_media,
                    "media_items": update.message.photo
                    or update.message.document
                    or update.message.video,
                    "message_id": progress_message.message_id,
                }
            else:
                # No content yet, ask for platform first
                platform_message += "\n\nAfter selecting, send your content as a reply."

                # Store the selection message to identify the reply later
                context.user_data["platform_selection"] = {
                    "message_id": progress_message.message_id,
                    "platforms": None,  # Will be set in the callback
                }

            # Update the progress message with platform selection
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=progress_message.message_id,
                text=platform_message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Error in post_command: {str(e)}")
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=progress_message.message_id,
                text="❌ Error checking your connections. Please try again.",
                parse_mode="Markdown",
            )

    async def post_platform_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle platform selection for posting.

        Description:
            This method processes the platform selection for posting.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state

        # Extract platform choice and user_id
        _, _, platform, user_id = query.data.split("_")

        if "pending_post" in context.user_data:
            # Content was already provided with the command
            post_data = context.user_data["pending_post"]

            # Show processing status
            await query.edit_message_text(
                "🔄 Posting your content...", parse_mode="Markdown"
            )

            # Process the post based on selected platform
            if platform == "both":
                platforms = ["threads", "twitter"]
            else:
                platforms = [platform]

            # Get the message content
            message = post_data["message"]
            media_items = post_data["media_items"] if post_data["has_media"] else None

            # Post to selected platforms
            results = []

            for plat in platforms:
                try:
                    if plat == "threads":
                        response = await self.api_post(
                            "/threads/post",
                            params={
                                "user_id": user_id,
                                "message": message,
                                "image_url": (
                                    media_items[0].file_id if media_items else None
                                ),
                            },
                            timeout=30,
                        )

                        if (
                            response.status_code == 200
                            and response.json().get("status") == "success"
                        ):
                            thread_data = response.json().get("thread", {})
                            thread_url = thread_data.get("permalink")
                            thread_timestamp = (
                                thread_data.get("timestamp")
                                .replace("T", " ")
                                .replace("+0000", "")
                            )

                            results.append(
                                POST_SUCCESS_MESSAGE.format(
                                    platform="Threads",
                                    post_url=thread_url,
                                    timestamp=thread_timestamp,
                                )
                            )

                            keyboard = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            "🗑️ Delete Post",
                                            callback_data=f"delete_threads_{thread_data.get('id')}_{user_id}",
                                        )
                                    ]
                                ]
                            )

                            await query.message.reply_text(
                                results[-1],
                                reply_markup=keyboard,
                                parse_mode="Markdown",
                            )
                            results[-1] = None

                        else:
                            error_message = response.json().get(
                                "message", "Unknown error"
                            )
                            results.append(
                                f"❌ *Threads*: Failed to post - {error_message}"
                            )

                    elif plat == "twitter":
                        response = await self.api_post(
                            "/twitter/post",
                            params={
                                "user_id": user_id,
                                "message": message,
                                "image_url": (
                                    media_items[0].file_id if media_items else None
                                ),
                            },
                            timeout=30,
                        )

                        if (
                            response.status_code == 200
                            and response.json().get("status") == "success"
                        ):
                            tweet_data = response.json().get("tweet", {})
                            tweet_url = tweet_data.get("permalink")
                            tweet_timestamp = tweet_data.get("timestamp")

                            results.append(
                                POST_SUCCESS_MESSAGE.format(
                                    platform="Twitter",
                                    post_url=tweet_url,
                                    timestamp=tweet_timestamp,
                                )
                            )

                            keyboard = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            "🗑️ Delete Post",
                                            callback_data=f"delete_twitter_{tweet_data.get('id')}_{user_id}",
                                        )
                                    ]
                                ]
                            )

                            await query.message.reply_text(
                                results[-1],
                                reply_markup=keyboard,
                                parse_mode="Markdown",
                            )
                            results[-1] = None
                        else:
                            error_message = response.json().get(
                                "message", "Unknown error"
                            )
                            results.append(
                                f"❌ *Twitter*: Failed to post - {error_message}"
                            )

                except Exception as e:
                    logger.error(f"Error posting to {plat}: {str(e)}")
                    results.append(f"❌ *{plat.capitalize()}*: Error - {str(e)}")

            # Show results
            results = [r for r in results if r is not None]

            if results:
                await query.edit_message_text(
                    "\n\n".join(results), parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "❌ Failed to post content. Please try again.",
                    parse_mode="Markdown",
                )

            # Clean up
            del context.user_data["pending_post"]

        else:
            # No content yet, update the selection message and prompt for content
            if platform == "both":
                platforms = ["threads", "twitter"]
                platform_names = "Threads and Twitter"
            else:
                platforms = [platform]
                platform_names = "Threads" if platform == "threads" else "Twitter"

            # Update selection message
            await query.edit_message_text(
                f"📝 Please send the content you want to post to {platform_names} as a reply to this message.\n\nYou can include text and/or media.",
                parse_mode="Markdown",
            )

            # Store the selection for handling the next message
            if "platform_selection" in context.user_data:
                context.user_data["platform_selection"]["platforms"] = platforms

    async def delete_post_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle post deletion callback.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()

        # Extract platform, post_id and user_id from callback data
        _, platform, post_id, user_id = query.data.split("_")

        try:
            # Show processing status
            await query.edit_message_text("🔄 Deleting post...", parse_mode="Markdown")

            # Call appropriate API endpoint
            response = await self.api_delete(
                f"/{platform}/delete_post",
                params={"user_id": user_id, "id": post_id},
                timeout=30,
            )

            if (
                response.status_code == 200
                and response.json().get("status") == "success"
            ):
                await query.edit_message_text(
                    f"✅ Post deleted successfully from {platform.capitalize()}",
                    parse_mode="Markdown",
                )
            else:
                error_message = response.json().get("message", "Unknown error")
                await query.edit_message_text(
                    f"❌ Failed to delete post from {platform.capitalize()} - {error_message}",
                    parse_mode="Markdown",
                )

        except Exception as e:
            logger.error(f"Error deleting post from {platform}: {str(e)}")
            await query.edit_message_text(
                f"❌ Error deleting post from {platform.capitalize()} - {str(e)}",
                parse_mode="Markdown",
            )

    async def process_post(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, platforms: list
    ):
        """
        Process a post to selected platforms.

        Description:
            This method processes a post to the selected platforms.

        Args:
            update: Update object
            context: Context object
            platforms: List of platforms to post to
        """
        user_id = update.message.from_user.id

        # Get message content
        content, content_type = get_message_content(update.message)

        if not content:
            await update.message.reply_text(
                "❌ Unsupported message type. Please send text or media.",
                parse_mode="Markdown",
            )
            return

        # Show processing message
        progress_message = await update.message.reply_text(
            "🔄 Processing your post...", parse_mode="Markdown"
        )

        # Post to selected platforms
        results = []

        for platform in platforms:
            try:
                if platform == "threads":
                    response = await self.api_post(
                        "/threads/post",
                        params={
                            "user_id": user_id,
                            "message": content if content_type == "text" else "",
                            "image_url": content if content_type != "text" else None,
                        },
                        timeout=30,
                    )

                    if (
                        response.status_code == 200
                        and response.json().get("status") == "success"
                    ):
                        thread_data = response.json().get("thread", {})
                        thread_url = thread_data.get("permalink")
                        thread_timestamp = (
                            thread_data.get("timestamp")
                            .replace("T", " ")
                            .replace("+0000", "")
                        )

                        results.append(
                            POST_SUCCESS_MESSAGE.format(
                                platform="Threads",
                                post_url=thread_url,
                                timestamp=thread_timestamp,
                            )
                        )
                    else:
                        error_message = response.json().get("message", "Unknown error")
                        results.append(
                            f"❌ *Threads*: Failed to post - {error_message}"
                        )

                elif platform == "twitter":
                    response = await self.api_post(
                        "/twitter/post",
                        params={
                            "user_id": user_id,
                            "message": content if content_type == "text" else "",
                            "image_url": content if content_type != "text" else None,
                        },
                        timeout=30,
                    )

                    if (
                        response.status_code == 200
                        and response.json().get("status") == "success"
                    ):
                        tweet_data = response.json().get("tweet", {})
                        tweet_url = tweet_data.get("permalink")
                        tweet_timestamp = tweet_data.get("timestamp")

                        results.append(
                            POST_SUCCESS_MESSAGE.format(
                                platform="Twitter",
                                post_url=tweet_url,
                                timestamp=tweet_timestamp,
                            )
                        )
                    else:
                        error_message = response.json().get("message", "Unknown error")
                        results.append(
                            f"❌ *Twitter*: Failed to post - {error_message}"
                        )

            except Exception as e:
                logger.error(f"Error posting to {platform}: {str(e)}")
                results.append(f"❌ *{platform.capitalize()}*: Error - {str(e)}")

        # Show results
        if results:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=progress_message.message_id,
                text="\n\n".join(results),
                parse_mode="Markdown",
            )
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=progress_message.message_id,
                text="❌ Failed to post content. Please try again.",
                parse_mode="Markdown",
            )

    async def handle_api_response(self, response, platform: str):
        """Handle API response and raise appropriate exceptions"""
        try:
            if response.status_code == 404:
                error_data = response.json()
                raise ConnectionError(
                    message=f"Not connected to {platform}",
                    status_code=404,
                    platform=platform,
                    details=error_data,
                )
            elif response.status_code == 401:
                error_data = response.json()
                raise ExpiredCredentialsError(
                    message=f"{platform} credentials expired",
                    status_code=401,
                    platform=platform,
                    details=error_data,
                )
            elif response.status_code != 200:

                error_data = response.json()
                raise APIError(
                    message=error_data.get("message", f"Error with {platform} API"),
                    status_code=response.status_code,
                    platform=platform,
                    details=error_data,
                )

            return response.json()

        except json.JSONDecodeError:
            raise APIError(
                message=f"Invalid response from {platform} API",
                status_code=response.status_code,
                platform=platform,
                details={"raw_response": response.text},
            )

    async def connection_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Show a visual dashboard of connected platforms and their status.

        Description:
            This method provides a visual representation of the user's connected accounts
            and their current status.

        Args:
            update: Update object
            context: Context object
        """
        user_id = update.message.from_user.id

        # Create a visual status board with emojis
        status_message = "📱 *Your Connected Accounts*\n\n"

        # First send a "processing" message
        progress_message = await update.message.reply_text(
            "🔄 Checking your account connections...", parse_mode="Markdown"
        )

        # Check Threads status
        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            is_threads_connected = (
                threads_response.json()
                if threads_response.status_code == 200
                else False
            )

            status_message += (
                "🧵 *Threads*: "
                + ("✅ Connected" if is_threads_connected else "❌ Not connected")
                + "\n"
            )

            # If connected, add account info
            if is_threads_connected:
                try:
                    account_response = await self.api_get(
                        "/threads/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            status_message += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Threads account info: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Threads connection: {str(e)}")
            status_message += "🧵 *Threads*: ❓ Status unknown\n"

        # Check Twitter status
        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            is_twitter_connected = (
                twitter_response.json()
                if twitter_response.status_code == 200
                else False
            )

            status_message += (
                "\n🐦 *Twitter*: "
                + ("✅ Connected" if is_twitter_connected else "❌ Not connected")
                + "\n"
            )

            # If connected, add account info
            if is_twitter_connected:
                try:
                    account_response = await self.api_get(
                        "/twitter/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            status_message += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Twitter account info: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Twitter connection: {str(e)}")
            status_message += "🐦 *Twitter*: ❓ Status unknown\n"

        # Add action buttons
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Refresh Status", callback_data=f"refresh_status_{user_id}"
                ),
                InlineKeyboardButton(
                    "🔗 Manage Connections",
                    callback_data=f"manage_connections_{user_id}",
                ),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update the progress message with the status
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=progress_message.message_id,
            text=status_message,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def refresh_status_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle refresh_status callback.

        Description:
            This method refreshes the connection status dashboard.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state

        # Extract user_id from callback_data
        _, _, user_id = query.data.split("_")

        # Create a visual status board with emojis
        status_message = "📱 *Your Connected Accounts*\n\n"

        # Show processing indicator
        await query.edit_message_text(
            "🔄 Refreshing your account connections...", parse_mode="Markdown"
        )

        # Check Threads status
        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            is_threads_connected = (
                threads_response.json()
                if threads_response.status_code == 200
                else False
            )

            status_message += (
                "🧵 *Threads*: "
                + ("✅ Connected" if is_threads_connected else "❌ Not connected")
                + "\n"
            )

            # If connected, add account info
            if is_threads_connected:
                try:
                    account_response = await self.api_get(
                        "/threads/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            status_message += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Threads account info: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Threads connection: {str(e)}")
            status_message += "🧵 *Threads*: ❓ Status unknown\n"

        # Check Twitter status
        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            is_twitter_connected = (
                twitter_response.json()
                if twitter_response.status_code == 200
                else False
            )

            status_message += (
                "\n🐦 *Twitter*: "
                + ("✅ Connected" if is_twitter_connected else "❌ Not connected")
                + "\n"
            )

            # If connected, add account info
            if is_twitter_connected:
                try:
                    account_response = await self.api_get(
                        "/twitter/user_account", params={"user_id": user_id}
                    )
                    if account_response.status_code == 200:
                        account_data = account_response.json().get("data", {})
                        username = account_data.get("username")
                        if username:
                            status_message += f"└─ @{username}\n"
                except Exception as e:
                    logger.error(f"Error fetching Twitter account info: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Twitter connection: {str(e)}")
            status_message += "🐦 *Twitter*: ❓ Status unknown\n"

        # Add action buttons
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Refresh Status", callback_data=f"refresh_status_{user_id}"
                ),
                InlineKeyboardButton(
                    "🔗 Manage Connections",
                    callback_data=f"manage_connections_{user_id}",
                ),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update the message with the refreshed status
        await query.edit_message_text(
            text=status_message, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def manage_connections_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle manage_connections callback.

        Description:
            This method shows a menu for managing connections.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state

        # Extract user_id from callback_data
        _, _, user_id = query.data.split("_")

        # Show processing indicator
        await query.edit_message_text(
            "🔄 Loading connection management options...", parse_mode="Markdown"
        )

        # Check current connection status
        is_threads_connected = False
        is_twitter_connected = False

        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            is_threads_connected = (
                threads_response.json()
                if threads_response.status_code == 200
                else False
            )
        except Exception as e:
            logger.error(f"Error checking Threads connection: {str(e)}")

        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            is_twitter_connected = (
                twitter_response.json()
                if twitter_response.status_code == 200
                else False
            )
        except Exception as e:
            logger.error(f"Error checking Twitter connection: {str(e)}")

        # Create connection management message
        connection_guide = (
            "📱 *Manage Your Social Accounts*\n\n"
            "Connect or disconnect your accounts:\n\n"
            f"🧵 *Threads*: {('✅ Connected' if is_threads_connected else '❌ Not connected')}\n"
            f"🐦 *Twitter*: {('✅ Connected' if is_twitter_connected else '❌ Not connected')}\n\n"
            "Select an option below:"
        )

        # Create multi-step keyboard
        keyboard = []

        # Add platform-specific connection buttons
        threads_row = []
        twitter_row = []

        if is_threads_connected:
            threads_row.append(
                InlineKeyboardButton(
                    "⛓️‍💥 Disconnect Threads",
                    callback_data=f"disconnect_threads_{user_id}",
                )
            )
        else:
            threads_row.append(
                InlineKeyboardButton(
                    "🔗 Connect Threads", callback_data=f"connect_threads_{user_id}"
                )
            )

        if is_twitter_connected:
            twitter_row.append(
                InlineKeyboardButton(
                    "⛓️‍💥 Disconnect Twitter",
                    callback_data=f"disconnect_twitter_{user_id}",
                )
            )
        else:
            twitter_row.append(
                InlineKeyboardButton(
                    "🔗 Connect Twitter", callback_data=f"connect_twitter_{user_id}"
                )
            )

        keyboard.append(threads_row)
        keyboard.append(twitter_row)

        # Add a "Back" button
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ Back to Status", callback_data=f"refresh_status_{user_id}"
                )
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update the message with connection management options
        await query.edit_message_text(
            text=connection_guide, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def connection_done_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle connection_done callback.

        Description:
            This method is called when the user clicks the "Done" button in the connection management interface.
            It provides a summary of the user's connections and next steps.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Answer the callback query to remove loading state

        # Extract user_id from callback_data
        _, _, user_id = query.data.split("_")

        # Check current connection status
        is_threads_connected = False
        is_twitter_connected = False

        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            is_threads_connected = (
                threads_response.json()
                if threads_response.status_code == 200
                else False
            )
        except Exception as e:
            logger.error(f"Error checking Threads connection: {str(e)}")

        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            is_twitter_connected = (
                twitter_response.json()
                if twitter_response.status_code == 200
                else False
            )
        except Exception as e:
            logger.error(f"Error checking Twitter connection: {str(e)}")

        # Create summary message
        summary = "📱 *Connection Summary*\n\n"

        if is_threads_connected or is_twitter_connected:
            summary += "✅ *Connected Accounts:*\n"
            if is_threads_connected:
                summary += "- 🧵 Threads\n"
            if is_twitter_connected:
                summary += "- 🐦 Twitter\n"

            summary += "\n🔄 *What's Next?*\n"
            summary += "- Send a message to post to your connected accounts\n"
            summary += "- Use /post to create a new post\n"
            summary += "- Use /account to view your account details\n"
            summary += "- Use /status to check your connections anytime\n"
        else:
            summary += "❌ *No Connected Accounts*\n\n"
            summary += "You don't have any social media accounts connected.\n"
            summary += "Use /connect to link your accounts first.\n"

        # Update the message with the summary
        await query.edit_message_text(text=summary, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /status command.

        Description:
            This method is an alias for connection_status.

        Args:
            update: Update object
            context: Context object
        """
        await self.connection_status(update, context)

    async def validate_connections(
        self, user_id: int, notify: bool = False, update: Update = None
    ):
        """
        Validate all platform connections and return status.

        Description:
            This method checks the validity of all platform connections and returns their status.
            It can also notify the user if tokens are expiring soon.

        Args:
            user_id: User ID
            notify: Whether to notify the user if tokens are expiring soon
            update: Update object (required if notify is True)

        Returns:
            Dictionary with connection status for each platform
        """
        results = {
            "threads": {
                "connected": False,
                "valid": False,
                "expires_in": None,
                "error": None,
            },
            "twitter": {
                "connected": False,
                "valid": False,
                "expires_in": None,
                "error": None,
            },
        }

        # Check Threads
        try:
            threads_response = await self.api_get(
                "/auth/threads/is_connected", params={"user_id": user_id}
            )
            logger.info(f"Threads response: {threads_response}")
            if threads_response.status_code == 200 and threads_response.json():
                results["threads"]["connected"] = True

                # Check token validity
                validity_response = await self.api_get(
                    "/threads/token_validity", params={"user_id": user_id}
                )
                logger.info(f"Validity response: {validity_response}")
                if validity_response.status_code == 200:
                    response_json = validity_response.json()
                    # Access the validity info from the data field
                    validity_data = response_json.get("data", {})

                    results["threads"]["valid"] = validity_data.get("valid", False)
                    results["threads"]["expires_in"] = validity_data.get("expires_in")

                    # Notify if token is expiring soon (less than 3 days)
                    if (
                        notify
                        and update
                        and results["threads"]["valid"]
                        and results["threads"]["expires_in"] < 259200
                    ):
                        days_left = results["threads"]["expires_in"] // 86400
                        await update.message.reply_text(
                            f"⚠️ Your Threads connection will expire in {days_left} days. Consider reconnecting soon using /connect.",
                            parse_mode="Markdown",
                        )
        except Exception as e:
            logger.error(f"Error validating Threads connection: {str(e)}")
            results["threads"]["error"] = str(e)

        # Check Twitter
        try:
            twitter_response = await self.api_get(
                "/auth/twitter/is_connected", params={"user_id": user_id}
            )
            if twitter_response.status_code == 200 and twitter_response.json():
                results["twitter"]["connected"] = True

                # Check token validity
                validity_response = await self.api_get(
                    "/twitter/token_validity", params={"user_id": user_id}
                )
                if validity_response.status_code == 200:
                    response_json = validity_response.json()
                    # Access the validity info from the data field
                    validity_data = response_json.get("data", {})

                    results["twitter"]["valid"] = validity_data.get("valid", False)
                    results["twitter"]["expires_in"] = validity_data.get("expires_in")

                    # Notify if token is expiring soon (less than 3 days)
                    if (
                        notify
                        and update
                        and results["twitter"]["valid"]
                        and results["twitter"]["expires_in"] < 259200
                    ):
                        days_left = results["twitter"]["expires_in"] // 86400
                        await update.message.reply_text(
                            f"⚠️ Your Twitter connection will expire in {days_left} days. Consider reconnecting soon using /connect.",
                            parse_mode="Markdown",
                        )
        except Exception as e:
            logger.error(f"Error validating Twitter connection: {str(e)}")
            results["twitter"]["error"] = str(e)

        return results

    async def handle_ai_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handles regular text messages by sending them to the AI API endpoint."""
        user_id = str(update.message.from_user.id)
        message_text = update.message.text
        logger.info(f"Handling AI text message from user_id: {user_id}")

        # -- Voice to Text --
        # Handle voice and transcribe
        if update.message.voice:
            await update.message.chat.send_action(
                action=constants.ChatAction.RECORD_VOICE
            )
            voice = update.message.voice
            voice_file = await context.bot.get_file(voice.file_id)

            # store file in memory, not on disk
            audio_buf = io.BytesIO()
            await voice_file.download_to_memory(audio_buf)
            audio_buf.name = "voice.oga"  # file extension is required
            audio_buf.seek(0)  # move cursor to the beginning of the buffer

            transcribed_text = transcribe_audio(audio_buf)
            message_text = transcribed_text

        # -- Media --
        # Gather attached media
        media = update.message.photo or update.message.video
        media_buf = None
        if media:
            media_file_ids = [file.file_id for file in media]
            media = await context.bot.get_file(media_file_ids[0])
            mime_type = "image/jpeg"

            # store file in memory, not on disk
            media_buf = io.BytesIO()
            await media.download_to_memory(media_buf)
            media_buf.name = "media.jpg"  # file extension is required
            media_buf.seek(0)  # move cursor to the beginning of the buffer
        else:
            media_buf = None

        # Prepare data for multipart request
        request_data = {"user_id": user_id, "message": message_text}
        request_files = None
        if media_buf:
            # httpx expects files as {field_name: (filename, file_obj, content_type)}
            # Use buf.name which was set earlier (e.g., 'voice.oga', 'media.jpg')
            # Using a generic content type here, could be refined if needed.
            request_files = {"media_file": (media_buf.name, media_buf, mime_type)}

        logger.debug(
            f"Sending AI request. Data: {request_data}, Files: {request_files is not None}"
        )

        await update.message.chat.send_action(
            action=constants.ChatAction.TYPING
        )  # Indicate bot is thinking

        try:
            # Call the AI API endpoint using multipart/form-data
            response = await self.api_post(
                "/ai/chat", data=request_data, files=request_files
            )

            response.raise_for_status()  # Raise exception for 4xx/5xx errors

            data = response.json()
            ai_response = data.get("response", "💀 No response received from AI.")

            if ai_response:
                await update.message.reply_text(ai_response, parse_mode="Markdown")
            else:
                logger.warning(f"Received empty AI response for user {user_id}")
                await update.message.reply_text(
                    "🤔 I received an empty response from the AI. Please try rephrasing your message.",
                    parse_mode="Markdown",
                )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"API Error calling AI endpoint for user {user_id}: {e.response.status_code} - {e.response.text}"
            )
            detail = "Failed to get AI response."
            try:  # Try to get detail from API error response
                error_detail = e.response.json().get("detail")
                if error_detail:
                    detail = f"Failed to get AI response: {error_detail}"
            except Exception:
                pass  # Ignore if parsing fails
            await update.message.reply_text(f"❌ {detail}", parse_mode="Markdown")

        except httpx.RequestError as e:
            logger.error(f"Network Error calling AI endpoint for user {user_id}: {e}")
            await update.message.reply_text(
                "❌ Could not connect to the AI service. Please try again later.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error in handle_ai_text_message for user {user_id}: {e}",
                exc_info=True,
            )
            await update.message.reply_text(
                "❌ An unexpected error occurred while processing your message.",
                parse_mode="Markdown",
            )

    # Bot Handlers
    def add_handlers(self):
        # Commands with user restriction
        if not settings.ALLOWED_USERS or "all" in settings.ALLOWED_USERS:
            allowed_users_filter = filters.ALL
        else:
            usernames = [x for x in settings.ALLOWED_USERS if isinstance(x, str)]
            any_ids = [x for x in settings.ALLOWED_USERS if isinstance(x, int)]
            user_ids = [x for x in any_ids if x > 0]
            group_ids = [x for x in any_ids if x < 0]
            allowed_users_filter = (
                filters.User(username=usernames)
                | filters.User(user_id=user_ids)
                | filters.Chat(chat_id=group_ids)
            )

        self.application.add_handler(
            CommandHandler("start", self.start_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("help", self.help_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler(
                "connect", self.connect_command, filters=allowed_users_filter
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(self.connect_callback, pattern="^connect_")
        )
        self.application.add_handler(
            CommandHandler(
                "callback", self.authorize_callback, filters=allowed_users_filter
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(self.disconnect_callback, pattern="^disconnect_")
        )
        self.application.add_handler(
            CommandHandler(
                "restart", self.restart_command, filters=allowed_users_filter
            )
        )
        self.application.add_handler(
            CommandHandler(
                "account", self.get_user_account, filters=allowed_users_filter
            )
        )
        self.application.add_handler(
            CommandHandler("health", self.health_check, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("post", self.post, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler(
                "connection_status",
                self.connection_status,
                filters=allowed_users_filter,
            )
        )
        self.application.add_handler(
            CommandHandler("status", self.status_command, filters=allowed_users_filter)
        )
        self.application.add_handler(
            CommandHandler("unknown", self.unknown, filters=filters.COMMAND)
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.refresh_status_callback, pattern="^refresh_status_"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.manage_connections_callback, pattern="^manage_connections_"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.connection_done_callback, pattern="^connection_done_"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(self.post_platform_callback, pattern="^post_platform_")
        )
        self.application.add_handler(
            MessageHandler(
                filters.TEXT
                | filters.PHOTO
                | filters.VIDEO
                | filters.VOICE & ~filters.COMMAND & allowed_users_filter,
                self.handle_ai_text_message,
            )
        )
        self.application.add_handler(
            MessageHandler(
                filters.ALL & ~filters.COMMAND & ~filters.TEXT & allowed_users_filter,
                self.handle_message,
            )
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
