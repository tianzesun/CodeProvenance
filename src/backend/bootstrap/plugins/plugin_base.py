"""Plugin base contract for all execution modules."""
from abc import ABC, abstractmethod


class ExecutionPlugin(ABC):
    """Base contract for all execution modules."""

    name: str
    version: str = "1.0"

    @abstractmethod
    def run(self, **kwargs):
        """Execute the plugin with given parameters."""
        pass