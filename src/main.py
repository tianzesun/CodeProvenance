"""Main entry point - ONLY bootstrap the application.

NO logic, NO engine imports, NO wiring.
"""
import uvicorn
from src.bootstrap.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
