"""Application factory - ONLY bootstrap, no logic."""
from typing import Dict, Optional
from fastapi import FastAPI

def create_app(weights: Optional[Dict] = None, threshold: float = 0.5) -> FastAPI:
    from src.bootstrap.container import Container
    Container.init(weights, threshold)
    app = FastAPI(title="CodeProvenance", version="1.0")
    # Routes go here - API is transport only
    from src.api.routes import health
    app.include_router(health.router)
    return app
