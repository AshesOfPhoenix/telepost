# API Main
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from api.utils.config import get_settings
from api.routers.threads import router as threads_router
from api.routers.auth.threads.auth import router as threads_auth_router
from api.routers.twitter import router as twitter_router
from api.routers.auth.twitter.auth import router as twitter_auth_router
from api.utils.logger import logger
from api.utils.auth import verify_api_key
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from api.utils.docs import custom_openapi

settings = get_settings()

logger.info("Initializing API...")

app = FastAPI(
    title="Telepost API",
    description="API for managing social media posts across platforms",
    version="1.0.0",
    dependencies=[Depends(verify_api_key)]
)

# Custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)

# Mount static files for docs
app.mount("/static", StaticFiles(directory="api/static"), name="static")

# Custom documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Telepost API Documentation",
        oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Telepost API Documentation",
        redoc_js_url="/static/redoc.standalone.js",
    )

logger.info("✓ API created")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

logger.info("✓ Trusted host middleware added")

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(threads_router, prefix="/threads")
app.include_router(threads_auth_router, prefix="/auth/threads")
app.include_router(twitter_router, prefix="/twitter")
app.include_router(twitter_auth_router, prefix="/auth/twitter")

logger.info("✓ API routes added")

logger.info("✅ API initialized")
