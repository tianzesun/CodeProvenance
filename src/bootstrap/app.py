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
    app = FastAPI(title="IntegrityDesk", version="1.0.0")
    
    # Register main API router (includes jobs, submissions, results, webhooks, usage, health)
    # Note: These modules require database infrastructure; kept commented until DB is configured
    # from src.api.routes.api import api_router
    # app.include_router(api_router, prefix="/api/v1")
    
    # Register dashboard routes for teacher review UI (temporarily disabled - needs DashboardService)
    # from src.api.routes import dashboard
    # app.include_router(dashboard.router)
    
    # Register analysis routes (temporarily disabled - requires database setup)
    # from src.api.routes import analyze
    # app.include_router(analyze.router, prefix="/api")
    
    # Register health check route
    from src.api.routes import health
    app.include_router(health.router, prefix="/health")
    
    # Register root endpoint
    from src.api.routes.root import router as root_router
    app.include_router(root_router)
    
    return app
