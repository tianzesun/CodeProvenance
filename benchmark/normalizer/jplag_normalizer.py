"""JPlag Normalizer."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import xml.etree.ElementTree as ET
import json
from benchmark.normalizer.base_normalizer import BaseNormalizer

class JPlagNormalizer(BaseNormalizer):
    @property
    def tool_name(self):
        return "jplag"
    def normalize(self, output_path):
        if not output_path.exists():
            return []
        xml_file = self._find_file(output_path, ".xml")
        json_file = self._find_file(output_path, ".json")
        results = []
        if xml_file:
            try:
                root = ET.parse(xml_file).getroot()
                for comp in root.findall(".//submission_comparison"):
                    f1 = (comp.find(".//first_submission") or {}).text or ""
                    f2 = (comp.find(".//second_submission") or {}).text or ""
                    s_elem = comp.find(".//average_similarity")
                    sim = float(s_elem.text or "0") if s_elem is not None else 0
                    ms = comp.find(".//max_similarity")
                    if ms is not None:
                        sim = max(sim, float(ms.text or "0"))
                    results.append({"file1": f1, "file2": f2, "similarity": min(1.0, sim/100.0)})
            except ET.ParseError:
                pass
        elif json_file:
            try:
                data = json.load(open(json_file))
                for c in data.get("comparisons", []):
                    f1, f2 = c.get("name1",""), c.get("name2","")
                    sim = float(c.get("similarity", 0))
                    results.append({"file1": f1, "file2": f2, "similarity": min(1.0, sim/100.0 if sim > 1 else sim)})
            except (json.JSONDecodeError, IOError):
                pass
        return self.deduplicate_pairs(results)
    def _find_file(self, path, ext):
        if path.is_file() and path.suffix == ext:
            return path
        if path.is_dir():
            for f in path.rglob(f"*{ext}"):
                if f.is_file():
                    return f
        return None
