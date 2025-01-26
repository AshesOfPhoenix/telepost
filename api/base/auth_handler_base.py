from abc import ABC, abstractmethod
from asyncio.log import logger
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
    
    async def store_user_credentials(self, user_id: int, credentials: Credentials | dict) -> bool:
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
        try:
            credentials = await self.get_user_credentials(user_id)
            return credentials is not None
        except Exception as e:
            logger.error(f"Error getting user credentials: {e}")
            return False
    
    def get_state_from_user_id(self, user_id: int) -> Dict[str, Any]:
        """
        Get state from user_id
        """
        try:
            return self.states.get(user_id, {})
        except Exception as e:
            logger.error(f"Error getting state from user_id: {e}")
            return {}
    
    def get_user_id_from_state(self, state: str) -> Optional[str]:
        """
        Helper method to retrieve user_id from stored state
        
        Args:
            state: OAuth state parameter
            
        Returns:
            user_id if found, None otherwise
        """
        try:
            logger.info(f"Getting user_id from state: {state}")
            for uid, stored_state in self.states.items():
                if stored_state.get("state") == state:
                    logger.info(f"Found user_id {uid} for state {state}")
                    return uid
            return None
        except Exception as e:
            logger.error(f"Error getting user_id from state: {e}")
            return None
    
    def get_code_verifier_from_state(self, state: str) -> Optional[str]:
        """
        Helper method to retrieve code_verifier from stored state
        
        Args:
            state: OAuth state parameter
            
        Returns:
            code_verifier if found, None otherwise
        """
        try:
            logger.info(f"Getting code_verifier from state: {state}")
            for uid, stored_state in self.states.items():
                if stored_state.get("state") == state:
                    logger.info(f"Found user_id {uid} for state {state}")
                    return stored_state.get("code_verifier")
            return None
        except Exception as e:
            logger.error(f"Error getting code_verifier from state: {e}")
            return None
    
    def store_state(self, user_id: str, state: str, code_verifier: str | None = None) -> None:
        """
        Store OAuth state for a user
        
        Args:
            user_id: User identifier
            state: OAuth state parameter
            code_verifier: OAuth code verifier parameter
        """
        try:
            logger.info(f"Storing state for user {user_id}: {state}")
            self.states[user_id] = {
                "state": state,
                "code_verifier": code_verifier
            }
        except Exception as e:
            logger.error(f"Error storing state: {e}")

    def get_all_states(self) -> Dict[str, Dict[str, str]]:
        """
        Get all stored states
        """
        try:
            return self.states
        except Exception as e:
            logger.error(f"Error getting all states: {e}")
            return {}

    def clear_state(self, user_id: str) -> None:
        """
        Clear stored state for a user
        
        Args:
            user_id: User identifier
        """
        if user_id in self.states:
            del self.states[user_id]
            logger.info(f"Cleared state for user {user_id}")
        else:
            logger.warning(f"State not found for user {user_id}")

    @abstractmethod
    async def disconnect(self, request: Request) -> Dict[str, Any]:
        """
        Disconnect user's account from the social media platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict[str, Any]: Response containing status of the operation
        """
        try:
            params = dict(request.query_params)
            user_id = params.get('user_id')
            
            self.clear_state(user_id)
            
            await self.db.delete_user_credentials(user_id, self.provider_id)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error disconnecting user: {e}")
            return {"status": "error", "message": str(e)}