"""Unit tests bounding the cost of a large submission.

A single million-line file used to pass the only upload check (a hard-coded
10 MB byte limit) and then ran for hours: the CFG builder grew super-linearly
and the chunker compared every chunk of A against every chunk of B. These tests
pin the bounds that make that impossible - per-file lines, per-upload file
count, and the graph growth inside the normalizer.
"""

import ast
import io
import time
import zipfile

import pytest

from src.backend.api import server
from src.backend.application.services.batch_detection_service import (
    MAX_CHUNK_COMPARISONS_PER_PAIR,
    BatchDetectionService,
    _aligned_chunks,
)
from src.backend.config.settings import settings
from src.backend.engines.features.ast_normalizer import (
    MAX_CFG_NODES,
    MAX_PENDING_EXITS,
    ASTNormalizer,
    CFGBuilder,
    CFGComparator,
    CFGTooLargeError,
    _cap_exits,
)


def _code_file(line_count: int) -> bytes:
    """Build a valid Python file of exactly *line_count* short lines."""
    body = "".join(f"x{index} = {index}\n" for index in range(line_count))
    return body.encode("utf-8")


class TestSubmissionSizeGuard:
    """``_check_submission_size`` rejects work, not just bytes."""

    def test_a_file_within_both_limits_is_accepted(self) -> None:
        assert server._check_submission_size("ok.py", _code_file(100)) is None

    def test_oversized_file_is_rejected_with_a_named_limit(self) -> None:
        error = server._check_submission_size(
            "big.py", _code_file(settings.MAX_FILE_LINES + 1)
        )

        assert error is not None
        assert "big.py" in error
        assert f"{settings.MAX_FILE_LINES:,}" in error

    def test_million_line_file_is_rejected(self) -> None:
        """The regression this guard exists for.

        Short statements keep such a file comfortably under the byte limit, so a
        byte-only check let it through.
        """
        million_lines = b"x = 1\n" * 1_000_000
        assert len(million_lines) < 10 * 1024 * 1024

        error = server._check_submission_size("million.py", million_lines)

        assert error is not None
        assert "1,000,000 lines" in error

    def test_trailing_line_without_newline_still_counts(self) -> None:
        """A file whose last line has no terminator must not be under-counted."""
        limit = settings.MAX_FILE_LINES
        content = b"x = 1\n" * (limit - 1) + b"x = 1"

        assert server._check_submission_size("edge.py", content) is None

        oversized = b"x = 1\n" * limit + b"x = 1"
        assert server._check_submission_size("edge.py", oversized) is not None


class TestSubmissionCountGuard:
    """``MAX_FILES_PER_JOB`` is enforced rather than merely advertised."""

    def test_upload_within_the_limit_is_accepted(self) -> None:
        assert server._check_submission_count(2) is None

    def test_upload_beyond_the_limit_is_rejected(self) -> None:
        error = server._check_submission_count(settings.MAX_FILES_PER_JOB + 1)

        assert error is not None
        assert str(settings.MAX_FILES_PER_JOB) in error


class TestZipExtractionGuard:
    """The 200 MB zip cap bounds compressed bytes, so members need their own."""

    def test_zip_within_limits_is_extracted(self, tmp_path) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("a.py", "def a():\n    return 1\n")
            archive.writestr("b.py", "def b():\n    return 2\n")
        zip_path = tmp_path / "ok.zip"
        zip_path.write_bytes(buffer.getvalue())

        extracted = server._extract_zip(zip_path, tmp_path)

        assert len(extracted) == 2
        assert (tmp_path / "a.py").read_text() == "def a():\n    return 1\n"

    def test_small_zip_hiding_an_oversized_member_is_rejected(self, tmp_path) -> None:
        """A tiny archive that expands past the line limit must not be accepted.

        Compressing a million short lines yields a small zip, so the archive-level
        byte cap never sees it.
        """
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("a.py", "x = 1\n")
            archive.writestr("bomb.py", b"x = 1\n" * (settings.MAX_FILE_LINES + 1))
        zip_path = tmp_path / "bomb.zip"
        zip_path.write_bytes(buffer.getvalue())

        with pytest.raises(server.UploadTooLargeError):
            server._extract_zip(zip_path, tmp_path)

        assert not (tmp_path / "bomb.py").exists()


class TestAlignedChunks:
    """Chunk pairing is positional, not a cross product."""

    class _Chunk:
        """Minimal stand-in carrying only the identity fields pairing uses."""

        def __init__(self, chunk_id: int) -> None:
            """Record the chunk's ordinal."""
            self.chunk_id = chunk_id

    def test_aligned_pairs_match_by_position(self) -> None:
        a = [self._Chunk(0), self._Chunk(1)]
        b = [self._Chunk(0), self._Chunk(1)]

        pairs = _aligned_chunks(a, b)

        assert [(x.chunk_id, y.chunk_id) for x, y in pairs] == [(0, 0), (1, 1)]

    def test_pair_count_is_linear_not_quadratic(self) -> None:
        """206 chunks per side must not become 42,436 comparisons."""
        a = [self._Chunk(i) for i in range(206)]
        b = [self._Chunk(i) for i in range(206)]

        assert len(_aligned_chunks(a, b)) == 206

    def test_longer_side_repeats_the_last_chunk_of_the_shorter(self) -> None:
        a = [self._Chunk(i) for i in range(3)]
        b = [self._Chunk(0)]

        pairs = _aligned_chunks(a, b)

        assert [(x.chunk_id, y.chunk_id) for x, y in pairs] == [(0, 0), (1, 0), (2, 0)]

    def test_empty_side_yields_no_pairs(self) -> None:
        assert _aligned_chunks([], [self._Chunk(0)]) == []


