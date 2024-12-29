# Threads Auth Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from pydantic import BaseModel
from fastapi import APIRouter, Request
from pythreads import threads, configuration
from pythreads.configuration import Configuration
from pythreads.credentials import Credentials
from pythreads.threads import Threads
from pythreads.api import API
from api.config import get_settings
from api.database import db

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
            return {"status": "error", "message": "Invalid state"}

        try:
            # Complete authorization
            logger.info(f"Callback URL: {str(request.url)}")
            # Check if the request was originally HTTPS
            forwarded_proto = request.headers.get('x-forwarded-proto', 'http')
            base_url = str(request.base_url)
            if forwarded_proto == 'https':
                base_url = 'https://' + base_url[7:]
            
            callback_url = str(base_url.replace('http://', 'https://')) + str(request.url.path) + '?' + str(request.url.query)
            
            credentials = Threads.complete_authorization(callback_url=callback_url, state=state_key, config=self.config)
            
            #! TODO Store credentials in database
            await self.db.store_user_threads_credentials(user_id, credentials.to_json())
            
            # Clean up state
            del self.states[user_id]
            
            # Notify user through Telegram
            # await self.bot.send_message(
            #     chat_id=user_id,
            #     text="Successfully connected your Threads account! ✅"
            # )
            
            return {"status": "success"}
            
        except Exception as e:
            # await self.bot.send_message(
            #     chat_id=user_id,
            #     text=f"Failed to connect Threads account: {str(e)}"
            # )
            return {"status": "error", "message": str(e)}
        
    async def disconnect_threads(self, request: Request):
        """Command handler for /disconnect_threads"""
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
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)