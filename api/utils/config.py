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
    
    # Allowed hosts
    ALLOWED_HOSTS: str = ""
    
    @field_validator("ALLOWED_HOSTS", mode="after")
    @classmethod
    def validate_allowed_hosts(cls, value) -> List[str]:
        if isinstance(value, str):
            return [x.strip() for x in value.split(",")]
        elif isinstance(value, list):
            return value
        return ["localhost", "127.0.0.1"]
    
    # Encryption
    ENCRYPTION_KEY: str
    
    # Database
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_HOST: str
    DATABASE_PORT: str
    DATABASE_NAME: str
    
    # Threads API
    THREADS_APP_ID: str
    THREADS_APP_SECRET: str
    THREADS_API_URL: str = "https://api.threads.net"
    THREADS_REDIRECT_URI: str
    
    # Telegram
    TELEGRAM_BOTNAME: str
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Redis (for rate limiting/caching)
    REDIS_URL: str | None = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()