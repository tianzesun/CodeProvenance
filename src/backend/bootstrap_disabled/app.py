"""
Single Execution Lifecycle - Bootstrap Entry Point

This module provides the canonical entry point for the entire system.
All initialization flows through here to ensure consistency.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backend.config.database import DatabaseConfig
from src.backend.infrastructure.db import DatabaseManager
from src.backend.domain.models import Base
from src.backend.application.pipeline.detection_pipeline import DetectionPipeline
from src.backend.engines.engine_registry import registry


class Application:
    """Single execution lifecycle manager."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.db_manager: Optional[DatabaseManager] = None
        self.pipeline: Optional[DetectionPipeline] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all components in correct order."""
        if self._initialized:
            return

        # 1. Configuration
        self._init_config()

        # 2. Database
        self._init_database()

        # 3. Domain models
        self._init_domain()

        # 4. Engines
        self._init_engines()

        # 5. Pipeline
        self._init_pipeline()

        self._initialized = True

    def _init_config(self) -> None:
        """Initialize configuration."""
        from src.backend.config.database import DatabaseConfig

        self.db_config = DatabaseConfig()

    def _init_database(self) -> None:
        """Initialize database connection."""
        self.db_manager = DatabaseManager(self.db_config)
        self.db_manager.initialize()

    def _init_domain(self) -> None:
        """Initialize domain models."""
        # Create tables if needed
        Base.metadata.create_all(self.db_manager.engine)

    def _init_engines(self) -> None:
        """Initialize detection engines."""
        # Engines are auto-registered via decorators
        pass

    def _init_pipeline(self) -> None:
        """Initialize detection pipeline."""
        self.pipeline = DetectionPipeline(
            db_manager=self.db_manager, config=self.config
        )

    def run(self, input_data: Any) -> Any:
        """Run the main application logic."""
        if not self._initialized:
            self.initialize()

        return self.pipeline.execute(input_data)

    def shutdown(self) -> None:
        """Clean shutdown of all components."""
        if self.db_manager:
            self.db_manager.close()

        self._initialized = False


# Global application instance
_app_instance: Optional[Application] = None


def get_application(config: Optional[Dict[str, Any]] = None) -> Application:
    """Get the global application instance (singleton)."""
    global _app_instance

    if _app_instance is None:
        _app_instance = Application(config)
        _app_instance.initialize()

    return _app_instance


def main():
    """Main entry point for the application."""
    app = get_application()

    try:
        # Example usage
        result = app.run({"test": "data"})
        print(f"Result: {result}")
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
