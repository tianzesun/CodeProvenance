import requests
import json
import logging
import re
from typing import Dict, List, Any, Optional
from src.backend.infrastructure.indexing.global_search import GlobalSearchService

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Web-Scale Search Service.
    Integrates with external APIs (GitHub, Stack Overflow, etc.) 
    to detect similarity with publicly available code.
    """
    
    def __init__(self, github_token: Optional[str] = None, stackoverflow_api_key: Optional[str] = None):
        self.github_token = github_token
        self.stackoverflow_api_key = stackoverflow_api_key
        # Header for GitHub API
        self.github_headers = {"Authorization": f"token {github_token}"} if github_token else {}

    def _tokenize_text(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", (text or "").lower())
            if len(token) > 2
        }

    def _score_match(self, query_code: str, candidate_text: str, base_score: float = 0.0) -> float:
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
        phrase_boost = 0.1 if phrase and phrase in (candidate_text or "").lower() else 0.0

        return round(min(1.0, max(base_score, (jaccard * 0.85) + phrase_boost)), 4)

    def search_github(self, query_code: str, language: str = "python") -> List[Dict[str, Any]]:
        """Search GitHub for code snippets using the Code Search API."""
        if not self.github_token:
            logger.warning("No GitHub token provided. GitHub search will be limited or disabled.")
            return []

        # Simplified: in a real system, you'd extract key tokens from the code for the query.
        # GitHub Code Search has strict rate limits.
        tokens = query_code.split()[:5] # Use the first 5 words as a query
        query_str = " ".join(tokens) + f" language:{language}"
        
        url = "https://api.github.com/search/code"
        params = {"q": query_str}
        
        try:
            response = requests.get(url, headers=self.github_headers, params=params, timeout=8)
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
                mapped_results.append({
                    "id": f"gh_{r['sha']}",
                    "name": r["repository"]["full_name"],
                    "url": r["html_url"],
                    "source": "github",
                    "similarity": self._score_match(query_code, candidate_text),
                })
            return mapped_results
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    def search_stackoverflow(self, query_code: str) -> List[Dict[str, Any]]:
        """Search Stack Overflow for code snippets."""
        # Simplified: Stack Overflow API search (SE API)
        url = "https://api.stackexchange.com/2.3/search/excerpts"
        params = {
            "q": " ".join(query_code.split()[:5]),
            "site": "stackoverflow",
            "key": self.stackoverflow_api_key
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
                mapped_results.append({
                    "id": f"so_{r['question_id']}",
                    "name": r["title"],
                    "url": f"https://stackoverflow.com/questions/{r['question_id']}",
                    "source": "stackoverflow",
                    "similarity": self._score_match(query_code, candidate_text),
                })
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
            "source_counts": {"github": len(github_results), "stackoverflow": len(so_results)}
        }
