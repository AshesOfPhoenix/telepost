from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
from typing import Dict, Any
import json
import os
from api.utils.logger import logger
from api.utils.config import get_settings

settings = get_settings()

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Telepost API",
        version="1.0.0",
        description="""
        Telepost API provides integration with various social media platforms.
        
        Key Features:
        - Social Media Authentication (Threads, Twitter)
        - Post Management
        - Account Information
        """,
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": settings.API_KEY_HEADER_NAME
        }
    }

    # Add global security requirement
    openapi_schema["security"] = [{"ApiKeyHeader": []}]

    # Custom tags metadata
    openapi_schema["tags"] = [
        {
            "name": "threads",
            "description": "Operations with Threads social media platform"
        },
        {
            "name": "twitter",
            "description": "Operations with Twitter social media platform"
        },
        {
            "name": "auth",
            "description": "Authentication operations for social media platforms"
        }
    ]

    # Save schema to file
    save_openapi_schema(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema

def save_openapi_schema(schema: Dict[str, Any]) -> None:
    """Save OpenAPI schema to file"""
    docs_dir = "api/docs"
    os.makedirs(docs_dir, exist_ok=True)
    
    schema_path = f"{docs_dir}/openapi.json"
    try:
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=2)
        logger.info(f"✓ OpenAPI schema saved to {schema_path}")
    except Exception as e:
        logger.error(f"Failed to save OpenAPI schema: {str(e)}")