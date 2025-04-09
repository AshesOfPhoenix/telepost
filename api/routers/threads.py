# Threads Controller
from datetime import datetime, timezone
import json
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import ThreadsAccountResponse, ThreadsInsightsResponse, get_settings
from fastapi import APIRouter, Depends, Request, HTTPException, Response
from pythreads.configuration import Configuration
from pythreads.api import API
from pythreads.threads import Threads
from pythreads.credentials import Credentials
from pythreads.api import Media, MediaType
from api.db.database import db
from api.base.social_controller_base import SocialController
from api.routers.auth.threads.auth import auth_handler as threads_auth_handler
import httpx

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
        self.auth_handler = threads_auth_handler
        self.http_client = httpx.AsyncClient(
            headers={
                "Host": settings.API_PUBLIC_URL.split("://")[1],
                "User-Agent": "TelegramBot/1.0",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            timeout=httpx.Timeout(
                connect=5.0, 
                read=30.0,   
                write=30.0,  
                pool=30.0      
            ),
            verify=True
        )
        logger.info("✅ ThreadsController initialized")
        
    async def get_user_account(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            
            if not user_id:
                return self.create_error_response(
                    status_code=400,
                    message="User ID is required"
                )
            
            credentials = await self.auth_handler.get_user_credentials(user_id)
            if not credentials:
                return self.create_error_response(
                    status_code=404,
                    message="User not connected to Threads"
                )
            
            # Check if credentials are expired
            is_expired = await self.auth_handler.check_credentials_expiration(user_id)
            if is_expired:
                await self.auth_handler.delete_user_credentials(user_id)
                return self.create_error_response(
                    status_code=401,
                    message="Credentials expired"
                )
            
            threads_credentials = Credentials.from_json(credentials)
            
            try:
                async with API(credentials=threads_credentials) as api:
                    account_response = await api.account()
                    account = ThreadsAccountResponse.model_validate(account_response)
                    insights_response = await api.user_insights(
                        metrics=['views', 'likes', 'replies', 'reposts', 'quotes', 'followers_count'],
                    )
                    insights = ThreadsInsightsResponse.model_validate(insights_response)
                    
                    account_data = {
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
                    
                    return self.create_success_response(
                        data=account_data,
                        message="User account retrieved successfully"
                    )
                    
            except Exception as api_error:
                logger.error(f"Threads API Error: {str(api_error)}")
                return self.create_error_response(
                    status_code=500,
                    message=f"API Error: {str(api_error)}"
                )
                
        except Exception as e:
            return self.handle_exception(e, "retrieving user account")
        
    async def post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            message = params.get('message', '')
            image_url = params.get('image_url')
            
            if not user_id:
                return self.create_error_response(
                    status_code=400,
                    message="User ID is required"
                )
            
            credentials = await self.auth_handler.get_user_credentials(user_id)
            if not credentials:
                return self.create_error_response(
                    status_code=404,
                    message="User not connected to Threads"
                )
            
            # Check if credentials are expired
            is_expired = await self.auth_handler.check_credentials_expiration(user_id)
            if is_expired:
                await self.auth_handler.delete_user_credentials(user_id)
                return self.create_error_response(
                    status_code=401,
                    message="Credentials expired"
                )
                
            threads_credentials = Credentials.from_json(credentials)
            
            async with API(credentials=threads_credentials) as api:
                container_id = None
                
                # Handle different posting scenarios
                if image_url:
                    # Create a media container
                    media = Media(type=MediaType.IMAGE, url=image_url)
                    container_id = await api.create_container(message, media=media)
                else:
                    # Create a text-only container
                    container_id = await api.create_container(message)
                
                if not container_id:
                    return self.create_error_response(
                        status_code=500,
                        message="Failed to create container"
                    )
                
                # Check the container status
                create_status = await api.container_status(container_id)
                logger.info(f"Create Status: {create_status}")
                
                # If status is not FINISHED, wait a bit and check again
                if create_status.status.value != "FINISHED":
                    # In a real app, this would be handled asynchronously
                    # For now, just return an error
                    return self.create_error_response(
                        status_code=500,
                        message="Container not ready for publishing"
                    )
                
                # Publish the container
                result_id = await api.publish_container(container_id)
                
                # Check the publish status
                publish_status = await api.container_status(container_id)
                logger.info(f"Publish Status: {publish_status}")
                
                if publish_status.status.value == "PUBLISHED":
                    # Get thread details
                    thread = await api.thread(result_id)
                    
                    # Format thread details for response
                    thread_data = {
                        "id": thread["id"],
                        "permalink": f"https://threads.net/@{thread['username']}/post/{thread['id']}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "text": message
                    }
                    
                    return self.create_success_response(
                        data={"thread": thread_data},
                        message="Thread posted successfully"
                    )
                else:
                    return self.create_error_response(
                        status_code=500,
                        message=f"Failed to publish thread. State: {publish_status.status.value}"
                    )
            
        except Exception as e:
            return self.handle_exception(e, "posting thread")
        
    async def delete_post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            thread_id = params.get('id')
            
            if not user_id or not thread_id:
                return self.create_error_response(
                    status_code=400,
                    message="User ID and Thread ID are required"
                )
                
            credentials = await self.auth_handler.get_user_credentials(user_id)
            if not credentials:
                return self.create_error_response(
                    status_code=404,
                    message="User not connected to Threads"
                )
            
            # Check if credentials are expired
            is_expired = await self.auth_handler.check_credentials_expiration(user_id)
            if is_expired:
                # Try to refresh the token
                refresh_success = await self.auth_handler.refresh_token(user_id)
                if not refresh_success:
                    await self.auth_handler.delete_user_credentials(user_id)
                    return self.create_error_response(
                        status_code=401,
                        message="Credentials expired and couldn't be refreshed"
                    )
                # Get refreshed credentials
                credentials = await self.auth_handler.get_user_credentials(user_id)
            
            if isinstance(credentials, str):
                credentials = json.loads(credentials)
            
            # NOT POSSIBLE USING TWITTER PACKAGE; WILL HAVE TO BE DONE USING API
            
            response = await self.http_client.delete(
                f"https://graph.threads.net/v1.0/{thread_id}?access_token={credentials['access_token']}"
            )
            
            if response.status_code != 200:
                return self.create_error_response(
                    status_code=500,
                    message="Failed to delete thread"
                )
            
            return self.create_success_response(
                data={"thread_id": thread_id},
                message="Thread deleted successfully"
            )
            
                
        except Exception as e:
            error_info = handle_threads_error(e)
            logger.error(f"Threads API Error: {error_info}")
            return self.create_error_response(
                status_code=error_info.get("code", 500),
                message=error_info.get("message", str(e))
            )
        
    async def token_validity(self, request: Request):
        """
        Check token validity for a user
        
        Args:
            request: FastAPI request with user_id parameter
            
        Returns:
            Response with token validity information
        """
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            
            if not user_id:
                return self.create_error_response(
                    status_code=400,
                    message="User ID is required"
                )
            
            # Use the auth handler to check token validity
            validity_info = await self.auth_handler.get_token_validity(user_id)
            logger.info(f"Validity info: {validity_info}")
            
            return self.create_success_response(
                data=validity_info,
                message="Token validity checked successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "checking token validity")


threads_controller = ThreadsController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=threads_controller.get_user_account,
        methods=["GET"],
        name="get_user_account",
        summary="Get user account info",
        description="Get Threads user account information",
        tags=["threads"]
    ),
    APIRoute(
        path="/post",
        endpoint=threads_controller.post,
        methods=["POST"],
        name="post",
        summary="Post to Threads",
        description="Post a message to Threads",
        tags=["threads"]
    ),
    APIRoute(
        path="/delete_post",
        endpoint=threads_controller.delete_post,
        methods=["POST"],
        name="delete_post",
        summary="Delete a post",
        description="Delete a post by its ID",
        tags=["threads"]
    ),
    APIRoute(
        path="/token_validity",
        endpoint=threads_controller.token_validity,
        methods=["GET"],
        name="token_validity",
        summary="Check token validity",
        description="Check if user token is valid and return detailed info",
        tags=["threads"]
    )
]

# Add routes to the router
for route in routes:
    router.routes.append(route)