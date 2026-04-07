"""Parser utilities - unified tool output interface."""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from src.benchmark.parsers.base_parser import BaseToolParser, StandardOutput, ParserError


def parse_tool_output(tool_name: str, input_path: Path, dataset: str = "",
                      threshold: float = 0.0, **kwargs) -> StandardOutput:
    """
    Unified entry point for parsing any tool's output.
    
    Args:
        tool_name: 'jplag', 'moss', 'nicad', etc.
        input_path: Path to tool output
        dataset: Dataset name
        threshold: Min similarity filter
        
    Returns:
        StandardOutput with normalized pairs
    """
    tool_name = tool_name.lower().strip()
    if tool_name == "jplag":
        from src.benchmark.parsers.jplag_parser import JPlagParser
        return JPlagParser(dataset=dataset, threshold=threshold).parse(input_path)
    elif tool_name == "moss":
        from src.benchmark.parsers.moss_parser import MossParser
        return MossParser(dataset=dataset, threshold=threshold).parse(input_path)
    elif tool_name == "nicad":
        from src.benchmark.parsers.nicad_parser import NiCadParser
        return NiCadParser(dataset=dataset, threshold=threshold).parse(input_path)
    else:
        raise ParserError(f"Unknown tool: {tool_name}")


def load_standard_output(path: Path) -> StandardOutput:
    """Load StandardOutput from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return StandardOutput(tool=data.get("tool", "unknown"), dataset=data.get("dataset", ""),
                          pairs=data.get("pairs", []))


def save_standard_output(output: StandardOutput, path: Path) -> None:
    """Save StandardOutput to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(output.to_dict(), f, indent=2)
