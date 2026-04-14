"""MOSS Parser - parses HTML output to StandardOutput."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import html as html_mod
from src.backend.benchmark.parsers.base_parser import BaseToolParser, StandardOutput, ParserError


class MossParser(BaseToolParser):
    """Parser for MOSS HTML output."""
    
    def __init__(self, dataset: str = "", threshold: float = 0.0):
        super().__init__(dataset)
        self.threshold = threshold
    
    @property
    def tool_name(self) -> str:
        return "moss"
    
    def parse(self, input_path: Path) -> StandardOutput:
        if not input_path.exists():
            raise ParserError(f"MOSS output not found: {input_path}")
        html_file = self._find_html_file(input_path)
        if not html_file:
            return StandardOutput(tool=self.tool_name, dataset=self.dataset)
        try:
            pairs = self._parse_html(html_file)
        except Exception:
            try:
                pairs = self._parse_regex(html_file)
            except Exception:
                pairs = []
        pairs = self.deduplicate_pairs(pairs)
        pairs = self.filter_pairs(pairs, self.threshold)
        return StandardOutput(tool=self.tool_name, dataset=self.dataset, pairs=pairs)
    
    def _find_html_file(self, path: Path) -> Optional[Path]:
        if path.is_file() and path.suffix in (".html", ".htm"):
            return path
        if path.is_dir():
            for p in ["index.html", "matches*.html", "*.html"]:
                for f in path.glob(p):
                    if f.is_file():
                        return f
        return None
    
    def _parse_html(self, html_path: Path) -> List[Dict[str, Any]]:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        pairs = []
        row_pat = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
        cell_pat = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
        pct_pat = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        for row_m in row_pat.finditer(content):
            cells = cell_pat.findall(row_m.group(1))
            if len(cells) < 2:
                continue
            info1 = self._extract_info(cells[0])
            info2 = self._extract_info(cells[1])
            if info1 and info2:
                # Use MIN for conservative estimate (MOSS is asymmetric)
                sim = min(info1["sim"], info2["sim"]) / 100.0
                pairs.append(self.make_pair(info1["file"], info2["file"], sim))
        return pairs
    
    def _extract_info(self, cell: str) -> Optional[Dict[str, Any]]:
        txt = html_mod.unescape(cell)
        pct = re.search(r'(\d+(?:\.\d+)?)\s*%', txt)
        if not pct:
            return None
        href = re.search(r'href="([^"]+)"', txt)
        if href:
            fp = href.group(1).split("/")[-1]
        else:
            tm = re.search(r'>([^<]+)</a>', txt)
            fp = tm.group(1) if tm else txt.strip()
        fp = re.sub(r'\s*\(\d+(?:\.\d+)?\s*%\)', '', fp).strip()
        fp = self.normalize_path(fp)
        return {"file": fp, "sim": float(pct.group(1))} if fp else None
    
    def _parse_regex(self, html_path: Path) -> List[Dict[str, Any]]:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        pairs = []
        pat = re.compile(r'(\S+)\s*\((\d+(?:\.\d+)?)\s*%\)\s+(\S+)\s*\((\d+(?:\.\d+)?)\s*%\)')
        for m in pat.finditer(content):
            f1, s1 = self.normalize_path(m.group(1)), float(m.group(2))
            f2, s2 = self.normalize_path(m.group(3)), float(m.group(4))
            pairs.append(self.make_pair(f1, f2, min(s1, s2) / 100.0))
        return pairs
