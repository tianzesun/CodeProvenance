"""Parser for CodeProvenance/UniGuard output."""
from typing import List, Dict, Any
from pathlib import Path
import json
from benchmark.parsers.base_parser import BaseToolParser, ToolResult


class UniGuardParser(BaseToolParser):
    @property
    def tool_name(self) -> str:
        return "uniguard"

    def parse(self, output_path: Path) -> ToolResult:
        with open(output_path) as f:
            data = json.load(f)
        pairs = []
        for p in data.get("pairs", data.get("all_results", [])):
            pair = ToolResult.make_pair(
                p.get("file1", p.get("file_a", "")),
                p.get("file2", p.get("file_b", "")),
                p.get("similarity", p.get("score", 0)),
            )
            for m in p.get("matches", []):
                ToolResult.add_match(pair, m.get("start1",0), m.get("end1",0),
                                     m.get("start2",0), m.get("end2",0))
            pairs.append(pair)
        return ToolResult(pairs=pairs)