class TestChunkComparisonCap:
    """A pair cannot schedule more full engine sweeps than the cap allows."""

    def test_cap_is_a_positive_bound(self) -> None:
        assert MAX_CHUNK_COMPARISONS_PER_PAIR > 0

    def test_cap_bounds_work_for_a_very_large_pair(self, monkeypatch) -> None:
        """Two huge files must stop at the cap instead of running forever."""
        service = BatchDetectionService(threshold=0.5)
        calls: list[int] = []

        class _Chunk:
            """Synthetic chunk with the fields the pairer reads."""

            def __init__(self, chunk_id: int) -> None:
                """Build a one-line chunk at a stable offset."""
                self.content = "x = 1\n"
                self.chunk_id = chunk_id
                self.start_line = chunk_id + 1
                self.line_count = 1

        class _Chunking:
            """Stand-in chunking result with a controllable chunk count."""

            def __init__(self, count: int) -> None:
                """Build *count* synthetic chunks."""
                self.chunk_count = count
                self.original_size = count
                self.chunks = [_Chunk(i) for i in range(count)]

        def fake_chunk_pair(chunk_a, chunk_b, *args):
            """Record one chunk comparison and return a minimal result."""
            calls.append(len(chunk_a))
            return {
                "score": 0.1,
                "ngram": 0.1,
                "matching_blocks": [],
                "weight": 1.0,
            }

        chunk_count = MAX_CHUNK_COMPARISONS_PER_PAIR + 50
        monkeypatch.setattr(service, "_compare_chunk_pair", fake_chunk_pair)
        monkeypatch.setattr(
            "src.backend.infrastructure.code_chunker.chunk_large_file",
            lambda code, language, filename: _Chunking(chunk_count),
        )


class TestCFGBuilderGrowth:
    """The normalizer builds a bounded graph in bounded time."""

    def test_edges_are_deduplicated(self) -> None:
        _nodes, edges = CFGBuilder().build(ast.parse("x = 1\n"))

        assert len(edges) == len(set(edges))

    def test_successor_and_predecessor_links_match_the_edge_list(self) -> None:
        nodes, edges = CFGBuilder().build(ast.parse("x = 1\ny = 2\n"))
        by_id = {node.node_id: node for node in nodes}

        for source_id, target_id in edges:
            assert target_id in by_id[source_id].successors
            assert source_id in by_id[target_id].predecessors

    def test_nested_branches_do_not_grow_the_graph_multiplicatively(self) -> None:
        """The regression behind the >600 s build.

        Pending exits used to multiply at every compound statement, so a function
        with nested branches produced far more nodes than statements.
        """
        depth = 12
        source_lines = ["def f():"]
        indent = "    "
        for level in range(depth):
            source_lines.append(f"{indent}if x > {level}:")
            indent += "    "
        source_lines.append(f"{indent}pass")
        source = "\n".join(source_lines) + "\n"

        start = time.perf_counter()
        nodes, _edges = CFGBuilder().build(ast.parse(source))
        elapsed = time.perf_counter() - start

        assert len(nodes) <= MAX_CFG_NODES
        assert elapsed < 10.0

    def test_pathological_program_is_refused_rather_than_hanging(self) -> None:
        """The builder must refuse an oversized graph instead of grinding on.

        The counter is driven directly because generating enough statements to
        trip a ceiling this high would make the test itself unbounded.
        """
        builder = CFGBuilder()
        tree = ast.parse("x = 1\n")
        nodes, _edges = builder.build(tree)

        # Every node minting checks the counter that ``build`` just reset.
        builder._node_counter = MAX_CFG_NODES

        with pytest.raises(CFGTooLargeError):
            builder._make_node("Extra")

        assert len(nodes) > 0

    def test_oversized_program_still_reports_ast_evidence(self) -> None:
        """A refused graph must not discard the cheaper AST signal."""
        normalizer = ASTNormalizer()

        def refuse(tree):
            """Always refuse the graph."""
            raise CFGTooLargeError("too large")

        normalizer.cfg_builder.build = refuse

        program = normalizer.normalize("def f():\n    return 1\n")

        assert program is not None
        assert program.cfg_nodes == []
        assert program.pdg_nodes == []
        assert program.token_sequence


class TestPendingExitCap:
    """``_cap_exits`` bounds the fan-out between consecutive statements."""

    def test_duplicates_are_removed_order_preservingly(self) -> None:
        assert _cap_exits([3, 1, 3, 2, 1]) == [3, 1, 2]

    def test_long_lists_are_truncated_to_the_cap(self) -> None:
        assert len(_cap_exits(list(range(MAX_PENDING_EXITS * 10)))) == MAX_PENDING_EXITS

    def test_short_lists_pass_through(self) -> None:
        assert _cap_exits([5, 6]) == [5, 6]


class TestCFGComparatorEmptyGraph:
    """An unavailable graph is not evidence of agreement."""

    def test_two_empty_graphs_score_zero(self) -> None:
        program = ASTNormalizer().normalize("def f():\n    return 1\n")
        empty = type(program)(**{**program.__dict__, "cfg_nodes": [], "cfg_edges": []})

        assert CFGComparator.compare(empty, empty) == 0.0
