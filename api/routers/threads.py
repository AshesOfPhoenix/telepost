# Threads Controller
from datetime import datetime, timezone
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import ThreadsAccountResponse, ThreadsInsightsResponse, get_settings
from fastapi import APIRouter, Depends, Request, HTTPException, Response
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
            
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "status": "error",
                        "code": 400,
                        "message": "User ID is required",
                        "platform": "Threads"
                    }
                )
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": "missing",
                        "code": 404,
                        "message": "User not connected to Threads",
                        "platform": "Threads"
                    }
                )
            
            threads_credentials = Credentials.from_json(credentials)
            
            # Check expiration
            expiration_datetime = threads_credentials.expiration
            current_time = datetime.now(timezone.utc)
            if expiration_datetime < current_time:
                await self.db.delete_user_credentials(user_id, self.provider_id)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "status": "expired",
                        "code": 401,
                        "message": "Credentials expired"
                    }
                )
            
            try:
                async with API(credentials=threads_credentials) as api:
                    account_response = await api.account()
                    account = ThreadsAccountResponse.model_validate(account_response)
                    insights_response = await api.user_insights(
                        metrics=['views', 'likes', 'replies', 'reposts', 'quotes', 'followers_count'],
                    )
                    insights = ThreadsInsightsResponse.model_validate(insights_response)
                    
                    return {
                        "status": "success",
                        "code": 200,
                        "data": {
                            "id": account.id,
                            "username": account.username,
                            "biography": account.threads_biography,
                            "profile_picture_url": account.threads_profile_picture_url,
                            "likes": insights.get_total_likes(),
                            "replies": insights.get_total_replies(),
                            "reposts": insights.get_total_reposts(),
                            "quotes": insights.get_total_quotes(),
                            "followers_count": insights.get_total_followers(),
                        }
                    }
                    
            except Exception as api_error:
                logger.error(f"Threads API Error: {str(api_error)}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "error",
                        "code": 500,
                        "message": f"API Error: {str(api_error)}"
                    }
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "code": 500,
                    "message": "An unexpected error occurred"
                }
            )
        
    async def post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            message = params.get('message')
            image_url = params.get('image_url')
            
            if not user_id:
                raise Exception(
                    "User ID is required",
                    platform="Threads",
                    status_code=400,
                    details={"message": "User ID is required"}
                )
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "status": "missing",
                        "code": 404,
                        "message": "User not connected to Threads",
                        "platform": "Threads"
                    }
                )
                
            threads_credentials = Credentials.from_json(credentials)
                
            # Check expiration
            expiration_datetime = threads_credentials.expiration
            current_time = datetime.now(timezone.utc)
            if expiration_datetime < current_time:
                await self.db.delete_user_credentials(user_id)
                raise HTTPException(
                    status_code=401, 
                    detail={
                        "status": "expired",
                        "code": 401,
                        "message": "Credentials expired"
                    }
                )
            
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
                    return Response(
                        status_code=200,
                        content={"status": "success", "code": 200, "message": "Thread posted successfully.", "details": {"result_id": result_id, "thread": thread}}
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "status": "error",
                            "code": 500,
                            "message": f"Failed to publish thread. State: {publish_state}"
                        }
                    )
            
        except HTTPException:
            raise
        except Exception as http_error:
            logger.error(f"HTTP Error: {str(http_error)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "code": 500,
                    "message": str(http_error)
                }
            )
        
    async def disconnect(self, user_id: int) -> bool:
        try:
            await self.db.delete_user_credentials(user_id, self.provider_id)
            return Response(
                status_code=200,
                content={"status": "success", "code": 200, "message": "Disconnected from Threads successfully."}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error disconnecting from Threads: {str(e)}")
            raise HTTPException(status_code=500, detail={
                    "status": "error",
                    "code": 500,
                    "message": str(e)
                }
            )
    

threads_controller = ThreadsController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=threads_controller.get_user_account,
        methods=["GET"],
        name="get_user_account",
        summary="Get user account",
        description="Get user account details from Threads",
        tags=["threads"]
    ),
    APIRoute(
        path="/post",
        endpoint=threads_controller.post,
        methods=["POST"],
        name="post_thread",
        summary="Post a thread",
        description="Post a thread to Threads",
        tags=["threads"]
    )
]

for route in routes:
    router.routes.append(route)