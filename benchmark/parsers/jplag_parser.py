"""Parser for JPlag XML/JSON output."""
from typing import List, Dict, Any
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from benchmark.parsers.base_parser import BaseToolParser, ToolResult


class JPlagParser(BaseToolParser):
    @property
    def tool_name(self) -> str:
        return "jplag"

    def parse(self, output_path: Path) -> ToolResult:
        if output_path.suffix == ".xml":
            return self._parse_xml(output_path)
        elif output_path.suffix == ".json":
            return self._parse_json(output_path)
        else:
            return ToolResult(pairs=[])

    def _parse_xml(self, path: Path) -> ToolResult:
        tree = ET.parse(path)
        root = tree.getroot()
        pairs = []
        for submission in root.findall(".//submission"):
            for other in submission.findall(".//other-submission"):
                f1 = submission.find("name").text
                f2 = other.find("name").text
                sim = float(other.get("sim", 0))
                pair = ToolResult.make_pair(f1, f2, sim)
                # JPlag match details
                for match in other.findall(".//match"):
                    ToolResult.add_match(
                        pair,
                        match.get("start1", 0), match.get("end1", 0),
                        match.get("start2", 0), match.get("end2", 0),
                    )
                pairs.append(pair)
        return ToolResult(pairs=pairs)

    def _parse_json(self, path: Path) -> ToolResult:
        with open(path) as f:
            data = json.load(f)
        pairs = []
        for p in data.get("comparisons", []):
            pair = ToolResult.make_pair(
                p.get("submission1", p.get("name1", "")),
                p.get("submission2", p.get("name2", "")),
                p.get("similarity", p.get("matches", 0)),
            )
            for m in p.get("matches", []):
                ToolResult.add_match(pair, m.get("start1",0), m.get("end1",0),
                                     m.get("start2",0), m.get("end2",0))
            pairs.append(pair)
        return ToolResult(pairs=pairs)
