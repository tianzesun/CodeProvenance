"""MOSS Normalizer."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import html as html_mod
from src.benchmark.normalizer.base_normalizer import BaseNormalizer

class MossNormalizer(BaseNormalizer):
    @property
    def tool_name(self):
        return "moss"
    def normalize(self, output_path):
        if not output_path.exists():
            return []
        html_file = self._find_html(output_path)
        if not html_file:
            return []
        with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        results = []
        row_pat = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL|re.IGNORECASE)
        cell_pat = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL|re.IGNORECASE)
        pct_pat = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        for rm in row_pat.finditer(content):
            cells = cell_pat.findall(rm.group(1))
            if len(cells) < 2:
                continue
            info1 = self._extract_info(cells[0])
            info2 = self._extract_info(cells[1])
            if info1 and info2:
                sim = min(info1[1], info2[1]) / 100.0
                results.append({"file1": info1[0], "file2": info2[0], "similarity": sim})
        return self.deduplicate_pairs(results)
    def _extract_info(self, cell):
        txt = html_mod.unescape(cell)
        pct = re.search(r'(\d+(?:\.\d+)?)\s*%', txt)
        if not pct:
            return None
        href = re.search(r'href="([^"]+)"', txt)
        fp = href.group(1).split("/")[-1] if href else cell.strip()
        fp = re.sub(r'\s*\(\d+(?:\.\d+)?\s*%\)', '', fp).strip()
        return (fp, float(pct.group(1))) if fp else None
    def _find_html(self, path):
        if path.is_file() and path.suffix in (".html", ".htm"):
            return path
        if path.is_dir():
            for p in ["index.html", "*.html"]:
                for f in path.glob(p):
                    if f.is_file():
                        return f
        return None
