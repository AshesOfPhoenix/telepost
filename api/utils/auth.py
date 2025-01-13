from asyncio.log import logger
from fastapi import HTTPException, Request
from fastapi.params import Security
from fastapi.security.api_key import APIKeyHeader
from api.utils.config import get_settings

settings = get_settings()

# API key header instance
# auto_error=False means that the API key is not required
# Returns the value of the API key if it is present, otherwise returns None
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)

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
):
    logger.info(f"Verifying API key for request: {request}")
    
    # If the request path is in the PUBLIC_PATHS set, return None
    if request.url.path in PUBLIC_PATHS:
        return None
    
    # If the API key is not present or does not match the settings API key, raise an HTTPException
    if not request.headers.get("host") or request.headers["host"] != settings.ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Invalid Host Header",
                "status": "unauthorized",
                "message": "The provided Host header is either missing or invalid. Please ensure you are accessing the API from an allowed host."
            }
        )