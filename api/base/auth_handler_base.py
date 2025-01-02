from abc import ABC, abstractmethod
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional, Tuple
from api.db.database import db
from pythreads.credentials import Credentials

class AuthHandlerBase(ABC):
    """
    Abstract base class for social media authentication handlers.
    Provides a common interface for authentication flows across different platforms.
    """
    
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self.db = db
        self.states = {}  # For OAuth state management
    
    
    @abstractmethod
    async def authorize(self, request: Request) -> Dict[str, Any]:
        """
        Start the authorization flow
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dict containing authorization URL and any other necessary data
        """
        pass
    
    @abstractmethod
    async def complete_authorization(self, request: Request) -> Response:
        """
        Handle the OAuth callback and complete the authorization process
        
        Args:
            request: FastAPI request object
            
        Returns:
            Response object (HTML, Redirect, etc.)
        """
        pass
    
    # @abstractmethod
    # async def disconnect(self, request: Request) -> Dict[str, Any]:
    #     """
    #     Disconnect user from the service
    #     
    #     Args:
    #         request: FastAPI request object
    #         
    #     Returns:
    #         Dict containing status of the operation
    #     """
    #     pass

    async def get_user_credentials(self, user_id: int) -> Credentials | None:
        """
        Get user credentials
        """
        credentials = await self.db.get_user_credentials(user_id, self.provider_id)
        return credentials
    
    async def store_user_credentials(self, user_id: int, credentials: Credentials) -> bool:
        """
        Store user credentials
        """
        return await self.db.store_user_credentials(user_id, credentials, self.provider_id)
    
    @abstractmethod
    async def verify_credentials(self, user_id: int) -> bool:
        """
        Verify if stored credentials are valid
        
        Args:
            user_id: User identifier
            
        Returns:
            bool indicating if credentials are valid
        """
        pass
    
    async def is_connected(self, user_id: int) -> bool:
        """
        Check if user is connected to the service
        
        Args:
            user_id: User identifier
            
        Returns:
            bool indicating if user is connected
        """
        credentials = await self.get_user_credentials(user_id)
        return credentials is not None
    
    def get_user_id_from_state(self, state_key: str) -> Optional[str]:
        """
        Helper method to retrieve user_id from stored state
        
        Args:
            state_key: OAuth state parameter
            
        Returns:
            user_id if found, None otherwise
        """
        for uid, stored_state in self.states.items():
            if stored_state == state_key:
                return uid
        return None
    
    def store_state(self, user_id: str, state: str) -> None:
        """
        Store OAuth state for a user
        
        Args:
            user_id: User identifier
            state: OAuth state parameter
        """
        self.states[user_id] = state
    
    def clear_state(self, user_id: str) -> None:
        """
        Clear stored state for a user
        
        Args:
            user_id: User identifier
        """
        if user_id in self.states:
            del self.states[user_id]

    @abstractmethod
    async def disconnect(self, request: Request) -> Dict[str, Any]:
        """
        Disconnect user's account from the social media platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict[str, Any]: Response containing status of the operation
        """
        params = dict(request.query_params)
        user_id = params.get('user_id')
        
        self.clear_state(user_id)
        
        await self.db.delete_user_credentials(user_id, self.provider_id)
        return {"status": "ok"}
