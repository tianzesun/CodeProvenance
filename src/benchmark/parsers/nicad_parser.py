"""NiCad Parser - parses XML clone output to StandardOutput."""
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET
from benchmark.parsers.base_parser import BaseToolParser, StandardOutput, ParserError


class NiCadParser(BaseToolParser):
    """Parser for NiCad XML output."""
    
    def __init__(self, dataset: str = "", threshold: float = 0.0):
        super().__init__(dataset)
        self.threshold = threshold
    
    @property
    def tool_name(self) -> str:
        return "nicad"
    
    def parse(self, input_path: Path) -> StandardOutput:
        if not input_path.exists():
            raise ParserError(f"NiCad output not found: {input_path}")
        xml_file = self._find_xml_file(input_path)
        if not xml_file:
            return StandardOutput(tool=self.tool_name, dataset=self.dataset)
        try:
            pairs = self._parse_xml(xml_file)
        except ET.ParseError:
            raise ParserError(f"Invalid NiCad XML: {xml_file}")
        pairs = self.deduplicate_pairs(pairs)
        pairs = self.filter_pairs(pairs, self.threshold)
        return StandardOutput(tool=self.tool_name, dataset=self.dataset, pairs=pairs)
    
    def _find_xml_file(self, path: Path) -> Optional[Path]:
        if path.is_file() and path.suffix == ".xml":
            return path
        if path.is_dir():
            for p in ["*.xml", "clones.xml"]:
                for f in path.glob(p):
                    if f.is_file():
                        return f
        return None
    
    def _parse_xml(self, xml_path: Path) -> List[Dict[str, Any]]:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        pair_counts = defaultdict(int)
        for cc in root.findall(".//clone"):
            instances = cc.findall(".//clone[@instance]")
            if len(instances) < 2:
                continue
            info = []
            for inst in instances:
                fe = inst.find(".//file")
                se = inst.find(".//start")
                ee = inst.find(".//end")
                if fe is None:
                    continue
                fp = self.normalize_path(fe.text or "")
                s, e = int((se.text or "0")), int((ee.text or "0"))
                if fp:
                    info.append((fp, s, e))
            for i in range(len(info)):
                for j in range(i+1, len(info)):
                    key = tuple(sorted([info[i][0], info[j][0]]))
                    pair_counts[key] += 1
        pairs = []
        for key, count in pair_counts.items():
            pairs.append(self.make_pair(key[0], key[1], 1.0))
        return pairs
