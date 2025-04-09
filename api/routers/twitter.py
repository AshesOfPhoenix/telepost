# Twitter Controller
import json
import httpx
from datetime import datetime, timezone
from api.utils.error import handle_twitter_error
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import TwitterAccountResponse, get_settings
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pytwitter import Api

from api.base.social_controller_base import SocialController
from api.routers.auth.twitter.auth import auth_handler as twitter_auth_handler

settings = get_settings()

class TwitterController(SocialController):
    def __init__(self):
        super().__init__(provider_id="twitter")
        self.auth_handler = twitter_auth_handler
        logger.info("✅ TwitterController initialized")
        
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
                    message="User not connected to Twitter"
                )
            
            # Check if credentials are expired
            is_expired = await self.auth_handler.check_credentials_expiration(user_id)
            if is_expired:
                await self.auth_handler.delete_user_credentials(user_id)
                return self.create_error_response(
                    status_code=401,
                    message="Credentials expired"
                )
            
            try:
                # If credentials is a string, parse it; otherwise use as is
                twitter_credentials = credentials
                if isinstance(credentials, str):
                    twitter_credentials = json.loads(credentials)
                
                my_api = Api(
                    bearer_token=twitter_credentials.get("access_token"),
                    client_id=settings.TWITTER_CLIENT_ID,
                    client_secret=settings.TWITTER_CLIENT_SECRET,
                    oauth_flow=True
                )
                
                if not my_api:
                    return self.create_error_response(
                        status_code=500,
                        message="Failed to initialize Twitter API"
                    )

                try:
                    account = my_api.get_me(
                        user_fields="created_at,description,entities,id,location,most_recent_tweet_id,name,pinned_tweet_id,profile_image_url,protected,public_metrics,url,username,verified,verified_type,withheld",
                        tweet_fields="created_at,id,text,public_metrics,entities,attachments,author_id,conversation_id,in_reply_to_user_id,referenced_tweets,source,withheld",
                        expansions="affiliation.user_id,most_recent_tweet_id,pinned_tweet_id",
                        return_json=True
                    )
                    
                    account = TwitterAccountResponse.model_validate(account)
                    account_data = account.data
                    
                    created_at = " ".join(account_data.created_at.replace(".000Z", "").split("T"))
                    public_metrics = account_data.public_metrics
                    
                    account_data = {
                        "platform": "twitter",
                        "username": account_data.username,
                        "name": account_data.name,
                        "biography": account_data.description,
                        "profile_picture_url": account_data.profile_image_url,
                        "id": account_data.id,
                        "verified": account_data.verified,
                        "verified_type": account_data.verified_type,
                        "location": account_data.location,
                        "created_at": created_at,
                        "protected": account_data.protected,
                        "metrics": {
                            "followers_count": public_metrics.followers_count,
                            "following_count": public_metrics.following_count,
                            "tweet_count": public_metrics.tweet_count,
                            "listed_count": public_metrics.listed_count,
                            "like_count": public_metrics.like_count,
                            "media_count": public_metrics.media_count
                        }
                    }
                    
                    return self.create_success_response(
                        data=account_data,
                        message="User account retrieved successfully"
                    )
                    
                except Exception as api_error:
                    error_response = handle_twitter_error(api_error)
                    logger.error(f"Twitter API Error: {error_response}")
                    return self.create_error_response(
                        status_code=error_response.get("code", 500),
                        message=error_response.get("message", str(api_error))
                    )
                
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON Decode Error: {str(json_error)}")
                return self.create_error_response(
                    status_code=500,
                    message="Invalid credentials format"
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
                    message="User not connected to Twitter"
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
            
            my_api = Api(
                bearer_token=credentials.get("access_token"),  # Just pass the access token directly
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True  # Keep OAuth flow enabled for user context
            )
            
            # Handle different posting scenarios
            response = None
            
            if image_url:
                # Twitter API needs to handle media uploads differently
                # For now, just mention that media upload is not implemented
                return self.create_error_response(
                    status_code=501,
                    message="Media upload not implemented yet for Twitter"
                )
            else:
                # Text-only post
                response = my_api.create_tweet(
                    text=message,
                    return_json=True
                )
            
            if not response:
                return self.create_error_response(
                    status_code=500,
                    message="Failed to create tweet"
                )
                
            logger.info(f"Twitter API Response: {response}")
            
            response_data = response.get("data")
            
            # Format tweet details for response
            tweet_data = {
                "id": response_data.get("id"),
                "permalink": f"https://x.com/i/status/{response_data.get('id')}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": message
            }
            
            return self.create_success_response(
                data={"tweet": tweet_data},
                message="Tweet posted successfully"
            )
            
        except Exception as e:
            error_info = handle_twitter_error(e)
            logger.error(f"Twitter API Error: {error_info}")
            return self.create_error_response(
                status_code=error_info.get("code", 500),
                message=error_info.get("message", str(e))
            )
            
    async def delete_post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            tweet_id = params.get('id')
            
            if not user_id or not tweet_id:
                return self.create_error_response(
                    status_code=400,
                    message="User ID and Tweet ID are required"
                )
                
            credentials = await self.auth_handler.get_user_credentials(user_id)
            if not credentials:
                return self.create_error_response(
                    status_code=404,
                    message="User not connected to Twitter"
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
            
            my_api = Api(
                bearer_token=credentials.get("access_token"),  # Just pass the access token directly
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True  # Keep OAuth flow enabled for user context
            )
            
            # Delete the tweet
            response = my_api.delete_tweet(tweet_id)
            
            if not response:
                return self.create_error_response(
                    status_code=500,
                    message="Failed to delete tweet"
                )
                
            logger.info(f"Twitter API Response: {response}")
            
            return self.create_success_response(
                data={"tweet_id": tweet_id},
                message="Tweet deleted successfully"
            )
            
        except Exception as e:
            error_info = handle_twitter_error(e)
            logger.error(f"Twitter API Error: {error_info}")
            return self.create_error_response(
                status_code=error_info.get("code", 500),
                message=error_info.get("message", str(e))
            )
    
    async def disconnect(self, user_id: int) -> bool:
        try:
            await self.db.delete_user_credentials(user_id, self.provider_id)
            return Response(
                status_code=200,
                content={"status": "success", "code": 200, "message": "Disconnected from Twitter successfully."}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error disconnecting from Twitter: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "code": 500,
                    "message": str(e)
                }
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
            
            return self.create_success_response(
                data=validity_info,
                message="Token validity checked successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "checking token validity")

twitter_controller = TwitterController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=twitter_controller.get_user_account,
        methods=["GET"],
        name="get_user_account",
        summary="Get user account info",
        description="Get Twitter user account information",
        tags=["twitter"]
    ),
    APIRoute(
        path="/post",
        endpoint=twitter_controller.post,
        methods=["POST"],
        name="post",
        summary="Post to Twitter",
        description="Post a message to Twitter",
        tags=["twitter"]
    ),
    APIRoute(
        path="/delete_post",
        endpoint=twitter_controller.delete_post,
        methods=["POST"],
        name="delete_post",
        summary="Delete a post",
        description="Delete a post from Twitter",
        tags=["twitter"]
    ),
    APIRoute(
        path="/token_validity",
        endpoint=twitter_controller.token_validity,
        methods=["GET"],
        name="token_validity",
        summary="Check token validity",
        description="Check if user token is valid and return detailed info",
        tags=["twitter"]
    )
]

for route in routes:
    router.routes.append(route)