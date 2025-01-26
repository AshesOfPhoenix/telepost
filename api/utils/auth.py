from asyncio.log import logger
from fastapi import HTTPException, Request, status
from fastapi.params import Security
from fastapi.security.api_key import APIKeyHeader
from api.utils.config import get_settings
import logging

logger = logging.getLogger("api")

settings = get_settings()

# API key header instance
# auto_error=False means that the API key is not required
# Returns the value of the API key if it is present, otherwise returns None
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME.strip('"'), auto_error=False)

PUBLIC_PATHS = {
    "/auth/threads/callback",
    "/auth/twitter/callback",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json"
}

# API key verification function
# This function is used to verify the API key for all requests except for the public paths
# Security is used to automatically extract the API key from the request headers
def verify_api_key(
    request: Request, 
    api_key: str = Security(api_key_header)
) -> None:
    """
    Verify API key for protected endpoints.
    Skips verification for public paths.
    Raises HTTPException if API key is invalid.
    """
    # Log request details for debugging
    logger.debug(f"Verifying request to: {request.url.path}")
    
    # Skip API key verification for public paths
    if request.url.path in PUBLIC_PATHS:
        return None
        
    # Validate API key presence
    if not api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Missing API Key",
                "status": "unauthorized",
                "message": f"Please provide an API key using the {settings.API_KEY_HEADER_NAME} header"
            }
        )
    
    # Validate API key value
    if api_key != settings.API_KEY:
        logger.warning("Invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Invalid API Key",
                "status": "forbidden",
                "message": "The provided API key is invalid"
            }
        )
    
    logger.debug("API key verification successful")
    return None