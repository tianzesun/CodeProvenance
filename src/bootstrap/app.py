"""Application Factory - ONLY place where everything is wired."""
from typing import Dict, Optional
from fastapi import FastAPI

def create_app(weights: Optional[Dict] = None, threshold: float = 0.5) -> FastAPI:
    """Create and wire the entire application.
    
    This is the SINGLE composition root for the system.
    """
    # Initialize architecture guard (import enforcement)
    from src.bootstrap.architecture_guard import ArchitectureGuard
    ArchitectureGuard.install_guard()
    
    # Initialize dependency container
    from src.bootstrap.container import Container
    Container.init(weights, threshold)
    
    # Create FastAPI app (API is transport ONLY)
    app = FastAPI(title="CodeProvenance", version="1.0")
    
    # Register routes (API delegates to application use cases)
    from src.api.routes import health
    app.include_router(health.router)
    
    return app
