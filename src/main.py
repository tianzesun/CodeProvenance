"""
Main application entry point for CodeProvenance.
"""

from fastapi import FastAPI
from src.api.routes.api import api_router
from src.config.database import db_config

# Create FastAPI app
app = FastAPI(
    title="CodeProvenance",
    description="Software Similarity Detection Service for EdTech Platforms",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint.
    """
    return {
        "message": "Welcome to CodeProvenance API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}

# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Application startup event.
    """
    # Test database connection
    try:
        engine = db_config.get_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event.
    """
    print("Shutting down CodeProvenance API")
