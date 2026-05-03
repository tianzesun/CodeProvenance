import json
import gzip
from typing import List, Dict, Any, Optional
from pathlib import Path
from benchmark.harness import Loader


class CodeSearchNetLoader(Loader):
    """Loader for CodeSearchNet gzipped JSONL dataset format."""

    def load(self, path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        file_path = Path(path)

        open_func = gzip.open if file_path.suffix == ".gz" else open

        with open_func(path, 'rt', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))

        return rows
