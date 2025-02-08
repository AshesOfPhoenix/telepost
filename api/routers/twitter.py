# Threads Controller
import json
import aiohttp
from datetime import datetime
from api.utils.error import handle_twitter_error
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import TwitterAccountResponse, get_settings
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pytwitter import Api

from api.base.social_controller_base import SocialController

settings = get_settings()

class TwitterController(SocialController):
    def __init__(self):
        super().__init__(provider_id="twitter")
        # self.config = Api(
        #     client_id=settings.TWITTER_CLIENT_ID, 
        #     client_secret=settings.TWITTER_CLIENT_SECRET, 
        #     oauth_flow=True,
        #     scopes=["tweet.read", "tweet.write", "users.read"],
        #     callback_uri=f"{settings.API_PUBLIC_URL}{settings.TWITTER_REDIRECT_URI}"
        # )
        logger.info("✅ TwitterController initialized")
        
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
                        "message": "User ID is required"
                    }
                )
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": "missing",
                        "code": 404,
                        "message": "User not connected to Twitter"
                    }
                )
            
            try:
                logger.info(f"Credentials: {type(credentials)}")
                # If credentials is a string, parse it; otherwise use as is
                twitter_credentials = credentials
                if isinstance(credentials, str):
                    twitter_credentials = json.loads(credentials)
                
                # Now twitter_credentials is guaranteed to be a dict
                if twitter_credentials.get("expires_at") < datetime.now().timestamp():
                    await self.db.delete_user_credentials(user_id, self.provider_id)
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "status": "expired",
                            "code": 401,
                            "message": "Credentials expired"
                        }
                    )
                
                my_api = Api(
                    bearer_token=twitter_credentials.get("access_token"),
                    client_id=settings.TWITTER_CLIENT_ID,
                    client_secret=settings.TWITTER_CLIENT_SECRET,
                    oauth_flow=True
                )
                
                if not my_api:
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "status": "error",
                            "code": 404,
                            "message": "Failed to initialize Twitter API"
                        }
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
                    
                    return Response(
                        status_code=200,
                        content=json.dumps({
                            "status": "success",
                            "code": 200,
                            "data": account_data
                        }),
                        media_type="application/json"
                    )
                    
                except Exception as api_error:
                    error_response = handle_twitter_error(api_error)
                    logger.error(f"Twitter API Error: {error_response}")
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "status": "error",
                            "code": error_response.get("code", 500),
                            "message": error_response.get("message", str(api_error))
                        }
                    )
                
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON Decode Error: {str(json_error)}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "error",
                        "code": 500,
                        "message": "Invalid credentials format"
                    }
                )
            
        except HTTPException as http_error:
            raise HTTPException(
                status_code=http_error.status_code,
                detail={
                    "status": "error",
                    "code": http_error.status_code,
                    "message": http_error.detail
                }
            )
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
                raise HTTPException(
                    status_code=400,
                    detail={
                        "status": "error",
                        "code": 400,
                        "message": "User ID is required"
                    }
                )
                
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": "missing",
                        "code": 404,
                        "message": "User not connected to Twitter"
                    }
                )
            
            if credentials.get("expires_at") < datetime.now().timestamp():
                await self.disconnect(user_id)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "status": "expired",
                        "code": 401,
                        "message": "Credentials expired"
                    }
                )
            
            my_api = Api(
                bearer_token=credentials.get("access_token"),  # Just pass the access token directly
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True  # Keep OAuth flow enabled for user context
            )
            
            response = my_api.create_tweet(
                text=message,
                return_json=True
            )
            # {'data': {'edit_history_tweet_ids': ['1875842406307737626'], 'id': '1875842406307737626', 'text': 'yolo'}}
            logger.info(f"Response: {response}")
            
            response_data = response.get("data")
            
            response_data["permalink"] = f"https://x.com/{user_id}/status/{response_data.get('id')}"
            response_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return Response(
                status_code=200,
                content={"status": "success", "code": 200, "message": "Tweet posted successfully", "details": {"tweet": response_data}}
            )
            
        except HTTPException:
            raise
        except Exception as e:
            error_response = handle_twitter_error(e)
            logger.error(f"Twitter API Error: {error_response}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "code": 500,
                    "message": str(e)
                }
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

twitter_controller = TwitterController()

router = APIRouter()

routes = [
    APIRoute(
        path="/user_account",
        endpoint=twitter_controller.get_user_account,
        methods=["GET"],
        name="get_user_account",
        summary="Get user account",
        description="Get user account details from Twitter",
        tags=["twitter"]
    ),
    APIRoute(
        path="/post",
        endpoint=twitter_controller.post,
        methods=["POST"],
        name="post_tweet",
        summary="Post a tweet",
        description="Post a tweet to Twitter",
        tags=["twitter"]
    )
]

for route in routes:
    router.routes.append(route)