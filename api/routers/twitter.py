# Threads Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import get_settings
from fastapi import APIRouter, Depends, Request

from api.base.social_controller_base import SocialController
settings = get_settings()

class TwitterController(SocialController):
    def __init__(self):
        super().__init__(provider_id="twitter")
        logger.info("✅ TwitterController initialized")
        
    async def get_user_account(self, request: Request):
        try:
            pass
                
        except Exception as e:
            logger.error(f"Error getting user account: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    async def post_thread(self, request: Request):
        try:
            pass
            
        except Exception as e:
            logger.error(f"Error posting thread: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def disconnect(self, user_id: int) -> bool:
        return await self.db.delete_user_twitter_credentials(user_id)

twitter_controller = TwitterController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=twitter_controller.get_user_account,
        methods=["GET"],
        name="get_user_account"
    ),
    APIRoute(
        path="/post",
        endpoint=twitter_controller.post_thread,
        methods=["POST"],
        name="post_thread"
    )
]

for route in routes:
    router.routes.append(route)