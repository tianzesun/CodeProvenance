"""
Experiment Definition - Core object for benchmark orchestration.

Defines the complete experimental setup that generates the full job matrix
for distributed execution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime


@dataclass
class Experiment:
    """
    Complete experimental definition.
    
    Experiment = Dataset × Transform × Tool × Task × Repetition
    
    This is the single source of truth for an entire benchmark run.
    """
    name: str
    dataset: str
    tools: List[str]
    transforms: List[str]
    tasks: List[str]
    n_runs: int = 30
    experiment_id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "dataset": self.dataset,
            "tools": self.tools,
            "transforms": self.transforms,
            "tasks": self.tasks,
            "n_runs": self.n_runs,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experiment':
        return cls(
            name=data["name"],
            dataset=data["dataset"],
            tools=data["tools"],
            transforms=data["transforms"],
            tasks=data["tasks"],
            n_runs=data.get("n_runs", 30),
            experiment_id=data.get("experiment_id", str(uuid4())[:8]),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {})
        )