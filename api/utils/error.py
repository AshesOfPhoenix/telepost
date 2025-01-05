from typing import TypedDict, Optional
from fastapi import HTTPException, status
from api.utils.logger import logger
from pytwitter import PyTwitterError

class TwitterErrorResponse(TypedDict):
    status: str
    message: str
    code: Optional[int]
    details: Optional[str]

def handle_twitter_error(e: Exception) -> TwitterErrorResponse:
    """Handle Twitter API errors and return appropriate response messages"""
    error_message = str(e)
    error_code = None
    
    logger.info(f"Error message: {error_message}")
    
    # Extract error code if present in the error message
    try:
        if isinstance(e, PyTwitterError):
            # PyTwitterError contains the error response as a dict in its args
            error_data = e.args[0] if e.args else {}
            if isinstance(error_data, dict):
                if 'status' in error_data:
                    error_code = int(error_data['status'])
                error_message = error_data.get('detail', str(e))
        elif hasattr(e, 'code'):
            error_code = int(e.code)
        elif hasattr(e, 'status'):
            error_code = int(e.status)
        elif isinstance(e, dict):
            if 'status' in e:
                error_code = int(e['status'])
        elif '[' in error_message and ']' in error_message:
            error_code = int(error_message.split('[')[1].split(']')[0])
    except (ValueError, IndexError):
        pass
    
    # Map common Twitter error codes to meaningful responses
    error_responses = {
        32: {
            "status": "unauthorized",
            "message": "Authentication failed. Please check your credentials.",
            "code": 32,
            "details": "Could not authenticate you"
        },
        34: {
            "status": "not_found",
            "message": "The requested resource was not found on Twitter.",
            "code": 34,
            "details": "Resource not found"
        },
        63: {
            "status": "suspended",
            "message": "This Twitter account has been suspended.",
            "code": 63,
            "details": "User has been suspended"
        },
        64: {
            "status": "account_suspended",
            "message": "Your Twitter account is suspended and cannot access this feature.",
            "code": 64,
            "details": "Account suspended"
        },
        88: {
            "status": "rate_limit",
            "message": "Rate limit exceeded. Please try again later.",
            "code": 88,
            "details": "Too many requests"
        },
        89: {
            "status": "invalid_token",
            "message": "Invalid or expired Twitter access token.",
            "code": 89,
            "details": "Token validation failed"
        },
        130: {
            "status": "over_capacity",
            "message": "Twitter is temporarily over capacity. Please try again later.",
            "code": 130,
            "details": "Service overloaded"
        },
        131: {
            "status": "internal_error",
            "message": "An internal error occurred on Twitter's end.",
            "code": 131,
            "details": "Twitter internal error"
        },
        215: {
            "status": "bad_authentication",
            "message": "Bad authentication data provided.",
            "code": 215,
            "details": "Authentication data invalid"
        },
        326: {
            "status": "account_locked",
            "message": "This account is temporarily locked. Please log in to Twitter to unlock.",
            "code": 326,
            "details": "Account locked"
        }
    }

    # Return mapped error response if code exists, otherwise return generic error
    if error_code in error_responses:
        return error_responses[error_code]
    
    # Handle rate limiting HTTP status
    if isinstance(e, HTTPException) and e.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return error_responses[88]

    # Generic error response
    return {
        "status": "error",
        "message": "An error occurred while processing your request.",
        "code": error_code,
        "details": error_message
    }