# Threads Auth Controller
from datetime import datetime, timezone
import json
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi import HTTPException
from api.utils.logger import logger
from fastapi.routing import APIRoute
from fastapi import APIRouter, Request
from pythreads.configuration import Configuration
from pythreads.threads import Threads
from pythreads.api import API
from api.utils.config import get_settings
from api.utils.prompts import SUCCESS_PAGE_HTML
from api.base.auth_handler_base import AuthHandlerBase

settings = get_settings()

router = APIRouter()

class ThreadsAuthHandler(AuthHandlerBase):
    def __init__(self):
        super().__init__(provider_id="threads")
        self.config = Configuration(
            scopes=["threads_basic", "threads_content_publish", "threads_manage_insights"], 
            app_id=settings.THREADS_APP_ID, 
            api_secret=settings.THREADS_APP_SECRET, 
            redirect_uri=f"{settings.API_PUBLIC_URL}{settings.THREADS_REDIRECT_URI}"
        )
        logger.info("✅ ThreadsAuthHandler initialized")
    
    async def authorize(self, request: Request):
        """Command handler for /connect"""
        logger.info("Generating Threads authorization URL")
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        auth_url, state_key = Threads.authorization_url(self.config)
        
        self.store_state(user_id, state_key)
        
        return {"url": auth_url}
    
    async def complete_authorization(self, request: Request):
        """Command handler for /callback"""
        params = dict(request.query_params)
    
        state_key = params.get('state')
        user_id = self.get_user_id_from_state(state_key)

        if not user_id:
            logger.error("Invalid state or user_id not found")
            # f"https://t.me/{settings.TELEGRAM_BOTNAME}?callback=auth_error_{user_id}"
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=auth_error_invalid_state"
            return RedirectResponse(url=bot_url)
        
        try:
            # Complete authorization
            logger.info(f"Processing authorization callback for user {user_id}")
            
            # Check if the request was originally HTTPS
            forwarded_proto = request.headers.get('x-forwarded-proto', 'http')
            base_url = str(request.base_url)
            if forwarded_proto == 'https':
                base_url = 'https://' + base_url[7:]
            
            callback_url = str(base_url.replace('http://', 'https://')) + str(request.url.path) + '?' + str(request.url.query)
            logger.info(f"Using callback URL: {callback_url}")
            
            credentials = Threads.complete_authorization(callback_url=callback_url, state=state_key, config=self.config)
            
            # Store credentials in database
            await self.store_user_credentials(user_id, credentials)
            logger.info(f"Successfully stored credentials for user {user_id}")
            
            # Clean up state
            self.clear_state(user_id)
            
            # Redirect to Telegram bot with success parameter
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=auth_success_{user_id}"
            
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    platform="Threads",
                    redirect_url=bot_url
                ),
                status_code=200
            )
            
        except Exception as e:
            logger.error(f"Error during authorization: {str(e)}")
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    platform="Threads",
                    redirect_url=f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=auth_error_{user_id}"
                ).replace(
                    "Successfully Connected!",
                    "Connection Failed"
                ).replace(
                    "✅",
                    "❌"
                ).replace(
                    "#4CAF50",
                    "#f44336"
                ).replace(
                    "Your Threads account has been connected successfully.",
                    f"Error: {str(e)}"
                ),
                status_code=400
            )
    
    async def verify_credentials(self, user_id: int):
        """Verify if stored credentials are valid"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            return False
            
        try:
            # Try to make a simple API call to verify credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            threads_credentials = Threads.from_dict(credentials)
            
            # Check expiration
            expiration_datetime = threads_credentials.expiration
            current_time = datetime.now(timezone.utc)
            if expiration_datetime < current_time:
                await self.delete_user_credentials(user_id)
                return False
                
            async with API(credentials=threads_credentials) as api:
                await api.threads()
            return True
        except Exception as e:
            logger.error(f"Error verifying credentials: {str(e)}")
            return False

    async def check_credentials_expiration(self, user_id: int) -> bool:
        """Check if credentials are expired"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            return True
        
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
            
            # "expiration": "2025-04-09T09:06:20.800964+00:00"
            # convert to utc
            expiration = datetime.strptime(credentials.get("expiration"), "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone.utc)
            return expiration < datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error checking credentials expiration: {str(e)}")
            return True
    
    def calculate_expiration_time(self, credentials) -> int:
        """Calculate time until token expiration in seconds"""
        if not credentials:
            return 0
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # "expiration": "2025-04-09T09:06:20.800964+00:00"
            expiration_str = credentials.get("expiration")
            if not expiration_str:
                return 0
                
            expiration = datetime.strptime(expiration_str, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            
            return max(0, int((expiration - now).total_seconds()))
        except Exception as e:
            logger.error(f"Error calculating expiration time: {str(e)}")
            return 0
    
    def can_refresh_token(self, credentials) -> bool:
        """Check if token can be refreshed"""
        # Threads uses long-lived tokens that can be refreshed before expiration
        if not credentials:
            return False
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Check if token is a long-lived token (can be refreshed)
            return credentials.get("short_lived", False) == False
        except Exception as e:
            logger.error(f"Error checking if token can be refreshed: {str(e)}")
            return False
    
    async def token_validity(self, request: Request):
        """Check if user token is valid and return detailed info"""
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=400, 
                detail={
                    "status": "error",
                    "code": 400,
                    "message": "User ID is required",
                    "platform": self.provider_id
                }
            )
        
        return await self.get_token_validity(user_id)


auth_handler = ThreadsAuthHandler()

# Define routes using the new approach
routes = [
    APIRoute(
        path="/connect",
        endpoint=auth_handler.authorize,
        methods=["GET"],
        name="authorize",
        summary="Authorize user",
        description="Authorize user to connect to Threads",
        tags=["threads", "auth"]
    ),
    APIRoute(
        path="/callback",
        endpoint=auth_handler.complete_authorization,
        methods=["GET"],
        name="callback",
        summary="Complete authorization",
        description="Complete authorization for Threads",
        tags=["threads", "auth"]
    ),
    APIRoute(
        path="/disconnect",
        endpoint=auth_handler.disconnect,
        methods=["POST"],
        name="disconnect",
        summary="Disconnect from Threads",
        description="Disconnect from Threads",
        tags=["threads", "auth"]
    ),
    APIRoute(
        path="/is_connected",
        endpoint=auth_handler.is_connected,
        methods=["GET"],
        name="is_connected",
        summary="Check if user is connected to Threads",
        description="Check if user is connected to Threads",
        tags=["threads", "auth"]
    ),
    APIRoute(
        path="/token_validity",
        endpoint=auth_handler.token_validity,
        methods=["GET"],
        name="token_validity",
        summary="Check if user token is valid",
        description="Check if user token is valid and return detailed info",
        tags=["threads", "auth"]
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)