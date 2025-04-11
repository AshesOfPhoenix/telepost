import os
from pydantic import BaseModel, field_validator, Field
from pydantic_settings import BaseSettings
from dataclasses import dataclass
from typing import List, Optional, Dict, Union
from datetime import datetime
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
    
    # CORS
    CORS_ALLOWED_ORIGINS: str = ""
    
    @field_validator("CORS_ALLOWED_ORIGINS", mode="after")
    @classmethod
    def validate_cors_allowed_origins(cls, value) -> List[str]:
        if isinstance(value, str):
            return [x.strip() for x in value.split(",")]
        elif isinstance(value, list):
            return value
        return []
    
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
    THREADS_REDIRECT_URI: str = "/auth/threads/callback"
    
    # Twitter API
    TWITTER_CLIENT_ID: str
    TWITTER_CLIENT_SECRET: str
    TWITTER_API_URL: str = "https://api.x.com"
    TWITTER_REDIRECT_URI: str = "/auth/twitter/callback"
    
    # Telegram
    TELEGRAM_BOTNAME: str
    
    # OpenAI (Original - Keeping for potential other uses)
    OPENAI_API_KEY: str | None = None

    # OpenRouter AI
    OPENROUTER_API_KEY: str
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"
    AI_MODEL_NAME: str # e.g., "openai/gpt-3.5-turbo"
    
    # Redis (for chat history, rate limiting, caching)
    REDIS_URL: str
    UPSTASH_REDIS_REST_TOKEN: str
    UPSTASH_REDIS_REST_URL: str
    CHAT_HISTORY_TTL_SECONDS: int = 3600 * 24 * 7 # Optional: TTL for chat history (default 1 week)
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Thread Account Response Interface
class ThreadsAccountResponse(BaseModel):
    id: str
    username: str
    threads_biography: str = Field(alias="biography")
    threads_profile_picture_url: str = Field(alias="profile_picture_url")
    name: Optional[str] = None  # Make name optional since it might not always be present

    class Config:
        populate_by_name = True
        extra = "allow"
        
    @property
    def biography(self) -> str:
        return self.threads_biography

    @property
    def profile_picture_url(self) -> str:
        return self.threads_profile_picture_url
    
    

# Threads Insights Response Interface
class MetricValue(BaseModel):
    value: int
    end_time: Optional[str] = None

class InsightMetric(BaseModel):
    name: str
    period: str
    title: str
    description: str
    id: str
    values: Optional[List[MetricValue]] = None
    total_value: Optional[dict] = None

class Paging(BaseModel):
    previous: str
    next: str

class ThreadsInsightsResponse(BaseModel):
    data: List[InsightMetric]
    paging: Paging
    
    class Config:
        populate_by_name = True
        extra = "allow"

    def get_metric_by_name(self, name: str) -> Optional[InsightMetric]:
        return next((metric for metric in self.data if metric.name == name), None)

    def get_total_followers(self) -> int:
        followers_metric = self.get_metric_by_name('followers_count')
        return followers_metric.total_value.get('value', 0) if followers_metric else 0
    
    def get_total_likes(self) -> int:
        likes_metric = self.get_metric_by_name('likes')
        return likes_metric.total_value.get('value', 0) if likes_metric else 0
    
    def get_total_replies(self) -> int:
        replies_metric = self.get_metric_by_name('replies')
        return replies_metric.total_value.get('value', 0) if replies_metric else 0
    
    def get_total_reposts(self) -> int:
        reposts_metric = self.get_metric_by_name('reposts')
        return reposts_metric.total_value.get('value', 0) if reposts_metric else 0
    
    def get_total_quotes(self) -> int:
        quotes_metric = self.get_metric_by_name('quotes')
        return quotes_metric.total_value.get('value', 0) if quotes_metric else 0

    def get_total_views(self) -> List[MetricValue]:
        views_metric = self.get_metric_by_name('views')
        return views_metric.values if views_metric else []
    
    
    
# Twitter Account Response Interface
class PublicMetrics(BaseModel):
    followers_count: int
    following_count: int
    tweet_count: int
    listed_count: int
    like_count: int
    media_count: int

class UrlEntity(BaseModel):
    start: int
    end: int
    url: str
    expanded_url: str
    display_url: str

class DescriptionEntities(BaseModel):
    urls: list[UrlEntity]

class Entities(BaseModel):
    description: DescriptionEntities

class TwitterAccountData(BaseModel):
    id: str
    username: str
    name: str
    description: str
    profile_image_url: str
    verified: bool
    verified_type: str
    location: str
    created_at: str
    protected: bool
    public_metrics: PublicMetrics
    most_recent_tweet_id: Optional[str] = None
    entities: Entities
    
    class Config:
        populate_by_name = True
        extra = "allow"

class TwitterAccountResponse(BaseModel):
    data: TwitterAccountData

    # Helper methods to easily access nested data
    @property
    def followers_count(self) -> int:
        return self.data.public_metrics.followers_count

    @property
    def following_count(self) -> int:
        return self.data.public_metrics.following_count

    @property
    def tweet_count(self) -> int:
        return self.data.public_metrics.tweet_count

    @property
    def profile_picture_url(self) -> str:
        return self.data.profile_image_url

    @property
    def biography(self) -> str:
        return self.data.description