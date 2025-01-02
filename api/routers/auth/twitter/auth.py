# Threads Auth Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from pydantic import BaseModel
from fastapi import APIRouter, Request

from api.utils.config import get_settings
from api.db.database import db
from api.base.auth_handler_base import AuthHandlerBase
settings = get_settings()

router = APIRouter()


class TwitterAuthHandler(AuthHandlerBase):
    def __init__(self):
        super().__init__(provider_id="twitter")        
        logger.info("TwitterAuthHandler initialized")
    
    async def authorize(self, request: Request):
        """Command handler for /connect_twitter"""
        params = dict(request.query_params)
        user_id = params.get('user_id')
        self.store_state(user_id, params.get('state'))
        pass
    
    async def complete_authorization(self, request: Request):
        """Command handler for /connect_twitter"""
        params = dict(request.query_params)
        user_id = self.get_user_id_from_state(params.get('state'))
        pass
        
    async def disconnect(self, request: Request):
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
        endpoint=auth_handler.authorize,
        methods=["GET"],
        name="authorize"
    ),
    APIRoute(
        path="/callback",
        endpoint=auth_handler.complete_authorization,
        methods=["GET"],
        name="callback"
    ),
    APIRoute(
        path="/disconnect",
        endpoint=auth_handler.disconnect,
        methods=["POST"],
        name="disconnect"
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)