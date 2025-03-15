import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    # API Settings
    API_PUBLIC_URL: str
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"
    DEBUG: bool = False
    
    # Security
    API_KEY: str
    API_KEY_HEADER_NAME: str = "X-API-KEY"
    
    # Encryption
    ENCRYPTION_KEY: str | None = None
    
    # Telegram
    TELEGRAM_TOKEN: str
    TELEGRAM_BOTNAME: str
    ALLOWED_USERS: str = ""
    
    @field_validator("ALLOWED_USERS", mode="after")
    @classmethod
    def parse_allowed_users(cls, v: str) -> List[str]:
        # if v == "":
        return ["kikoems"]
        # if not v:
        #     return None
        # return [x.strip() for x in v.split(",")]
    
    # Redis (for rate limiting/caching)
    REDIS_URL: str | None = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()