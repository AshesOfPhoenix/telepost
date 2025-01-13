import asyncio
import dotenv
from fastapi.testclient import TestClient
from api.main import app
from api.utils.config import get_settings
import json
import os

dotenv.load_dotenv()

settings = get_settings()

async def update_api_docs():
    """Update API documentation"""
    client = TestClient(app)
    
    # Get OpenAPI schema
    response = client.get("/openapi.json")
    schema = response.json()
    
    # Save schema
    docs_dir = "api/docs"
    os.makedirs(docs_dir, exist_ok=True)
    
    with open(f"{docs_dir}/openapi.json", "w") as f:
        json.dump(schema, f, indent=2)
        
    print("✓ API documentation updated successfully")

if __name__ == "__main__":
    asyncio.run(update_api_docs())