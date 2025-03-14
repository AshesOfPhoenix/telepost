from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from fastapi import HTTPException, Request, Response
from api.db.database import db

class SocialController(ABC):
    """
    Abstract base class for social media provider implementations.
    Defines the contract that all social media providers must follow.
    """
    
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self.db = db
        
    async def get_user_credentials(self, user_id: int, provider_id: str | None = None) -> Dict[str, Any]:
        """
        Retrieve user credentials for the social media platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing user credentials
        """
        try:
            credentials = await self.db.get_user_credentials(
                user_id, 
                provider_id if provider_id is not None else self.provider_id
            )
            return credentials
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    async def delete_user_credentials(self, user_id: int, provider_id: str | None = None):
        """
        Delete user credentials for the social media platform.
        """
        try:
            await self.db.delete_user_credentials(user_id, provider_id if provider_id is not None else self.provider_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @abstractmethod
    async def get_user_account(self, user_id: int) -> Response:
        """
        Retrieve user account information from the social platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing user account details
        """
        pass
    
    @abstractmethod
    async def post(self, request: Request) -> Response:
        """
        Post a thread to the social media platform.
        
        Args:
            user_id: The ID of the user
            thread: The content to be posted
            
        Returns:
            Dict containing the post details
        """
        pass