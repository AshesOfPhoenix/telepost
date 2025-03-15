from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import traceback

from fastapi import HTTPException, Request, Response
from api.db.database import db
from api.utils.logger import logger

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
            provider_id: Optional provider ID override
            
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
            logger.error(f"Error retrieving credentials: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail={
                    "status": "error", 
                    "code": 500, 
                    "message": f"Error retrieving credentials: {str(e)}",
                    "platform": self.provider_id
                }
            )
        
    async def delete_user_credentials(self, user_id: int, provider_id: str | None = None):
        """
        Delete user credentials for the social media platform.
        
        Args:
            user_id: The ID of the user
            provider_id: Optional provider ID override
        """
        try:
            await self.db.delete_user_credentials(
                user_id, 
                provider_id if provider_id is not None else self.provider_id
            )
        except Exception as e:
            logger.error(f"Error deleting credentials: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail={
                    "status": "error", 
                    "code": 500, 
                    "message": f"Error deleting credentials: {str(e)}",
                    "platform": self.provider_id
                }
            )
    
    def create_success_response(self, data: Dict[str, Any], message: str = "Success") -> Response:
        """
        Create a standardized success response
        
        Args:
            data: Response data
            message: Success message
            
        Returns:
            Standardized Response object
        """
        return Response(
            content=json.dumps({
                "status": "success",
                "code": 200,
                "message": message,
                "data": data,
                "platform": self.provider_id
            }),
            media_type="application/json",
            status_code=200
        )
    
    def create_error_response(self, status_code: int, message: str, details: Dict[str, Any] = None) -> Response:
        """
        Create a standardized error response
        
        Args:
            status_code: HTTP status code
            message: Error message
            details: Optional error details
            
        Returns:
            Standardized Response object
        """
        response_data = {
            "status": "error",
            "code": status_code,
            "message": message,
            "platform": self.provider_id
        }
        
        if details:
            response_data["details"] = details
            
        return Response(
            content=json.dumps(response_data),
            media_type="application/json",
            status_code=status_code
        )
    
    def handle_exception(self, e: Exception, operation: str) -> Response:
        """
        Handle exceptions in a standardized way
        
        Args:
            e: Exception object
            operation: Operation being performed when exception occurred
            
        Returns:
            Standardized error Response
        """
        logger.error(f"Error during {operation} for {self.provider_id}: {str(e)}")
        logger.debug(traceback.format_exc())
        
        if isinstance(e, HTTPException):
            # Pass through HTTPExceptions with their status code
            detail = e.detail
            status_code = e.status_code
            
            # Ensure detail is properly formatted
            if isinstance(detail, str):
                detail = {
                    "message": detail,
                    "platform": self.provider_id
                }
                
            return self.create_error_response(
                status_code=status_code,
                message=detail.get("message", f"Error during {operation}"),
                details=detail
            )
        else:
            # For other exceptions, return a 500 error
            return self.create_error_response(
                status_code=500,
                message=f"Error during {operation}: {str(e)}",
                details={"exception_type": type(e).__name__}
            )
    
    @abstractmethod
    async def get_user_account(self, user_id: int) -> Response:
        """
        Retrieve user account information from the social platform.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Response containing user account details
        """
        pass
    
    @abstractmethod
    async def post(self, request: Request) -> Response:
        """
        Post content to the social media platform.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Response containing the post details
        """
        pass
    
    async def check_token_validity(self, user_id: int) -> Dict[str, Any]:
        """
        Check if user's token is valid and not expired.
        Should be implemented by provider-specific controllers.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            Dict with token validity information
        """
        raise NotImplementedError("Token validity check not implemented for this provider")