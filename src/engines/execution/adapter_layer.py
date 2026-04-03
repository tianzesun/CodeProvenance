"""
Adapter Layer - Converts raw external tool output to unified Finding schema.

Takes ExecutionResult + parsed StandardOutput and converts to:
- Finding objects (domain schema)
- Unified score matrices
- Pair-level evidence blocks
"""

from __future__ import annotations

import csv
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.domain.models import EvidenceBlock, Finding

logger = logging.getLogger(__name__)


@dataclass
class ToolFinding:
    """A finding from an external tool, normalized to our schema."""
    tool_name: str
    file1: str
    file2: str
    similarity: float
    confidence: float
    evidence_blocks: List[EvidenceBlock] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_finding(self) -> Finding:
        return Finding(
            engine=self.tool_name,
            score=self.similarity,
            confidence=self.confidence,
            evidence_blocks=self.evidence_blocks,
            methodology=f"External tool: {self.tool_name}",
            metadata=self.metadata,
        )


class MossAdapter:
    """Adapts MOSS HTML output to unified findings."""

    def adapt(
        self,
        output_path: Path,
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> List[ToolFinding]:
        if not output_path or not output_path.exists():
            return []

        pairs = self._parse_html(output_path)
        return [self._to_finding(p, ground_truth) for p in pairs]

    def _parse_html(self, html_path: Path) -> List[Dict[str, Any]]:
        import re
        content = html_path.read_text(errors="ignore")
        pairs = []
        row_pat = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
        cell_pat = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
        for row_m in row_pat.finditer(content):
            cells = cell_pat.findall(row_m.group(1))
            if len(cells) < 2:
                continue
            info1 = self._extract_cell(cells[0])
            info2 = self._extract_cell(cells[1])
            if info1 and info2:
                sim = min(info1["sim"], info2["sim"]) / 100.0
                pairs.append({
                    "file1": info1["file"],
                    "file2": info2["file"],
                    "similarity": sim,
                    "matches": [],
                })
        return pairs

    def _extract_cell(self, cell: str) -> Optional[Dict[str, Any]]:
        import re
        import html as html_mod
        txt = html_mod.unescape(cell)
        pct = re.search(r'(\d+(?:\.\d+)?)\s*%', txt)
        if not pct:
            return None
        href = re.search(r'href="([^"]+)"', txt)
        fp = href.group(1).split("/")[-1] if href else txt.strip()
        fp = re.sub(r'\s*\(\d+(?:\.\d+)?\s*%\)', '', fp).strip()
        return {"file": fp, "sim": float(pct.group(1))} if fp else None

    def _to_finding(
        self, pair: Dict[str, Any],
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> ToolFinding:
        sim = pair["similarity"]
        confidence = 0.85 if sim > 0.7 else (0.65 if sim > 0.4 else 0.4)

        evidence = []
        if sim > 0.5:
            evidence.append(EvidenceBlock(
                engine="moss",
                score=sim,
                confidence=confidence,
                a_snippet=f"MOSS detected {sim:.1%} similarity",
                b_snippet=f"MOSS detected {sim:.1%} similarity",
                transformation_notes=["Token-sequence match via winnowing"],
            ))

        return ToolFinding(
            tool_name="moss",
            file1=pair["file1"],
            file2=pair["file2"],
            similarity=sim,
            confidence=confidence,
            evidence_blocks=evidence,
            metadata={"tool": "moss"},
        )


class JPlagAdapter:
    """Adapts JPlag JSON/XML output to unified findings."""

    def adapt(
        self,
        output_path: Path,
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> List[ToolFinding]:
        if not output_path or not output_path.exists():
            return []

        pairs = []
        if output_path.suffix == ".json":
            pairs = self._parse_json(output_path)
        elif output_path.suffix == ".xml":
            pairs = self._parse_xml(output_path)
        else:
            results_json = output_path.parent / "results.json"
            results_xml = output_path.parent / "results.xml"
            if results_json.exists():
                pairs = self._parse_json(results_json)
            elif results_xml.exists():
                pairs = self._parse_xml(results_xml)

        return [self._to_finding(p, ground_truth) for p in pairs]

    def _parse_json(self, json_path: Path) -> List[Dict[str, Any]]:
        data = json.loads(json_path.read_text())
        pairs = []
        for c in data.get("comparisons", []):
            sim = float(c.get("similarity", 0))
            if sim > 1.0:
                sim /= 100.0
            pairs.append({
                "file1": c.get("name1", ""),
                "file2": c.get("name2", ""),
                "similarity": sim,
                "matches": c.get("matches", []),
            })
        return pairs

    def _parse_xml(self, xml_path: Path) -> List[Dict[str, Any]]:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        pairs = []
        for comp in root.findall(".//submission_comparison"):
            f1 = comp.findtext(".//first_submission", "")
            f2 = comp.findtext(".//second_submission", "")
            s_elem = comp.find(".//average_similarity")
            sim = float(s_elem.text) if s_elem is not None else 0.0
            if sim > 1.0:
                sim /= 100.0
            matches = []
            for m in comp.findall(".//matches/match"):
                s1 = m.findtext(".//start_in_first", "0")
                e1 = m.findtext(".//end_in_first", "0")
                s2 = m.findtext(".//start_in_second", "0")
                e2 = m.findtext(".//end_in_second", "0")
                matches.append({"start1": int(s1), "end1": int(e1),
                                "start2": int(s2), "end2": int(e2)})
            pairs.append({"file1": f1, "file2": f2,
                          "similarity": sim, "matches": matches})
        return pairs

    def _to_finding(
        self, pair: Dict[str, Any],
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> ToolFinding:
        sim = pair["similarity"]
        confidence = 0.90 if sim > 0.7 else (0.70 if sim > 0.4 else 0.45)

        evidence = []
        for m in pair.get("matches", [])[:5]:
            evidence.append(EvidenceBlock(
                engine="jplag",
                score=sim,
                confidence=confidence,
                a_start_line=m.get("start1", 0),
                a_end_line=m.get("end1", 0),
                b_start_line=m.get("start2", 0),
                b_end_line=m.get("end2", 0),
                a_snippet=f"Match lines {m.get('start1', 0)}-{m.get('end1', 0)}",
                b_snippet=f"Match lines {m.get('start2', 0)}-{m.get('end2', 0)}",
                transformation_notes=["AST-based structural match"],
            ))

        if not evidence and sim > 0.5:
            evidence.append(EvidenceBlock(
                engine="jplag",
                score=sim,
                confidence=confidence,
                a_snippet=f"JPlag detected {sim:.1%} similarity",
                b_snippet=f"JPlag detected {sim:.1%} similarity",
                transformation_notes=["Structural similarity detected"],
            ))

        return ToolFinding(
            tool_name="jplag",
            file1=pair["file1"],
            file2=pair["file2"],
            similarity=sim,
            confidence=confidence,
            evidence_blocks=evidence,
            metadata={"tool": "jplag", "num_matches": len(pair.get("matches", []))},
        )


class DolosAdapter:
    """Adapts Dolos CSV output to unified findings."""

    def adapt(
        self,
        output_path: Path,
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> List[ToolFinding]:
        if not output_path or not output_path.exists():
            return []

        pairs = self._parse_csv(output_path)
        return [self._to_finding(p, ground_truth) for p in pairs]

    def _parse_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        pairs = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sim = float(row.get("similarity", row.get("score", 0)))
                pairs.append({
                    "file1": row.get("file1", row.get("left_file", "")),
                    "file2": row.get("file2", row.get("right_file", "")),
                    "similarity": sim,
                })
        return pairs

    def _to_finding(
        self, pair: Dict[str, Any],
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> ToolFinding:
        sim = pair["similarity"]
        confidence = 0.88 if sim > 0.7 else (0.68 if sim > 0.4 else 0.4)

        evidence = []
        if sim > 0.5:
            evidence.append(EvidenceBlock(
                engine="dolos",
                score=sim,
                confidence=confidence,
                a_snippet=f"Dolos detected {sim:.1%} similarity",
                b_snippet=f"Dolos detected {sim:.1%} similarity",
                transformation_notes=["Winnowing-based fingerprint match"],
            ))

        return ToolFinding(
            tool_name="dolos",
            file1=pair["file1"],
            file2=pair["file2"],
            similarity=sim,
            confidence=confidence,
            evidence_blocks=evidence,
            metadata={"tool": "dolos"},
        )


class NiCadAdapter:
    """Adapts NiCad XML output to unified findings."""

    def adapt(
        self,
        output_path: Path,
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> List[ToolFinding]:
        if not output_path or not output_path.exists():
            return []

        pairs = []
        if output_path.suffix == ".xml":
            pairs = self._parse_xml(output_path)
        else:
            content = output_path.read_text(errors="ignore")
            pairs = self._parse_text(content)

        return [self._to_finding(p, ground_truth) for p in pairs]

    def _parse_xml(self, xml_path: Path) -> List[Dict[str, Any]]:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        pairs = []
        for clone_class in root.findall(".//clone_class"):
            clone_type = clone_class.get("type", "3")
            for clone in clone_class.findall(".//clone"):
                fragments = clone.findall(".//fragment")
                if len(fragments) < 2:
                    continue
                for i in range(len(fragments)):
                    for j in range(i + 1, len(fragments)):
                        f1, f2 = fragments[i], fragments[j]
                        file1 = f1.findtext("file", "")
                        file2 = f2.findtext("file", "")
                        start1 = int(f1.findtext("start", "0"))
                        end1 = int(f1.findtext("end", "0"))
                        start2 = int(f2.findtext("start", "0"))
                        end2 = int(f2.findtext("end", "0"))
                        lines1 = end1 - start1 + 1
                        lines2 = end2 - start2 + 1
                        sim = min(lines1, lines2) / max(lines1, lines2) if max(lines1, lines2) > 0 else 0.0
                        pairs.append({
                            "file1": file1,
                            "file2": file2,
                            "similarity": sim,
                            "clone_type": int(clone_type),
                            "matches": [{"start1": start1, "end1": end1,
                                         "start2": start2, "end2": end2}],
                        })
        return pairs

    def _parse_text(self, content: str) -> List[Dict[str, Any]]:
        import re
        pairs = []
        clone_pat = re.compile(
            r'clone\s*#?\s*(\d+).*?type\s*[:=]\s*(\d+).*?'
            r'file\s*[:=]\s*(\S+).*?lines\s*[:=]\s*(\d+)-(\d+)',
            re.IGNORECASE | re.DOTALL,
        )
        clones = {}
        for m in clone_pat.finditer(content):
            cid = m.group(1)
            ctype = int(m.group(2))
            file = m.group(3)
            start, end = int(m.group(4)), int(m.group(5))
            clones.setdefault(cid, []).append({
                "file": file, "start": start, "end": end, "type": ctype,
            })
        for cid, frags in clones.items():
            for i in range(len(frags)):
                for j in range(i + 1, len(frags)):
                    f1, f2 = frags[i], frags[j]
                    lines1 = f1["end"] - f1["start"] + 1
                    lines2 = f2["end"] - f2["start"] + 1
                    sim = min(lines1, lines2) / max(lines1, lines2) if max(lines1, lines2) > 0 else 0.0
                    pairs.append({
                        "file1": f1["file"],
                        "file2": f2["file"],
                        "similarity": sim,
                        "clone_type": f1["type"],
                        "matches": [{"start1": f1["start"], "end1": f1["end"],
                                     "start2": f2["start"], "end2": f2["end"]}],
                    })
        return pairs

    def _to_finding(
        self, pair: Dict[str, Any],
        ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> ToolFinding:
        sim = pair["similarity"]
        clone_type = pair.get("clone_type", 3)
        confidence = 0.92 if clone_type <= 2 else (0.80 if clone_type == 3 else 0.60)

        evidence = []
        for m in pair.get("matches", [])[:5]:
            evidence.append(EvidenceBlock(
                engine="nicad",
                score=sim,
                confidence=confidence,
                a_start_line=m.get("start1", 0),
                a_end_line=m.get("end1", 0),
                b_start_line=m.get("start2", 0),
                b_end_line=m.get("end2", 0),
                a_snippet=f"Clone type {clone_type}, lines {m.get('start1', 0)}-{m.get('end1', 0)}",
                b_snippet=f"Clone type {clone_type}, lines {m.get('start2', 0)}-{m.get('end2', 0)}",
                transformation_notes=[f"Type-{clone_type} clone detected by NiCad"],
            ))

        if not evidence and sim > 0.5:
            evidence.append(EvidenceBlock(
                engine="nicad",
                score=sim,
                confidence=confidence,
                a_snippet=f"NiCad type-{clone_type} clone, {sim:.1%} similarity",
                b_snippet=f"NiCad type-{clone_type} clone, {sim:.1%} similarity",
                transformation_notes=[f"Type-{clone_type} clone"],
            ))

        return ToolFinding(
            tool_name="nicad",
            file1=pair["file1"],
            file2=pair["file2"],
            similarity=sim,
            confidence=confidence,
            evidence_blocks=evidence,
            metadata={"tool": "nicad", "clone_type": clone_type},
        )


class AdapterRegistry:
    """Registry mapping tool names to their adapters."""

    _adapters = {
        "moss": MossAdapter,
        "jplag": JPlagAdapter,
        "dolos": DolosAdapter,
        "nicad": NiCadAdapter,
    }

    @classmethod
    def get_adapter(cls, tool_name: str):
        cls_name = cls._adapters.get(tool_name.lower())
        if not cls_name:
            raise ValueError(f"No adapter for tool: {tool_name}")
        return cls_name()

    @classmethod
    def available_tools(cls) -> List[str]:
        return list(cls._adapters.keys())


def adapt_tool_output(
    tool_name: str,
    output_path: Path,
    ground_truth: Optional[Dict[Tuple[str, str], int]] = None,
) -> List[Finding]:
    """
    High-level function: adapt raw tool output to domain Findings.

    Args:
        tool_name: Name of the tool (moss, jplag, dolos, nicad).
        output_path: Path to the tool's output file.
        ground_truth: Optional mapping of (file1, file2) -> label.

    Returns:
        List of Finding objects.
    """
    adapter = AdapterRegistry.get_adapter(tool_name)
    tool_findings = adapter.adapt(output_path, ground_truth)
    return [tf.to_finding() for tf in tool_findings]
