# Threads Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.config import get_settings
from fastapi import APIRouter, Depends, Request
from pythreads.configuration import Configuration
from pythreads.api import API
from pythreads.threads import Threads
from pythreads.credentials import Credentials
from api.database import db

settings = get_settings()

class ThreadsController:
    def __init__(self):
        self.db = db
        self.config = Configuration(
            scopes=["threads_basic", "threads_content_publish", "threads_manage_insights"], 
            app_id=settings.THREADS_APP_ID, 
            api_secret=settings.THREADS_APP_SECRET, 
            redirect_uri=settings.THREADS_REDIRECT_URI
        )
        logger.info("ThreadsController initialized")
        
    async def get_user_account(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            
            credentials = await self.db.get_user_threads_credentials(user_id)
            
            if not credentials:
                return {"status": "error", "message": "User not connected to Threads"}
            
            # Convert credentials from JSON string to Threads credentials object
            threads_credentials = Credentials.from_json(credentials)
            logger.info(f"Credentials: {threads_credentials}")
            
            async with API(credentials=threads_credentials) as api:
                account = await api.account()
                # Convert account data to a dictionary
                logger.info(f"Account: {account}")
                account_data = {
                    "username": account.get("username"),
                    "biography": account.get("threads_biography"),
                    "profile_picture_url": account.get("threads_profile_picture_url"),
                    "id": account.get("id")
                }
                return account_data
                
        except Exception as e:
            logger.error(f"Error getting user account: {str(e)}")
            return {"status": "error", "message": str(e)}
    

threads_controller = ThreadsController()

router = APIRouter()


routes = [
    APIRoute(
        path="/get_user_account",
        endpoint=threads_controller.get_user_account,
        methods=["GET"],
        name="get_user_account"
    )
]

for route in routes:
    router.routes.append(route)