import requests
import logging
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Web-Scale Search Service.
    Integrates with external APIs (GitHub, Stack Overflow, etc.)
    to detect similarity with publicly available code.
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        stackoverflow_api_key: Optional[str] = None,
    ):
        self.github_token = github_token
        self.stackoverflow_api_key = stackoverflow_api_key
        # Header for GitHub API
        self.github_headers = (
            {"Authorization": f"token {github_token}"} if github_token else {}
        )

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

    def search_github(
        self, query_code: str, language: str = "python"
    ) -> List[Dict[str, Any]]:
        """Search GitHub for code snippets using the Code Search API."""
        if not self.github_token:
            logger.warning(
                "No GitHub token provided. GitHub search will be limited or disabled."
            )
            return []

        # Simplified: in a real system, you'd extract key tokens from the code for the query.
        # GitHub Code Search has strict rate limits.
        tokens = query_code.split()[:5]  # Use the first 5 words as a query
        query_str = " ".join(tokens) + f" language:{language}"

        url = "https://api.github.com/search/code"
        params = {"q": query_str}

        try:
            response = requests.get(
                url, headers=self.github_headers, params=params, timeout=8
            )
            response.raise_for_status()
            results = response.json().get("items", [])

            # Map GitHub response to internal result format
            mapped_results = []
            for r in results:
                candidate_text = " ".join(
                    [
                        r.get("name", ""),
                        r.get("path", ""),
                        r.get("repository", {}).get("full_name", ""),
                    ]
                )
                mapped_results.append(
                    {
                        "id": f"gh_{r['sha']}",
                        "name": r["repository"]["full_name"],
                        "url": r["html_url"],
                        "source": "github",
                        "similarity": self._score_match(query_code, candidate_text),
                    }
                )
            return mapped_results
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    def scan_github_repo(
        self, query_code: str, repo_url: str, language: str = "python"
    ) -> List[Dict[str, Any]]:
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

        matches: List[Dict[str, Any]] = []
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
                continue

            score = self._score_match(query_code, raw.text)
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

    def scan_configured_sources(
        self, query_code: str, language: str, source_sites: List[str]
    ) -> Dict[str, Any]:
        """Scan administrator-configured public source locations."""
        all_results: List[Dict[str, Any]] = []
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
        source_counts: Dict[str, int] = {}
        for result in all_results:
            source = str(result.get("source") or "web")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "web_results": all_results[:10],
            "max_web_similarity": all_results[0]["similarity"] if all_results else 0.0,
            "source_counts": source_counts,
            "configured_sources": configured_sources,
        }

    def _scan_raw_source_url(
        self, query_code: str, source_url: str
    ) -> List[Dict[str, Any]]:
        """Fetch and compare one configured raw source URL."""
        try:
            response = requests.get(source_url, timeout=8)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Configured source fetch failed for %s: %s", source_url, exc)
            return []

        score = self._score_match(query_code, response.text)
        return [
            {
                "id": f"web_{hash(source_url)}",
                "name": source_url,
                "url": source_url,
                "source": urlparse(source_url).netloc or "web",
                "similarity": score,
            }
        ]

    def _parse_github_repo(self, repo_url: str) -> Optional[tuple[str, str]]:
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

    def search_stackoverflow(self, query_code: str) -> List[Dict[str, Any]]:
        """Search Stack Overflow for code snippets."""
        # Simplified: Stack Overflow API search (SE API)
        url = "https://api.stackexchange.com/2.3/search/excerpts"
        params = {
            "q": " ".join(query_code.split()[:5]),
            "site": "stackoverflow",
            "key": self.stackoverflow_api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            results = response.json().get("items", [])

            mapped_results = []
            for r in results:
                candidate_text = " ".join(
                    [
                        r.get("title", ""),
                        str(r.get("excerpt", "")),
                    ]
                )
                mapped_results.append(
                    {
                        "id": f"so_{r['question_id']}",
                        "name": r["title"],
                        "url": f"https://stackoverflow.com/questions/{r['question_id']}",
                        "source": "stackoverflow",
                        "similarity": self._score_match(query_code, candidate_text),
                    }
                )
            return mapped_results
        except Exception as e:
            logger.error(f"Stack Overflow search failed: {e}")
            return []

    def perform_full_web_scan(self, code: str, language: str) -> Dict[str, Any]:
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
