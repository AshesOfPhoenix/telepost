# Threads Auth Controller
from datetime import datetime, timezone
import json
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import HTTPException
from api.utils.logger import logger
from fastapi.routing import APIRoute
from fastapi import APIRouter, Request

from api.utils.config import get_settings
from pytwitter import Api
from api.base.auth_handler_base import AuthHandlerBase
from api.utils.prompts import SUCCESS_PAGE_HTML

settings = get_settings()

router = APIRouter()
class TwitterAuthHandler(AuthHandlerBase):
    def __init__(self):
        super().__init__(provider_id="twitter")      
        self.config = Api(
            client_id=settings.TWITTER_CLIENT_ID, 
            client_secret=settings.TWITTER_CLIENT_SECRET, 
            oauth_flow=True,
            scopes=["tweet.read", "tweet.write", "users.read"],
            callback_uri=f"{settings.API_PUBLIC_URL}{settings.TWITTER_REDIRECT_URI}"
        )
        logger.info("✅ TwitterAuthHandler initialized")
    
    async def authorize(self, request: Request):
        """Command handler for /connect"""
        logger.info(f"Generating Twitter authorization URL")
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
        
        authorization_url, code_verifier, state = self.config.get_oauth2_authorize_url(
            redirect_uri=f"{settings.API_PUBLIC_URL}{settings.TWITTER_REDIRECT_URI}",
            scope=["tweet.read", "tweet.write", "users.read"] 
        )
        
        logger.info(f"Authorization URL: {authorization_url}")
        logger.info(f"Code Verifier: {code_verifier}")
        logger.info(f"State: {state}")
        
        self.store_state(user_id, state, code_verifier)
        
        return {"url": authorization_url}
    
    async def complete_authorization(self, request: Request):
        """Command handler for /callback"""
        logger.info(f"Processing Twitter authorization callback with params: {request.query_params}")
        params = dict(request.query_params)
        state = params.get('state')
        user_id = self.get_user_id_from_state(state)
        code_verifier = self.get_code_verifier_from_state(state)
        
        logger.info(f"State: {state}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Code Verifier: {code_verifier}")
        
        if not user_id:
            logger.error("Invalid state or user_id not found")
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
            
            credentials = self.config.generate_oauth2_access_token(response=callback_url, code_verifier=code_verifier)
            
            logger.info(f"Credentials: {credentials}")
            
            # Store credentials in database
            await self.store_user_credentials(user_id, credentials)
            logger.info(f"Successfully stored credentials for user {user_id}")
            
            # Clean up state
            self.clear_state(user_id)
            
            # Redirect to Telegram bot with success parameter
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=auth_success_{user_id}"
            
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    platform="Twitter",
                    redirect_url=bot_url
                ),
                status_code=200
            )
            
        except Exception as e:
            logger.error(f"Error getting OAuth2 token: {e}")
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    platform="Twitter",
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
        
    async def disconnect(self, request: Request):
        """Command handler for /disconnect_twitter"""
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        self.clear_state(user_id)
        
        await self.db.delete_user_credentials(user_id, self.provider_id)
        return {"status": "ok"}
        
    async def verify_credentials(self, user_id: int):
        """Verify if stored credentials are valid"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            return False
        
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Check if token is expired
            if credentials.get("expires_at", 0) < datetime.now().timestamp():
                await self.delete_user_credentials(user_id)
                return False
                
            # Create API client with access token
            my_api = Api(
                bearer_token=credentials.get("access_token"),
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True
            )
            
            # Make a lightweight call to verify token
            my_api.get_me()
            return True
        except Exception as e:
            logger.error(f"Error verifying Twitter credentials: {str(e)}")
            return False

    async def check_credentials_expiration(self, user_id: int) -> bool:
        """Check if credentials are expired"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            return True
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Twitter uses expires_at in UNIX timestamp format
            expires_at = credentials.get("expires_at", 0)
            return expires_at < datetime.now().timestamp()
        except Exception as e:
            logger.error(f"Error checking Twitter credentials expiration: {str(e)}")
            return True
            
    def calculate_expiration_time(self, credentials) -> int:
        """Calculate time until token expiration in seconds"""
        if not credentials:
            return 0
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Twitter uses expires_at timestamp
            expires_at = credentials.get("expires_at", 0)
            now = datetime.now().timestamp()
            
            return max(0, int(expires_at - now))
        except Exception as e:
            logger.error(f"Error calculating Twitter expiration time: {str(e)}")
            return 0
    
    def can_refresh_token(self, credentials) -> bool:
        """Check if token can be refreshed"""
        if not credentials:
            return False
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Twitter OAuth 2.0 tokens can be refreshed if refresh_token is present
            # and the token is not too old
            if credentials.get("refresh_token") and self.calculate_expiration_time(credentials) > -86400:  # Within 24h of expiry
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking if Twitter token can be refreshed: {str(e)}")
            return False
            
    async def refresh_token(self, user_id: int) -> bool:
        """Refresh the user's access token"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            return False
            
        try:
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
                
            # Check if token can be refreshed
            if not self.can_refresh_token(credentials):
                return False
                
            # Use the Twitter OAuth2 API to refresh the token
            refresh_token = credentials.get("refresh_token")
            if not refresh_token:
                return False
                
            # Create a new API instance for refreshing
            api = Api(
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True
            )
            
            # Generate a new token using the refresh token
            new_credentials = api.refresh_oauth2_token(refresh_token)
            
            # Store the new credentials
            await self.store_user_credentials(user_id, new_credentials)
            return True
        except Exception as e:
            logger.error(f"Error refreshing Twitter token: {str(e)}")
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
        
        token_validity = await self.get_token_validity(user_id)
        
        # If token is invalid but can be refreshed, try refreshing it
        if not token_validity["valid"] and token_validity["refresh_possible"]:
            refresh_success = await self.refresh_token(user_id)
            if refresh_success:
                # Get updated token validity
                token_validity = await self.get_token_validity(user_id)
                token_validity["refreshed"] = True
        
        return token_validity


auth_handler = TwitterAuthHandler()

# Define routes using the new approach
routes = [
    APIRoute(
        path="/connect",
        endpoint=auth_handler.authorize,
        methods=["GET"],
        name="authorize",
        summary="Authorize user",
        description="Authorize user to connect to Twitter",
        tags=["twitter", "auth"]
    ),
    APIRoute(
        path="/callback",
        endpoint=auth_handler.complete_authorization,
        methods=["GET"],
        name="callback",
        summary="Complete authorization",
        description="Complete authorization for Twitter",
        tags=["twitter", "auth"]
    ),
    APIRoute(
        path="/disconnect",
        endpoint=auth_handler.disconnect,
        methods=["POST"],
        name="disconnect",
        summary="Disconnect from Twitter",
        description="Disconnect from Twitter",
        tags=["twitter", "auth"]
    ),
    APIRoute(
        path="/is_connected",
        endpoint=auth_handler.is_connected,
        methods=["GET"],
        name="is_connected",
        summary="Check if user is connected to Twitter",
        description="Check if user is connected to Twitter",
        tags=["twitter", "auth"]
    ),
    APIRoute(
        path="/token_validity",
        endpoint=auth_handler.token_validity,
        methods=["GET"],
        name="token_validity",
        summary="Check if user token is valid",
        description="Check if user token is valid and return detailed info",
        tags=["twitter", "auth"]
    ),
    APIRoute(
        path="/refresh_token",
        endpoint=auth_handler.refresh_token,
        methods=["POST"],
        name="refresh_token",
        summary="Refresh user token",
        description="Refresh user token if it can be refreshed",
        tags=["twitter", "auth"]
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)