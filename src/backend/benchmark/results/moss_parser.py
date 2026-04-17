from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class MossPair:
    left_name: str
    left_percent: int | None
    right_name: str
    right_percent: int | None
    lines_matched: int | None
    comparison_url: str | None
    local_comparison_path: str | None = None


@dataclass
class MossMirrorResult:
    result_url: str
    mirrored_root: str
    index_path: str
    pairs: list[MossPair] = field(default_factory=list)


class MossParserError(RuntimeError):
    pass


def _safe_filename_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "index.html"
    name = path.split("/")[-1]
    if "." not in name:
        name += ".html"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _parse_percent(value: str) -> tuple[str, int | None]:
    match = re.match(r"^(.*)\((\d+)%\)\s*$", value.strip())
    if not match:
        return value.strip(), None
    return match.group(1).strip(), int(match.group(2))


def _parse_lines(value: str) -> int | None:
    text = value.strip()
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _download_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _extract_pairs(index_html: str, base_url: str) -> list[MossPair]:
    soup = BeautifulSoup(index_html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    pairs: list[MossPair] = []
    rows = table.find_all("tr")
    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        left_anchor = cols[0].find("a")
        right_anchor = cols[1].find("a")
        lines_text = cols[2].get_text(" ", strip=True)

        if not left_anchor or not right_anchor:
            continue

        left_name, left_percent = _parse_percent(left_anchor.get_text(" ", strip=True))
        right_name, right_percent = _parse_percent(right_anchor.get_text(" ", strip=True))
        lines_matched = _parse_lines(lines_text)

        href = left_anchor.get("href") or right_anchor.get("href")
        comparison_url = urljoin(base_url, href) if href else None

        pairs.append(
            MossPair(
                left_name=left_name,
                left_percent=left_percent,
                right_name=right_name,
                right_percent=right_percent,
                lines_matched=lines_matched,
                comparison_url=comparison_url,
            )
        )

    return pairs


def mirror_moss_report(result_url: str, target_root: Path, limit_pairs: int = 200) -> MossMirrorResult:
    target_root.mkdir(parents=True, exist_ok=True)

    index_html = _download_html(result_url)
    index_path = target_root / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    pairs = _extract_pairs(index_html=index_html, base_url=result_url)

    for pair in pairs[:limit_pairs]:
        if not pair.comparison_url:
            continue
        try:
            comparison_html = _download_html(pair.comparison_url)
            filename = _safe_filename_from_url(pair.comparison_url)
            local_path = target_root / filename
            local_path.write_text(comparison_html, encoding="utf-8")
            pair.local_comparison_path = str(local_path)
        except Exception:
            pair.local_comparison_path = None

    mirror = MossMirrorResult(
        result_url=result_url,
        mirrored_root=str(target_root),
        index_path=str(index_path),
        pairs=pairs,
    )

    (target_root / "moss_pairs.json").write_text(
        json.dumps(asdict(mirror), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return mirror
