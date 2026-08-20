"""Unit tests for cluster_detection module."""

import pytest

from src.backend.evaluation.cluster_detection import (
    ClusterDetector,
    ClusterDetectionResult,
    SubmissionNode,
    SimilarityEdge,
    run_cluster_detection,
)


class TestSubmissionNode:
    """Tests for SubmissionNode dataclass."""

    def test_create_submission_node(self) -> None:
        """Test creating a submission node."""
        node = SubmissionNode(
            submission_id="sub_001",
            code_hash="abc123",
            language="python",
            content="print('hello')",
        )
        assert node.submission_id == "sub_001"
        assert node.language == "python"

    def test_submission_node_with_metadata(self) -> None:
        """Test submission node with metadata."""
        node = SubmissionNode(
            submission_id="sub_002",
            code_hash="",
            language="java",
            content="class Test {}",
            metadata={"student": "John"},
        )
        assert node.metadata == {"student": "John"}


class TestSimilarityEdge:
    """Tests for SimilarityEdge dataclass."""

    def test_create_similarity_edge(self) -> None:
        """Test creating a similarity edge."""
        edge = SimilarityEdge(
            submission_a="sub_001",
            submission_b="sub_002",
            similarity=0.85,
            engine="MOSS",
        )
        assert edge.similarity == 0.85
        assert edge.engine == "MOSS"

    def test_similarity_edge_with_evidence(self) -> None:
        """Test edge with evidence."""
        edge = SimilarityEdge(
            submission_a="sub_001",
            submission_b="sub_002",
            similarity=0.90,
            engine="JPlag",
            confidence=0.95,
            evidence=[{"type": "function", "name": "main"}],
        )
        assert len(edge.evidence) == 1


class TestClusterDetector:
    """Tests for ClusterDetector class."""

    def test_detect_single_cluster(self) -> None:
        """Test detecting a single cluster of submissions."""
        submissions = [
            SubmissionNode(
                submission_id=f"sub_{i}", code_hash="", language="py", content=""
            )
            for i in range(4)
        ]

        edges = [
            SimilarityEdge("sub_0", "sub_1", 0.80, "MOSS"),
            SimilarityEdge("sub_1", "sub_2", 0.75, "MOSS"),
            SimilarityEdge("sub_2", "sub_3", 0.85, "MOSS"),
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)

        assert result.total_submissions == 4
        assert result.total_clusters == 1
        assert result.max_cluster_size == 4

    def test_detect_multiple_clusters(self) -> None:
        """Test detecting multiple separate clusters."""
        submissions = [
            SubmissionNode(
                submission_id=f"sub_{i}", code_hash="", language="py", content=""
            )
            for i in range(6)
        ]

        edges = [
            SimilarityEdge("sub_0", "sub_1", 0.80, "MOSS"),
            SimilarityEdge("sub_2", "sub_3", 0.85, "MOSS"),
            SimilarityEdge("sub_4", "sub_5", 0.75, "MOSS"),
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)

        assert result.total_clusters == 3
        assert result.max_cluster_size == 2

    def test_detect_isolated_submissions(self) -> None:
        """Test detection with no similarity edges."""
        submissions = [
            SubmissionNode(
                submission_id=f"sub_{i}", code_hash="", language="py", content=""
            )
            for i in range(3)
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, [])

        assert result.total_clusters == 0
        assert len(result.isolated_submissions) == 3

    def test_threshold_filtering(self) -> None:
        """Test that threshold filters edges correctly."""
        submissions = [
            SubmissionNode(
                submission_id=f"sub_{i}", code_hash="", language="py", content=""
            )
            for i in range(4)
        ]

        edges = [
            SimilarityEdge("sub_0", "sub_1", 0.50, "MOSS"),  # Below threshold
            SimilarityEdge("sub_2", "sub_3", 0.80, "MOSS"),  # Above threshold
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)

        assert result.total_clusters == 1
        assert len(result.isolated_submissions) == 2

    def test_get_cluster_stats(self) -> None:
        """Test cluster statistics."""
        submissions = [
            SubmissionNode(
                submission_id=f"sub_{i}", code_hash="", language="py", content=""
            )
            for i in range(4)
        ]

        edges = [
            SimilarityEdge("sub_0", "sub_1", 0.80, "MOSS"),
            SimilarityEdge("sub_1", "sub_2", 0.75, "MOSS"),
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)
        stats = detector.get_cluster_stats(result)

        assert stats["total_clusters"] == 1
        assert stats["total_submissions"] == 4


