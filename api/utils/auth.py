from asyncio.log import logger
from fastapi import HTTPException, Request
from fastapi.security.api_key import APIKeyHeader
from api.utils.config import get_settings

settings = get_settings()

api_key_header_name = APIKeyHeader(name=settings.API_KEY_HEADER_NAME)

def verify_api_key(request: Request):
    logger.info(f"Verifying API key for request: {request}")
    api_key = request.headers.get(settings.API_KEY_HEADER_NAME)
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")