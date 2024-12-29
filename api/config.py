import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    # API Settings
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"
    DEBUG: bool = False
    
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
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