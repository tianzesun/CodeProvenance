"""Legacy bootstrap package kept only for backward reference.

This directory is quarantined and must not be used by active production code.
Its contents remain in the repository temporarily so cleanup can proceed
without breaking history-driven or exploratory work.

Allowed use:
- reference during migration
- historical comparison

Blocked use:
- new production imports
- new feature work
- new runtime dependencies
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


class DependencyContainer:
    """Simple dependency injection container."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._initialized = False

    def register(self, name: str, service: Any) -> None:
        """Register a service."""
        self._services[name] = service

    def get(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        """Check if service is registered."""
        return name in self._services

    def initialize(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return

        # Initialize services in dependency order
        self._init_config()
        self._init_database()
        self._init_repositories()
        self._init_services()
        self._init_engines()
        self._init_pipeline()

        self._initialized = True

    def _init_config(self) -> None:
        """Initialize configuration."""
        from src.backend.config.database import DatabaseConfig

        self.register("db_config", DatabaseConfig())

    def _init_database(self) -> None:
        """Initialize database."""
        db_config = self.get("db_config")
        db_manager = DatabaseManager(db_config)
        db_manager.initialize()
        self.register("db_manager", db_manager)

    def _init_repositories(self) -> None:
        """Initialize repositories."""
        # Register repository implementations
        pass

    def _init_services(self) -> None:
        """Initialize application services."""
        # Register service implementations
        pass

    def _init_engines(self) -> None:
        """Initialize detection engines."""
        # Engines are auto-registered via decorators
        pass

    def _init_pipeline(self) -> None:
        """Initialize processing pipeline."""
        # Register pipeline components
        pass

    def shutdown(self) -> None:
        """Shutdown all services."""
        db_manager = self.get("db_manager")
        if db_manager:
            db_manager.close()

        self._initialized = False


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Get the global dependency container (singleton)."""
    global _container

    if _container is None:
        _container = DependencyContainer()
        _container.initialize()

    return _container


def get_service(name: str) -> Optional[Any]:
    """Get a service from the container."""
    container = get_container()
    return container.get(name)


def main():
    """Main entry point for dependency wiring."""
    container = get_container()

    try:
        # System is now initialized and ready
        print("System initialized successfully")

        # Example: Get a service
        # service = get_service('some_service')
        # if service:
        #     service.do_something()

    finally:
        container.shutdown()


if __name__ == "__main__":
    main()
