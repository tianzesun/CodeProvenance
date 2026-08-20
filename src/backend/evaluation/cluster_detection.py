"""Cluster Detection - Similarity graph analysis for plagiarism clusters.

Groups submissions into connected components based on similarity scores,
identifying potential academic integrity violations.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default clustering threshold
DEFAULT_CLUSTER_THRESHOLD = 0.65


@dataclass
class SubmissionNode:
    """A node in the similarity graph representing a submission."""

    submission_id: str
    code_hash: str
    language: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimilarityEdge:
    """An edge in the similarity graph connecting two submissions."""

    submission_a: str
    submission_b: str
    similarity: float
    engine: str
    confidence: float = 1.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Cluster:
    """A cluster of submissions with high mutual similarity."""

    cluster_id: str
    submissions: List[str]
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    max_similarity: float = 0.0
    avg_similarity: float = 0.0
    size: int = 0
    risk_level: str = "low"
    evidence_summary: List[str] = field(default_factory=list)


@dataclass
class ClusterDetectionResult:
    """Result of cluster detection analysis."""

    clusters: List[Cluster] = field(default_factory=list)
    isolated_submissions: List[str] = field(default_factory=list)
    total_submissions: int = 0
    total_clusters: int = 0
    max_cluster_size: int = 0
    has_violations: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "submissions": c.submissions,
                    "similarity_scores": c.similarity_scores,
                    "max_similarity": c.max_similarity,
                    "avg_similarity": c.avg_similarity,
                    "size": c.size,
                    "risk_level": c.risk_level,
                    "evidence_summary": c.evidence_summary,
                }
                for c in self.clusters
            ],
            "isolated_submissions": self.isolated_submissions,
            "total_submissions": self.total_submissions,
            "total_clusters": self.total_clusters,
            "max_cluster_size": self.max_cluster_size,
            "has_violations": self.has_violations,
        }


class ClusterDetector:
    """Detects plagiarism clusters using Union-Find on similarity graphs."""

    def __init__(self, threshold: float = DEFAULT_CLUSTER_THRESHOLD) -> None:
        """
        Initialize the cluster detector.

        Args:
            threshold: Minimum similarity score to consider for clustering.
        """
        self.threshold = threshold
        self._parent: Dict[str, str] = {}
        self._rank: Dict[str, int] = {}
        self._similarities: Dict[Tuple[str, str], float] = {}

    def _find(self, x: str) -> str:
        """Find root of x with path compression."""
        if self._parent[x] != x:
            self._parent[x] = self._find(self._parent[x])
        return self._parent[x]

    def _union(self, x: str, y: str) -> None:
        """Union by rank."""
        px, py = self._find(x), self._find(y)
        if px == py:
            return
        if self._rank[px] < self._rank[py]:
            px, py = py, px
        self._parent[py] = px
        if self._rank[px] == self._rank[py]:
            self._rank[px] += 1

    def detect(
        self,
        submissions: List[SubmissionNode],
        edges: List[SimilarityEdge],
    ) -> ClusterDetectionResult:
        """
        Detect clusters in the similarity graph.

        Args:
            submissions: List of submission nodes.
            edges: List of similarity edges.

        Returns:
            ClusterDetectionResult with detected clusters.
        """
        # Initialize Union-Find
        for sub in submissions:
            self._parent[sub.submission_id] = sub.submission_id
            self._rank[sub.submission_id] = 0

        # Store similarities and union edges above threshold
        for edge in edges:
            key = (edge.submission_a, edge.submission_b)
            self._similarities[key] = edge.similarity
            if edge.similarity >= self.threshold:
                self._union(edge.submission_a, edge.submission_b)

        # Group submissions by cluster
        cluster_groups: Dict[str, List[str]] = defaultdict(list)
        for sub in submissions:
            root = self._find(sub.submission_id)
            cluster_groups[root].append(sub.submission_id)

        # Build cluster objects
        clusters = []
        isolated = []

        for root, members in cluster_groups.items():
            if len(members) == 1:
                isolated.append(members[0])
            else:
                cluster = self._build_cluster(root, members, edges)
                clusters.append(cluster)

        # Determine if there are violations
        has_violations = any(c.risk_level in ("high", "critical") for c in clusters)

        result = ClusterDetectionResult(
            clusters=clusters,
            isolated_submissions=isolated,
            total_submissions=len(submissions),
            total_clusters=len(clusters),
            max_cluster_size=max((len(c.submissions) for c in clusters), default=0),
            has_violations=has_violations,
        )

        logger.info(
            f"Detected {len(clusters)} clusters from {len(submissions)} submissions"
        )
        return result

    def _build_cluster(
        self,
        cluster_id: str,
        members: List[str],
        edges: List[SimilarityEdge],
    ) -> Cluster:
        """Build a Cluster object from members and edges."""
        # Calculate pairwise similarities
        similarities: Dict[str, float] = {}
        edge_similarities = []
        evidence_summary = []

        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                key = (a, b) if (a, b) in self._similarities else (b, a)
                sim = self._similarities.get(key, 0.0)
                edge_similarities.append(sim)
                similarities[a] = max(similarities.get(a, 0.0), sim)
                similarities[b] = max(similarities.get(b, 0.0), sim)

                # Collect evidence
                for edge in edges:
                    if (edge.submission_a == a and edge.submission_b == b) or (
                        edge.submission_a == b and edge.submission_b == a
                    ):
                        if edge.evidence:
                            for ev in edge.evidence[:2]:
                                # Convert dict to string for hashing
                                if isinstance(ev, dict):
                                    evidence_summary.append(
                                        json.dumps(ev, sort_keys=True)
                                    )
                                else:
                                    evidence_summary.append(str(ev))

        max_sim = max(edge_similarities) if edge_similarities else 0.0
        avg_sim = (
            sum(edge_similarities) / len(edge_similarities)
            if edge_similarities
            else 0.0
        )

        # Determine risk level
        if max_sim >= 0.85:
            risk_level = "critical"
        elif max_sim >= 0.70:
            risk_level = "high"
        elif max_sim >= 0.50:
            risk_level = "medium"
        else:
            risk_level = "low"

        return Cluster(
            cluster_id=f"cluster_{cluster_id[:8]}",
            submissions=members,
            similarity_scores=similarities,
            max_similarity=max_sim,
            avg_similarity=avg_sim,
            size=len(members),
            risk_level=risk_level,
            evidence_summary=list(dict.fromkeys(evidence_summary))[:5],
        )

    def get_cluster_stats(self, result: ClusterDetectionResult) -> Dict[str, Any]:
        """Get statistics about detected clusters."""
        return {
            "total_clusters": result.total_clusters,
            "total_submissions": result.total_submissions,
            "isolated_count": len(result.isolated_submissions),
            "clusters_with_violations": sum(
                1 for c in result.clusters if c.risk_level in ("high", "critical")
            ),
            "total_clustered_submissions": sum(c.size for c in result.clusters),
            "average_cluster_size": (
                result.total_clusters / result.total_clusters
                if result.total_clusters
                else 0
            ),
        }


def run_cluster_detection(
    submissions: List[Dict[str, Any]],
    similarity_results: List[Dict[str, Any]],
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
) -> ClusterDetectionResult:
    """
    Convenience function to run cluster detection from dict inputs.

    Args:
        submissions: List of submission dicts with 'id', 'hash', 'language', 'content'.
        similarity_results: List of similarity result dicts.
        threshold: Minimum similarity for clustering.

    Returns:
        ClusterDetectionResult with detected clusters.
    """
    submission_nodes = [
        SubmissionNode(
            submission_id=s["id"],
            code_hash=s.get("hash", ""),
            language=s.get("language", "unknown"),
            content=s.get("content", ""),
            metadata=s.get("metadata", {}),
        )
        for s in submissions
    ]

    edges = [
        SimilarityEdge(
            submission_a=e["submission_a"],
            submission_b=e["submission_b"],
            similarity=e.get("similarity", 0.0),
            engine=e.get("engine", "unknown"),
            confidence=e.get("confidence", 1.0),
            evidence=e.get("evidence", []),
        )
        for e in similarity_results
    ]

    detector = ClusterDetector(threshold=threshold)
    return detector.detect(submission_nodes, edges)
