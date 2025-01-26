# API Main
import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

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

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        logger.info("\n=== Incoming Request ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Path: {request.url.path}")
        logger.info(f"Client: {request.client}")
        
        # Allowed Hosts
        
        logger.info(f"Allowed Hosts: {settings.ALLOWED_HOSTS}")
        
        # Allowed CORS
        
        logger.info(f"Allowed CORS: {settings.CORS_ALLOWED_ORIGINS}")
        
        # Headers
        logger.info("\n=== Headers ===")
        for name, value in request.headers.items():
            logger.info(f"{name}: {value}")
            
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            logger.info("\n=== Response ===")
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Process Time: {process_time:.4f}s")
            
            return response
        except Exception as e:
            logger.error(f"\n=== Error Processing Request ===")
            logger.error(f"Error: {str(e)}")
            raise
        finally:
            logger.info("=== End Request ===\n")

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

app.add_middleware(RequestLoggingMiddleware)

logger.info(f"Setting up CORS middleware with allowed origins: {settings.CORS_ALLOWED_ORIGINS}")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger.info("✓ CORS middleware added")


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
