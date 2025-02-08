# Threads Auth Controller
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
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=YOYOYO"
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
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=YOYOYO"
            # return RedirectResponse(url=bot_url)
            
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
                    redirect_url=f"https://t.me/{settings.TELEGRAM_BOTNAME}?start=YOYOYO"
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
        """Command handler for /disconnect_threads"""
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
            # Try to make a simple API call to verify credentials
            async with API(credentials=Threads.from_dict(credentials)) as api:
                await api.threads()
            return True
        except:
            raise HTTPException(status_code=404, detail="User not connected to Threads")


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
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)