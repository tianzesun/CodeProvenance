import json
from typing import List, Dict, Any
from benchmark.harness import Loader


class HumanEvalLoader(Loader):
    """Loader for HumanEval JSONL dataset format."""

    def load(self, path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
