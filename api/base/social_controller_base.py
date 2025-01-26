from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from fastapi import Request
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
        credentials = await self.db.get_user_credentials(
            user_id, 
            provider_id if provider_id is not None else self.provider_id
        )
        return credentials
    
    @abstractmethod
    async def get_user_account(self, user_id: int) -> Dict[str, Any]:
        """
        Retrieve user account information from the social platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict containing user account details
        """
        pass
    
    @abstractmethod
    async def post(self, request: Request) -> Dict[str, Any]:
        """
        Post a thread to the social media platform.
        
        Args:
            user_id: The ID of the user
            thread: The content to be posted
            
        Returns:
            Dict containing the post details
        """
        pass