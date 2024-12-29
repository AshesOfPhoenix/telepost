# Threads Auth Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from pydantic import BaseModel
from fastapi import APIRouter, Request

from api.utils.config import get_settings
from api.database import db

settings = get_settings()

router = APIRouter()

# Pydantic models for request/response validation
class TwitterAuthorizeRequest(Request):
    user_id: str

class TwitterAuthHandler:
    def __init__(self):
        self.states = {}
        self.db = db
        
        logger.info("TwitterAuthHandler initialized")
    
    async def authorize_twitter(self, request: Request):
        """Command handler for /connect_twitter"""
        params = dict(request.query_params)
        pass
    
    async def complete_authorization(self, request: Request):
        """Command handler for /connect_twitter"""
        params = dict(request.query_params)
    
        pass
        
    async def disconnect_twitter(self, request: Request):
        """Command handler for /disconnect_twitter"""
        pass
        
    async def verify_credentials(self, user_id: int):
        """Verify if stored credentials are valid"""
        pass


auth_handler = TwitterAuthHandler()

# Define routes using the new approach
routes = [
    APIRoute(
        path="/connect",
        endpoint=auth_handler.authorize_twitter,
        methods=["GET"],
        name="authorize_twitter"
    ),
    APIRoute(
        path="/callback",
        endpoint=auth_handler.complete_authorization,
        methods=["GET"],
        name="twitter_callback"
    ),
    APIRoute(
        path="/disconnect",
        endpoint=auth_handler.disconnect_twitter,
        methods=["POST"],
        name="disconnect_twitter"
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)