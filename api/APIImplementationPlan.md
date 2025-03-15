# TelePost API Implementation Plan

## Overview

This document outlines the implementation plan for the TelePost API, which serves as the backend for the TelePost Telegram bot. The API provides endpoints for authentication, posting, and account management for various social media platforms.

## Architecture

The TelePost API is built on a modular architecture with clear separation of concerns:

1. **Base Classes**
   - `AuthHandlerBase`: Abstract base class for authentication handlers
   - `SocialController`: Abstract base class for social media controllers

2. **Platform-Specific Implementations**
   - Authentication handlers for each platform
   - Social controllers for each platform
   
3. **Routing Layer**
   - REST API endpoints for each platform

## Authentication Flow

### OAuth Flow (Common to all platforms)

1. **Authorization Request**
   - Client requests authorization URL from API
   - API generates a state parameter and stores it with the user ID
   - API returns authorization URL to client

2. **Authorization Callback**
   - User completes authorization on platform
   - Platform redirects to callback URL with auth code and state parameter
   - API verifies state parameter, exchanges code for token
   - API stores credentials in database
   - API redirects user back to the Telegram bot with success/error status

3. **Token Management**
   - API provides endpoints to check token validity
   - API provides endpoints to refresh tokens when possible

## API Endpoints

### Authentication Endpoints

#### Threads Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/threads/connect` | GET | Get Threads authorization URL |
| `/auth/threads/callback` | GET | Handle Threads OAuth callback |
| `/auth/threads/disconnect` | POST | Disconnect user from Threads |
| `/auth/threads/is_connected` | GET | Check if user is connected to Threads |
| `/auth/threads/token_validity` | GET | Check Threads token validity |

#### Twitter Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/twitter/connect` | GET | Get Twitter authorization URL |
| `/auth/twitter/callback` | GET | Handle Twitter OAuth callback |
| `/auth/twitter/disconnect` | POST | Disconnect user from Twitter |
| `/auth/twitter/is_connected` | GET | Check if user is connected to Twitter |
| `/auth/twitter/token_validity` | GET | Check Twitter token validity |
| `/auth/twitter/refresh_token` | POST | Refresh Twitter token if possible |

### Social Media Operations

#### Threads Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/threads/user_account` | GET | Get user account information |
| `/threads/post` | POST | Post a message to Threads |
| `/threads/token_validity` | GET | Check token validity |

#### Twitter Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/twitter/user_account` | GET | Get user account information |
| `/twitter/post` | POST | Post a message to Twitter |
| `/twitter/token_validity` | GET | Check token validity |

## Enhancements and New Features

### 1. Token Management

- **Token Validation**: Added new endpoints to check token validity with detailed information
- **Token Refreshing**: Added capability to refresh Twitter tokens
- **Expiration Handling**: Improved handling of expired tokens with graceful error messages

### 2. Standardized Response Format

All API responses now follow a consistent format:

```json
{
  "status": "success" | "error",
  "code": 200 | 400 | 401 | 404 | 500,
  "message": "Human-readable message",
  "data": {}, // Response data (for success)
  "platform": "threads" | "twitter",
  "details": {} // Additional details (for errors)
}
```

### 3. Error Handling

Improved error handling throughout the API:

- **Exception Handling**: Centralized exception handling in the base classes
- **Graceful Degradation**: Better handling of API errors and expired tokens
- **Detailed Error Messages**: More informative error messages to help debugging

### 4. Media Handling

Enhanced media handling capabilities:

- **Threads Media**: Proper handling of media attachments for Threads posts
- **Twitter Media**: Framework for media handling (currently limited to text-only posts)

## Implementation Specifics

### AuthHandlerBase Enhancements

Added new abstract methods:
- `calculate_expiration_time(credentials)`: Calculate time until expiration in seconds
- `can_refresh_token(credentials)`: Check if token can be refreshed

Added new concrete method:
- `get_token_validity(user_id)`: Get detailed token validity information

### SocialController Enhancements

Added new methods:
- `create_success_response(data, message)`: Create standardized success response
- `create_error_response(status_code, message, details)`: Create standardized error response
- `handle_exception(e, operation)`: Handle exceptions in a standardized way

### Platform-Specific Implementations

#### Threads

- Added token validity checking
- Improved media handling
- Enhanced error handling

#### Twitter

- Added token refreshing capability
- Added token validity checking
- Improved post error handling

## Future Enhancements

1. **Media Upload for Twitter**:
   - Implement proper media upload for Twitter

2. **Carousel Posts for Threads**:
   - Support for multi-image carousel posts on Threads

3. **Scheduled Posts**:
   - Allow scheduling posts for future publishing

4. **Analytics**:
   - Add endpoints for retrieving post performance analytics

5. **Batch Operations**:
   - Support for posting to multiple platforms in a single request

## Conclusion

This implementation plan provides a comprehensive roadmap for enhancing the TelePost API to better support the recently improved Telegram bot functionality. The changes focus on improving reliability, standardizing response formats, and enhancing token management to ensure a seamless user experience. 