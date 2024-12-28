import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    # API Settings
    API_BASE_URL: str
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"
    DEBUG: bool = False
    
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Encryption
    ENCRYPTION_KEY: str
    
    # Telegram
    TELEGRAM_TOKEN: str
    TELEGRAM_BOTNAME: str
    ALLOWED_USERS: str = ""
    
    @field_validator("ALLOWED_USERS", mode="after")
    @classmethod
    def parse_allowed_users(cls, v: str) -> List[str]:
        if not v:
            return []
        return [x.strip() for x in v.split(",")]
    
    # Redis (for rate limiting/caching)
    REDIS_URL: str | None = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()