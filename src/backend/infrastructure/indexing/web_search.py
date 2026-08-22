"""Web-scale public source search for external code provenance checks."""

import logging
import re
from html import unescape
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Maximum characters for a search probe; keeps API queries within provider limits.
_PROBE_MAX_CHARS = 120

# Minimum characters for a probe or code block to be considered signal.
_PROBE_MIN_CHARS = 15
_CODE_BLOCK_MIN_CHARS = 30

# Lines that never carry distinctive signal for code search queries: comment
# prefixes, dependency/import statements, and idiomatic entry-point guards.
_BOILERPLATE_LINE_RE = re.compile(
    r"^(?:"
    r"[#*]|//|/\*|<!--|--|;"
    r"|if\s+__name__\s*=="
    r"|(?:import|from|package|using|include|require|extern)\b"
    r")"
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CODE_BLOCK_RE = re.compile(r"<code[^>]*>(.*?)</code>", re.DOTALL | re.IGNORECASE)


class WebSearchService:
    """
    Web-Scale Search Service.
    Integrates with external APIs (GitHub, Stack Overflow, etc.)
    to detect similarity with publicly available code.
    """

    def __init__(
        self,
        github_token: str | None = None,
        stackoverflow_api_key: str | None = None,
    ):
        self.github_token = github_token
        self.stackoverflow_api_key = stackoverflow_api_key
        # Header for GitHub API
        self.github_headers = (
            {"Authorization": f"token {github_token}"} if github_token else {}
        )

    # ------------------------------------------------------------------
    # Query construction and similarity scoring
    # ------------------------------------------------------------------

    def _extract_probe_queries(self, query_code: str, max_probes: int = 2) -> list[str]:
        """Build distinctive search probes from a code snippet's salient lines.

        Imports, comments, and idiomatic boilerplate are skipped because they
        match millions of unrelated files; identifier-dense lines are the most
        selective queries for public code search.
        """
        scored: list[tuple[float, str]] = []
        for raw_line in (query_code or "").splitlines():
            line = raw_line.strip()
            if len(line) < _PROBE_MIN_CHARS or self._is_boilerplate_line(line):
                continue
            tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", line)
            if len(tokens) < 2:
                continue
            avg_token_len = sum(len(token) for token in tokens) / len(tokens)
            scored.append((avg_token_len, line))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        probes: list[str] = []
        for _, line in scored:
            probe = re.sub(r"\s+", " ", line)[:_PROBE_MAX_CHARS].strip()
            if len(probe) >= _PROBE_MIN_CHARS and probe not in probes:
                probes.append(probe)
            if len(probes) >= max_probes:
                break
        return probes

    @staticmethod
    def _is_boilerplate_line(line: str) -> bool:
        """Return True for imports, comments, and other non-distinctive lines."""
        return bool(_BOILERPLATE_LINE_RE.match(line))

    def _tokenize_text(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", (text or "").lower())
            if len(token) > 2
        }

    def _score_match(
        self, query_code: str, candidate_text: str, base_score: float = 0.0
    ) -> float:
        """Compute a simple lexical similarity score instead of placeholder constants."""
        query_tokens = self._tokenize_text(query_code)
        candidate_tokens = self._tokenize_text(candidate_text)

        if not query_tokens or not candidate_tokens:
            return round(max(0.0, min(1.0, base_score)), 4)

        overlap = len(query_tokens & candidate_tokens)
        union = len(query_tokens | candidate_tokens)
        jaccard = overlap / union if union else 0.0

        # Give a small boost for exact phrase presence without letting score explode.
        phrase = " ".join(query_code.split()[:5]).strip().lower()
        phrase_boost = (
            0.1 if phrase and phrase in (candidate_text or "").lower() else 0.0
        )

        return round(min(1.0, max(base_score, (jaccard * 0.85) + phrase_boost)), 4)

    def _code_similarity(
        self, query_code: str, candidate_code: str, k: int = 5
    ) -> float:
        """Fraction of the query's token k-grams found verbatim in the candidate.

        Containment (rather than symmetric similarity) answers the provenance
        question directly: how much of the submission appears in the public
        source, regardless of how much extra content that source carries.
        """
        query_grams = self._shingle_tokens(query_code, k)
        if not query_grams:
            return 0.0
        candidate_grams = self._shingle_tokens(candidate_code, k)
        if not candidate_grams:
            return 0.0
        containment = len(query_grams & candidate_grams) / len(query_grams)
        return round(min(1.0, containment), 4)

    @staticmethod
    def _shingle_tokens(code: str, k: int) -> set[tuple[str, ...]]:
        """Return the set of token k-grams (shingles) for a code snippet."""
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", (code or "").lower())
        if len(tokens) < k:
            return set()
        return {
            tuple(tokens[index : index + k]) for index in range(len(tokens) - k + 1)
        }

    # ------------------------------------------------------------------
    # GitHub
    # ------------------------------------------------------------------

    def search_github(
        self, query_code: str, language: str = "python"
    ) -> list[dict[str, Any]]:
        """Search GitHub public code using the submission's distinctive lines.

        Results are scored against the matched file fragments returned by the
        text-match media type, so similarity reflects actual code content
        rather than repository metadata.
        """
        if not self.github_token:
            logger.warning(
                "No GitHub token provided. GitHub search will be limited or disabled."
            )
            return []

        probes = self._extract_probe_queries(query_code)
        mapped: dict[str, dict[str, Any]] = {}
        for probe in probes:
            try:
                response = requests.get(
                    "https://api.github.com/search/code",
                    headers={
                        **self.github_headers,
                        "Accept": "application/vnd.github.text-match+json",
                    },
                    params={"q": f"{probe} language:{language}", "per_page": 5},
                    timeout=8,
                )
                response.raise_for_status()
                items = response.json().get("items", [])
            except Exception as exc:
                logger.error("GitHub search failed: %s", exc)
                continue

            for item in items:
                url = str(item.get("html_url") or "")
                if not url or url in mapped:
                    continue
                fragments = "\n".join(
                    str(match.get("fragment") or "")
                    for match in item.get("text_matches", [])
                )
                similarity = self._code_similarity(query_code, fragments)
                if similarity <= 0:
                    continue
                repository = item.get("repository") or {}
                mapped[url] = {
                    "id": f"gh_{item.get('sha', '')}",
                    "name": f"{repository.get('full_name', '')}/{item.get('path', '')}",
                    "url": url,
                    "source": "github",
                    "similarity": similarity,
                }

        ranked = sorted(
            mapped.values(), key=lambda item: item["similarity"], reverse=True
        )
        return ranked[:5]

    def scan_github_repo(
        self, query_code: str, repo_url: str, language: str = "python"
    ) -> list[dict[str, Any]]:
        """Scan a configured public GitHub repository for similar source files."""
        repo = self._parse_github_repo(repo_url)
        if not repo:
            return []

        owner, name = repo
        tree_url = f"https://api.github.com/repos/{owner}/{name}/git/trees/HEAD"
        suffixes = self._language_suffixes(language)
        try:
            response = requests.get(
                tree_url,
                headers=self.github_headers,
                params={"recursive": "1"},
                timeout=10,
            )
            response.raise_for_status()
            tree = response.json().get("tree", [])
        except Exception as exc:
            logger.error("GitHub repo tree fetch failed for %s: %s", repo_url, exc)
            return []

        matches: list[dict[str, Any]] = []
        for item in tree:
            path = str(item.get("path") or "")
            if item.get("type") != "blob" or not path.endswith(suffixes):
                continue
            if int(item.get("size") or 0) > 200_000:
                continue
            raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/HEAD/{path}"
            try:
                raw = requests.get(raw_url, headers=self.github_headers, timeout=8)
                raw.raise_for_status()
            except Exception:
                logger.debug("Failed to fetch raw source %s", raw_url, exc_info=True)
                continue

            score = self._code_similarity(query_code, raw.text)
            if score <= 0:
                continue
            matches.append(
                {
                    "id": f"gh_repo_{owner}_{name}_{path}",
                    "name": f"{owner}/{name}/{path}",
                    "url": f"https://github.com/{owner}/{name}/blob/HEAD/{path}",
                    "source": "github",
                    "similarity": score,
                }
            )
            if len(matches) >= 40:
                break

        return sorted(matches, key=lambda item: item["similarity"], reverse=True)[:10]

    # ------------------------------------------------------------------
    # Stack Overflow
    # ------------------------------------------------------------------

    def search_stackoverflow(self, query_code: str) -> list[dict[str, Any]]:
        """Search Stack Overflow answers whose code blocks resemble the submission.

        Two steps: excerpt search to locate candidate questions, then an
        answer fetch with bodies so similarity is scored against the actual
        posted code, not just question titles and excerpts.
        """
        probes = self._extract_probe_queries(query_code, max_probes=1)
        if not probes:
            return []

        params = {
            "q": probes[0],
            "site": "stackoverflow",
            "pagesize": 10,
        }
        if self.stackoverflow_api_key:
            params["key"] = self.stackoverflow_api_key
        try:
            response = requests.get(
                "https://api.stackexchange.com/2.3/search/excerpts",
                params=params,
                timeout=8,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except Exception as exc:
            logger.error("Stack Overflow search failed: %s", exc)
            return []

        titles: dict[int, str] = {}
        for item in items:
            question_id = int(item.get("question_id") or 0)
            if question_id and question_id not in titles:
                titles[question_id] = str(item.get("title") or "")
        question_ids = list(titles.keys())[:5]
        if not question_ids:
            return []

        ids_param = ";".join(str(question_id) for question_id in question_ids)
        answer_params = {
            "site": "stackoverflow",
            "filter": "withbody",
            "pagesize": 30,
        }
        if self.stackoverflow_api_key:
            answer_params["key"] = self.stackoverflow_api_key
        try:
            response = requests.get(
                f"https://api.stackexchange.com/2.3/questions/{ids_param}/answers",
                params=answer_params,
                timeout=8,
            )
            response.raise_for_status()
            answers = response.json().get("items", [])
        except Exception as exc:
            logger.error("Stack Overflow answer fetch failed: %s", exc)
            return []

        best_by_question: dict[int, float] = {}
        for answer in answers:
            question_id = int(answer.get("question_id") or 0)
            if not question_id:
                continue
            for block in self._extract_code_blocks(str(answer.get("body") or "")):
                score = self._code_similarity(query_code, block)
                best_by_question[question_id] = max(
                    best_by_question.get(question_id, 0.0), score
                )

        mapped = [
            {
                "id": f"so_{question_id}",
                "name": titles.get(
                    question_id, f"Stack Overflow question {question_id}"
                ),
                "url": f"https://stackoverflow.com/questions/{question_id}",
                "source": "stackoverflow",
                "similarity": score,
            }
            for question_id, score in best_by_question.items()
            if score > 0
        ]
        return sorted(mapped, key=lambda item: item["similarity"], reverse=True)[:5]

    @staticmethod
    def _extract_code_blocks(html_body: str) -> list[str]:
        """Extract unescaped code blocks from a Stack Overflow HTML body."""
        blocks: list[str] = []
        for raw in _CODE_BLOCK_RE.findall(html_body or ""):
            text = unescape(_HTML_TAG_RE.sub("", raw)).strip()
            if len(text) >= _CODE_BLOCK_MIN_CHARS:
                blocks.append(text)
        return blocks

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def scan_configured_sources(
        self, query_code: str, language: str, source_sites: list[str]
    ) -> dict[str, Any]:
        """Scan administrator-configured public source locations."""
        all_results: list[dict[str, Any]] = []
        configured_sources = [site.strip() for site in source_sites if site.strip()]

        for site in configured_sources:
            parsed = urlparse(site if "://" in site else f"https://{site}")
            host = parsed.netloc.lower()
            if host.endswith("github.com"):
                repo_results = self.scan_github_repo(query_code, site, language)
                all_results.extend(
                    repo_results or self.search_github(query_code, language)
                )
            else:
                all_results.extend(self._scan_raw_source_url(query_code, site))

        all_results.sort(key=lambda item: item.get("similarity", 0), reverse=True)
        source_counts: dict[str, int] = {}
        for result in all_results:
            source = str(result.get("source") or "web")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "web_results": all_results[:10],
            "max_web_similarity": all_results[0]["similarity"] if all_results else 0.0,
            "source_counts": source_counts,
            "configured_sources": configured_sources,
        }

    def scan_public_sources(
        self, query_code: str, language: str, source_sites: list[str]
    ) -> dict[str, Any]:
        """Scan built-in public sources plus administrator-configured locations.

        Built-in sources are GitHub code search (requires a token) and Stack
        Overflow (works without a key). Failures in any source never raise;
        they only shrink the result set.
        """
        configured = self.scan_configured_sources(query_code, language, source_sites)
        all_results: list[dict[str, Any]] = list(configured.get("web_results", []))
        all_results.extend(self.search_github(query_code, language))
        all_results.extend(self.search_stackoverflow(query_code))

        deduped: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for result in all_results:
            url = str(result.get("url") or "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(result)
        deduped.sort(key=lambda item: item.get("similarity", 0), reverse=True)

        source_counts: dict[str, int] = {}
        for result in deduped:
            source = str(result.get("source") or "web")
            source_counts[source] = source_counts.get(source, 0) + 1

        skipped = [] if self.github_token else ["github"]
        return {
            "web_results": deduped[:10],
            "max_web_similarity": deduped[0]["similarity"] if deduped else 0.0,
            "source_counts": source_counts,
            "configured_sources": configured.get("configured_sources", []),
            "skipped_sources": skipped,
        }

    def _scan_raw_source_url(
        self, query_code: str, source_url: str
    ) -> list[dict[str, Any]]:
        """Fetch and compare one configured raw source URL."""
        try:
            response = requests.get(source_url, timeout=8)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Configured source fetch failed for %s: %s", source_url, exc)
            return []

        score = self._code_similarity(query_code, response.text)
        return [
            {
                "id": f"web_{hash(source_url)}",
                "name": source_url,
                "url": source_url,
                "source": urlparse(source_url).netloc or "web",
                "similarity": score,
            }
        ]

    def _parse_github_repo(self, repo_url: str) -> tuple[str, str] | None:
        """Return owner/repo from a GitHub repository URL."""
        parsed = urlparse(repo_url if "://" in repo_url else f"https://{repo_url}")
        if not parsed.netloc.lower().endswith("github.com"):
            return None
        parts = [part for part in PurePosixPath(parsed.path).parts if part != "/"]
        if len(parts) < 2:
            return None
        return parts[0], parts[1].removesuffix(".git")

    def _language_suffixes(self, language: str) -> tuple[str, ...]:
        """Return code suffixes used for repository source filtering."""
        return {
            "python": (".py",),
            "java": (".java",),
            "javascript": (".js", ".jsx"),
            "typescript": (".ts", ".tsx"),
            "cpp": (".cpp", ".cc", ".cxx", ".h", ".hpp"),
            "c": (".c", ".h"),
        }.get(language, (".py", ".java", ".js", ".ts", ".c", ".cpp"))

    def perform_full_web_scan(self, code: str, language: str) -> dict[str, Any]:
        """Perform a comprehensive web-scale scan."""
        github_results = self.search_github(code, language)
        so_results = self.search_stackoverflow(code)

        all_results = github_results + so_results
        all_results.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "web_results": all_results[:10],
            "max_web_similarity": all_results[0]["similarity"] if all_results else 0.0,
            "source_counts": {
                "github": len(github_results),
                "stackoverflow": len(so_results),
            },
        }
