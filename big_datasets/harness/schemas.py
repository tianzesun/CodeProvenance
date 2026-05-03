from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Literal
import json


TaskType = Literal[
    "retrieval",
    "binary_classification",
    "generation_exec",
    "similarity"
]

SplitType = Literal["train", "valid", "test", "prompt", "evaluation"]


@dataclass
class Sample:
    """
    Unified benchmark sample schema. All datasets are normalized into this common format
    to ensure consistent evaluation across retrieval, classification, and code generation tasks.
    """
    id: str
    dataset: str
    task: TaskType
    split: SplitType
    language: str
    prompt: Optional[str] = None
    code: Optional[str] = None
    code_b: Optional[str] = None
    label: Optional[int] = None
    tests: List[str] = field(default_factory=list)
    entry_point: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> Sample:
        return cls(**json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def write_jsonl(path: str, rows: List[Sample]) -> None:
    """Write list of Sample objects to JSONL file."""
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row.to_dict(), ensure_ascii=False) + '\n')
