# Threads Controller

import httpx
from api.config import get_settings
from fastapi import APIRouter, Depends
from pydantic import BaseModel

settings = get_settings()


router = APIRouter()

class ThreadPost(BaseModel):
    content: str
    schedule_time: str | None = None

@router.post("/create")
async def create_thread(post: ThreadPost):
    # Thread creation logic
    return {"thread_id": "123"}