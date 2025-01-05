# Threads Controller
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import ThreadsAccountResponse, ThreadsInsightsResponse, get_settings
from fastapi import APIRouter, Depends, Request
from pythreads.configuration import Configuration
from pythreads.api import API
from pythreads.threads import Threads
from pythreads.credentials import Credentials
from api.db.database import db
from api.base.social_controller_base import SocialController

settings = get_settings()

class ThreadsController(SocialController):
    def __init__(self):
        super().__init__(provider_id="threads")
        self.config = Configuration(
            scopes=["threads_basic", "threads_content_publish", "threads_manage_insights"], 
            app_id=settings.THREADS_APP_ID, 
            api_secret=settings.THREADS_APP_SECRET, 
            redirect_uri=f"{settings.API_PUBLIC_URL}{settings.THREADS_REDIRECT_URI}"
        )
        logger.info("✅ ThreadsController initialized")
        
    async def get_user_account(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            
            credentials = await self.get_user_credentials(user_id)
            
            if not credentials:
                return {"status": "missing", "message": "❌ User not connected to Threads"}
            
            # Convert credentials from JSON string to Threads credentials object
            threads_credentials = Credentials.from_json(credentials)
            logger.info(f"Credentials: {threads_credentials}")
            
            async with API(credentials=threads_credentials) as api:
                account: ThreadsAccountResponse = await api.account()
                # 'views', 'likes', 'replies', 'reposts', 'quotes', 'followers_count', 'follower_demographics'
                insights: ThreadsInsightsResponse = await api.user_insights(
                    metrics=['views', 'likes', 'replies', 'reposts', 'quotes', 'followers_count'],
                )
                # Convert account data to a dictionary
                logger.info(f"Account: {account}")
                logger.info(f"Insights: {insights}")
                likes = insights.get_total_likes()
                replies = insights.get_total_replies()
                reposts = insights.get_total_reposts()
                quotes = insights.get_total_quotes()
                followers_count = insights.get_total_followers()
                
                account_data = {
                    "id": account.id,
                    "username": account.username,
                    "biography": account.threads_biography,
                    "profile_picture_url": account.threads_profile_picture_url,
                    #"views": insights.get("views"),
                    "likes": likes,
                    "replies": replies,
                    "reposts": reposts,
                    "quotes": quotes,
                    "followers_count": followers_count,
                }
                logger.info(f"Account data: {account_data}")
                return account_data
                
        except Exception as e:
            logger.error(f"Error getting user account: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    async def post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            message = params.get('message')
            image_url = params.get('image_url')
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                return {"status": "missing", "message": "❌ User not connected to Threads"}
            
            threads_credentials = Credentials.from_json(credentials)
            logger.info(f"Credentials: {threads_credentials}")
            
            async with API(credentials=threads_credentials) as api:
                # Create a container
                container_id = await api.create_container(message)
                
                # Check the container status
                create_status = await api.container_status(container_id)
                logger.info(f"Create Status: {create_status}")
                
                # state
                create_state = create_status.status.value
                logger.info(f"Create State: {create_state}")
                
                # Publish the container
                result_id = await api.publish_container(container_id)
                
                # Check the container status
                publish_status = await api.container_status(container_id)
                logger.info(f"Publish Status: {publish_status}")
                
                publish_state = publish_status.status.value
                logger.info(f"Publish State: {publish_state}")

                if publish_state == "PUBLISHED":
                    thread = await api.thread(result_id)
                    logger.info(f"Thread: {thread}")
                    return {
                        "status": "success",
                        "message": "Thread posted successfully.",
                        "result_id": result_id,
                        "thread": thread
                    }
                else:
                    return {"status": "error", "message": f"Failed to publish thread. State: {publish_state}"}
            
        except Exception as e:
            logger.error(f"Error posting thread: {str(e)}")
            return {"status": "error", "message": str(e)}
    

threads_controller = ThreadsController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=threads_controller.get_user_account,
        methods=["GET"],
        name="get_user_account"
    ),
    APIRoute(
        path="/post",
        endpoint=threads_controller.post,
        methods=["POST"],
        name="post_thread"
    )
]

for route in routes:
    router.routes.append(route)