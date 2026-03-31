"""Parser for MOSS output."""
from typing import Dict, Any
from pathlib import Path
from benchmark.parsers.base_parser import BaseToolParser, ToolResult


class MossParser(BaseToolParser):
    @property
    def tool_name(self) -> str:
        return "moss"

    def parse(self, output_path: Path) -> ToolResult:
        with open(output_path) as f:
            lines = f.readlines()
        pairs = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                f1, f2 = parts[0], parts[1]
                sim = float(parts[2]) / 100.0 if parts[2].isdigit() else 0
                pair = ToolResult.make_pair(f1, f2, sim)
                pairs.append(pair)
        return ToolResult(pairs=pairs)
