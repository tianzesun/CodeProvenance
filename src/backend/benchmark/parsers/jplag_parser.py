"""JPlag Parser - parses XML/JSON output to StandardOutput."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from src.backend.benchmark.parsers.base_parser import BaseToolParser, StandardOutput, ParserError


class JPlagParser(BaseToolParser):
    """Parser for JPlag XML and JSON output."""
    
    def __init__(self, dataset: str = "", threshold: float = 0.0):
        super().__init__(dataset)
        self.threshold = threshold
    
    @property
    def tool_name(self) -> str:
        return "jplag"
    
    def parse(self, input_path: Path) -> StandardOutput:
        if not input_path.exists():
            raise ParserError(f"JPlag output not found: {input_path}")
        xml_file = self._find_file(input_path, ".xml")
        json_file = self._find_file(input_path, ".json")
        if xml_file:
            pairs = self._parse_xml(xml_file)
        elif json_file:
            pairs = self._parse_json(json_file)
        else:
            results_dir = input_path / "results"
            pairs = self._parse_results_dir(results_dir) if results_dir.is_dir() else []
        pairs = self.deduplicate_pairs(pairs)
        pairs = self.filter_pairs(pairs, self.threshold)
        return StandardOutput(tool=self.tool_name, dataset=self.dataset, pairs=pairs)
    
    def _find_file(self, path: Path, ext: str) -> Optional[Path]:
        if path.is_file() and path.suffix == ext:
            return path
        if path.is_dir():
            for f in path.rglob(f"*{ext}"):
                if f.is_file():
                    return f
        return None
    
    def _parse_xml(self, xml_path: Path) -> List[Dict[str, Any]]:
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            raise ParserError(f"Invalid XML: {xml_path}")
        root = tree.getroot()
        pairs = []
        for comp in root.findall(".//submission_comparison"):
            f1_elem = comp.find(".//first_submission")
            f2_elem = comp.find(".//second_submission")
            s_elem = comp.find(".//average_similarity")
            if not all([f1_elem, f2_elem, s_elem]):
                continue
            f1 = self.normalize_path(f1_elem.text or "")
            f2 = self.normalize_path(f2_elem.text or "")
            sim = self.normalize_similarity(float(s_elem.text or "0"), 100.0)
            # Check max_similarity too
            ms_elem = comp.find(".//max_similarity")
            if ms_elem:
                sim = max(sim, self.normalize_similarity(float(ms_elem.text or "0"), 100.0))
            pair = self.make_pair(f1, f2, sim)
            for m in comp.findall(".//matches/match"):
                s1, e1 = m.find(".//start_in_first"), m.find(".//end_in_first")
                s2, e2 = m.find(".//start_in_second"), m.find(".//end_in_second")
                if all([s1, e1, s2, e2]):
                    pair["matches"].append({"start1": int(s1.text or "0"), "end1": int(e1.text or "0"),
                                            "start2": int(s2.text or "0"), "end2": int(e2.text or "0")})
            pairs.append(pair)
        return pairs
    
    def _parse_json(self, json_path: Path) -> List[Dict[str, Any]]:
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            raise ParserError(f"Invalid JSON: {json_path}")
        pairs = []
        for c in data.get("comparisons", []):
            sim = float(c.get("similarity", 0))
            if sim > 1.0:
                sim = self.normalize_similarity(sim, 100.0)
            pairs.append(self.make_pair(c.get("name1", ""), c.get("name2", ""), sim))
        return pairs
    
    def _parse_results_dir(self, results_dir: Path) -> List[Dict[str, Any]]:
        pairs = []
        for rf in results_dir.glob("result-*.xml"):
            try:
                tree = ET.parse(rf)
                root = tree.getroot()
                f1 = root.findtext(".//file1", "")
                f2 = root.findtext(".//file2", "")
                sim = float(root.findtext(".//similarity", "0"))
                if sim > 1.0:
                    sim /= 100.0
                pairs.append(self.make_pair(f1, f2, sim))
            except (ET.ParseError, IOError, ValueError):
                continue
        return pairs
