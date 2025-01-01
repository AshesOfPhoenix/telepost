# API Main
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from api.utils.config import get_settings
from api.routers.threads import router as threads_router
from api.routers.auth.threads.auth import router as threads_auth_router
from api.routers.twitter import router as twitter_router
from api.utils.logger import logger
from api.utils.auth import verify_api_key

settings = get_settings()

app = FastAPI(dependencies=[Depends(verify_api_key)])

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api", "localhost", "127.0.0.1"],
)

logger.info("API initialized")

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(threads_router, prefix="/threads")
app.include_router(threads_auth_router, prefix="/auth/threads")
app.include_router(twitter_router, prefix="/twitter")

logger.info("API routes added")