class TestRunClusterDetection:
    """Tests for run_cluster_detection convenience function."""

    def test_run_cluster_detection_dicts(self) -> None:
        """Test running cluster detection with dict inputs."""
        submissions = [
            {"id": "sub_0", "hash": "abc", "language": "python", "content": "print(1)"},
            {"id": "sub_1", "hash": "def", "language": "python", "content": "print(2)"},
        ]

        similarity_results = [
            {
                "submission_a": "sub_0",
                "submission_b": "sub_1",
                "similarity": 0.80,
                "engine": "MOSS",
            }
        ]

        result = run_cluster_detection(submissions, similarity_results, threshold=0.65)

        assert isinstance(result, ClusterDetectionResult)
        assert result.total_submissions == 2


class TestClusterDetectionResult:
    """Tests for ClusterDetectionResult dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        result = ClusterDetectionResult(
            clusters=[],
            isolated_submissions=["sub_0"],
            total_submissions=1,
            total_clusters=0,
            max_cluster_size=0,
            has_violations=False,
        )

        d = result.to_dict()
        assert d["total_submissions"] == 1
        assert d["total_clusters"] == 0
        assert d["has_violations"] is False

    def test_to_dict_with_clusters(self) -> None:
        """Test serialization with clusters."""
        from src.backend.evaluation.cluster_detection import Cluster

        cluster = Cluster(
            cluster_id="cluster_001",
            submissions=["sub_0", "sub_1"],
            similarity_scores={"sub_0": 0.8, "sub_1": 0.85},
            max_similarity=0.85,
            avg_similarity=0.82,
            size=2,
            risk_level="high",
            evidence_summary=["test"],
        )

        result = ClusterDetectionResult(
            clusters=[cluster],
            isolated_submissions=[],
            total_submissions=2,
            total_clusters=1,
            max_cluster_size=2,
            has_violations=True,
        )

        d = result.to_dict()
        assert len(d["clusters"]) == 1
        assert d["clusters"][0]["risk_level"] == "high"
        assert d["has_violations"] is True


class TestClusterDetectorEdgeCases:
    """Tests for edge cases in ClusterDetector."""

    def test_empty_submissions(self) -> None:
        """Test with empty submissions list."""
        detector = ClusterDetector(threshold=0.65)
        result = detector.detect([], [])

        assert result.total_submissions == 0
        assert result.total_clusters == 0

    def test_single_submission(self) -> None:
        """Test with a single submission."""
        submissions = [
            SubmissionNode(
                submission_id="sub_0", code_hash="", language="py", content=""
            )
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, [])

        assert result.total_submissions == 1
        assert len(result.isolated_submissions) == 1

    def test_cycle_in_graph(self) -> None:
        """Test handling of cyclic edges (same submission)."""
        submissions = [
            SubmissionNode(
                submission_id="sub_0", code_hash="", language="py", content=""
            ),
        ]

        edges = [
            SimilarityEdge("sub_0", "sub_0", 0.90, "MOSS"),  # Self-edge
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)

        assert result.total_submissions == 1

    def test_build_cluster_with_evidence(self) -> None:
        """Test cluster building with evidence."""
        submissions = [
            SubmissionNode(
                submission_id="sub_0", code_hash="", language="py", content=""
            ),
            SubmissionNode(
                submission_id="sub_1", code_hash="", language="py", content=""
            ),
        ]

        edges = [
            SimilarityEdge(
                "sub_0",
                "sub_1",
                0.80,
                "MOSS",
                evidence=[{"type": "function", "name": "test"}],
            ),
        ]

        detector = ClusterDetector(threshold=0.65)
        result = detector.detect(submissions, edges)

        assert result.total_clusters == 1
        assert len(result.clusters[0].evidence_summary) > 0
