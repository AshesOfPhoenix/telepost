# Threads Controller
import aiohttp
from datetime import datetime
from api.utils.error import handle_twitter_error
from api.utils.logger import logger
from fastapi.routing import APIRoute
from api.utils.config import TwitterAccountResponse, get_settings
from fastapi import APIRouter, Depends, Request
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
                raise Exception("User ID is required")
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                return {"status": "missing", "message": "❌ User not connected to Twitter"}
            
            # {
            #     "access_token": "access_token",
            #     "token_type": "bearer",
            #     "scope": "tweet.read tweet.write users.read",
            #     "expires_in": 1719859200
            #     "expires_at": 1719859200
            # }
            logger.info(f"Credentials: {credentials}")
            
            my_api = Api(
                bearer_token=credentials.get("access_token"),  # Just pass the access token directly
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                oauth_flow=True  # Keep OAuth flow enabled for user context
            )
            logger.info(f"My API user id: {my_api.auth_user_id}")
                       
            account = my_api.get_me(
                user_fields="created_at,description,entities,id,location,most_recent_tweet_id,name,pinned_tweet_id,profile_image_url,protected,public_metrics,url,username,verified,verified_type,withheld",
                tweet_fields="created_at,id,text,public_metrics,entities,attachments,author_id,conversation_id,in_reply_to_user_id,referenced_tweets,source,withheld",
                expansions="affiliation.user_id,most_recent_tweet_id,pinned_tweet_id",
                return_json=True
            )
            logger.info(f"Account with my_api: {account}")
            
            account = TwitterAccountResponse.model_validate(account)
            logger.info(f"Account with model_validate: {account}")
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
                # Added fields
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
            return account_data
            
            
            """ async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"{credentials.get('token_type')} {credentials.get('access_token')}",
                    "Content-Type": "application/json",
                    "User-Agent": "MyTwitterApp/1.0"
                }
                
                # Call the /me endpoint with user fields
                async with session.get(
                    "https://api.twitter.com/2/users/me",
                    headers=headers,
                    params={"user.fields": "created_at,description,entities,id,location,most_recent_tweet_id,name,pinned_tweet_id,profile_image_url,protected,public_metrics,url,username,verified,verified_type,withheld"}
                ) as response:
                    data = await response.json()
                    logger.info(f"Twitter API response: {data}")
                    
                    if "data" in data:
                        user_data = data["data"]
                        public_metrics = user_data.get("public_metrics", {})
                        account_data = {
                            "platform": "twitter",
                            "username": user_data.get("username"),
                            "name": user_data.get("name"),
                            "biography": user_data.get("description"),
                            "profile_picture_url": user_data.get("profile_image_url"),
                            "id": user_data.get("id"),
                            # Added fields
                            "verified": user_data.get("verified"),
                            "verified_type": user_data.get("verified_type"),
                            "location": user_data.get("location"),
                            "created_at": user_data.get("created_at"),
                            "protected": user_data.get("protected"),
                            "metrics": {
                                "followers_count": public_metrics.get("followers_count"),
                                "following_count": public_metrics.get("following_count"),
                                "tweet_count": public_metrics.get("tweet_count"),
                                "listed_count": public_metrics.get("listed_count"),
                                "like_count": public_metrics.get("like_count"),
                                "media_count": public_metrics.get("media_count")
                            }
                        }
                        return account_data
                    else:
                        logger.error(f"Error in Twitter API response: {data}")
                        return {"status": "error", "message": str(data)} """
        except Exception as e:
            error_response = handle_twitter_error(e)
            logger.error(f"Twitter API Error: {error_response}")
            return error_response
        
    async def post(self, request: Request):
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            message = params.get('message')
            image_url = params.get('image_url')
            
            credentials = await self.get_user_credentials(user_id)
            if not credentials:
                return {"status": "missing", "message": "❌ User not connected to Twitter"}
            
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
            return {"status": "success", "message": "Tweet posted successfully", "tweet": response_data}
            
        except Exception as e:
            error_response = handle_twitter_error(e)
            logger.error(f"Twitter API Error: {error_response}")
            return error_response
    
    async def disconnect(self, user_id: int) -> bool:
        return await self.db.delete_user_twitter_credentials(user_id)

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