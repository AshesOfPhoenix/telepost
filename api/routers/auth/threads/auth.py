# Threads Auth Controller
from fastapi.responses import RedirectResponse, HTMLResponse
from api.utils.logger import logger
from fastapi.routing import APIRoute
from pydantic import BaseModel
from fastapi import APIRouter, Request
from pythreads import threads, configuration
from pythreads.configuration import Configuration
from pythreads.credentials import Credentials
from pythreads.threads import Threads
from pythreads.api import API
from api.utils.config import get_settings
from api.database import db
from api.utils.prompts import SUCCESS_PAGE_HTML

settings = get_settings()

router = APIRouter()

# Pydantic models for request/response validation
class ThreadsAuthorizeRequest(Request):
    user_id: str

class ThreadsAuthHandler:
    def __init__(self):
        self.states = {}
        self.db = db
        self.config = Configuration(
            scopes=["threads_basic", "threads_content_publish", "threads_manage_insights"], 
            app_id=settings.THREADS_APP_ID, 
            api_secret=settings.THREADS_APP_SECRET, 
            redirect_uri=settings.THREADS_REDIRECT_URI
        )
        logger.info("ThreadsAuthHandler initialized")
    
    async def authorize_threads(self, request: Request):
        """Command handler for /connect_threads"""
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        auth_url, state_key = Threads.authorization_url(self.config)
        
        self.states[user_id] = state_key
        
        return {"url": auth_url}
    
    async def complete_authorization(self, request: Request):
        """Command handler for /connect_threads"""
        params = dict(request.query_params)
    
        # Extract user_id from state (you'll need to modify the state to include user_id)
        state_key = params.get('state')
        user_id = None
        
        for uid, stored_state in self.states.items():
            if stored_state == state_key:
                user_id = uid
                break
                
        if not user_id:
            logger.error("Invalid state or user_id not found")
            bot_url = f"https://t.me/{settings.TELEGRAM_BOTNAME}?command=connect_callback&auth_error_invalid_state"
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
            await self.db.store_user_threads_credentials(user_id, credentials.to_json())
            logger.info(f"Successfully stored credentials for user {user_id}")
            
            # Clean up state
            del self.states[user_id]
            
            # Redirect to Telegram bot with success parameter
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    telegram_botname=settings.TELEGRAM_BOTNAME
                ),
                status_code=200
            )
            
        except Exception as e:
            logger.error(f"Error during authorization: {str(e)}")
            return HTMLResponse(
                content=SUCCESS_PAGE_HTML.format(
                    telegram_botname=settings.TELEGRAM_BOTNAME
                ).replace(
                    "Successfully Connected!",
                    "Connection Failed"
                ).replace(
                    "✓",
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
        
    async def disconnect_threads(self, request: Request):
        """Command handler for /disconnect_threads"""
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        await self.db.delete_user_threads_credentials(user_id)
        return {"status": "ok"}
        
    async def verify_credentials(self, user_id: int):
        """Verify if stored credentials are valid"""
        credentials = await self.db.get_user_threads_credentials(user_id)
        if not credentials:
            return False
            
        try:
            # Try to make a simple API call to verify credentials
            async with API(credentials=Threads.from_dict(credentials)) as api:
                await api.threads()
            return True
        except:
            return False
        
    async def is_connected(self, user_id: int):
        """Check if the user is connected to Threads"""
        credentials = await self.db.get_user_threads_credentials(user_id)
        return credentials is not None


auth_handler = ThreadsAuthHandler()

# Define routes using the new approach
routes = [
    APIRoute(
        path="/connect",
        endpoint=auth_handler.authorize_threads,
        methods=["GET"],
        name="authorize_threads"
    ),
    APIRoute(
        path="/callback",
        endpoint=auth_handler.complete_authorization,
        methods=["GET"],
        name="threads_callback"
    ),
    APIRoute(
        path="/disconnect",
        endpoint=auth_handler.disconnect_threads,
        methods=["POST"],
        name="disconnect_threads"
    ),
    APIRoute(
        path="/is_connected",
        endpoint=auth_handler.is_connected,
        methods=["GET"],
        name="is_connected"
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)