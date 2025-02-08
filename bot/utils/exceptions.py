class BotError(Exception):
    """Base exception for bot errors"""
    def __init__(self, message: str, platform: str = None, status_code: int = None, details: dict = None):
        self.message = message
        self.platform = platform
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

class APIError(BotError):
    """Raised when API request fails"""
    pass

class AuthenticationError(BotError):
    """Raised when authentication fails"""
    pass

class ConnectionError(BotError):
    """Raised when connection to service fails"""
    pass

class ExpiredCredentialsError(BotError):
    """Raised when credentials are expired"""
    pass 