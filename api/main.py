# API Main
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from api.config import get_settings
from api.routers.threads import router as threads_router
from api.routers.auth.threads.auth import router as threads_auth_router
from api.utils.logger import logger

settings = get_settings()

app = FastAPI()

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

logger.info("API routes added")