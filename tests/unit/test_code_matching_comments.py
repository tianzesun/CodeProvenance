"""Added comments must not hide matched code from the side-by-side evidence."""

from src.backend.engines.similarity.code_matching import (
    CodeHighlighter,
    strip_hash_comment,
    uses_slash_comments,
)

SOURCE = """def mean(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)

def variance(values):
    m = mean(values)
    acc = 0
    for v in values:
        acc += (v - m) ** 2
    return acc / len(values)
"""


def test_trailing_comments_on_every_line_still_match() -> None:
    """A copy with a comment appended to each line is still one matched block."""
    commented = "\n".join(
        line + "  # step" if line.strip() else line for line in SOURCE.splitlines()
    )
    result = CodeHighlighter().find_matching_segments(SOURCE, commented)
    assert result.segments, "the commented copy must still show matching code"
    assert (
        result.total_matched_lines_a == 12
    ), "the whole source (lines 1-12) should be matched"
    assert (
        result.segments[0].similarity == 1.0
    ), "with comments cut the lines are identical"


def test_interleaved_comment_lines_keep_one_block_with_original_line_numbers() -> None:
    """Comment lines between copied lines neither split the match nor shift line numbers."""
    lines = SOURCE.splitlines()
    interleaved = "\n".join(
        f"{line}\n# explain" if line.strip() else line for line in lines
    )
    result = CodeHighlighter().find_matching_segments(SOURCE, interleaved)
    assert (
        len(result.segments) == 1
    ), "interleaved comments should not fragment the match"
    segment = result.segments[0]
    assert (segment.start_line_a, segment.end_line_a) == (1, 12)
    assert segment.start_line_b == 1
    assert (
        interleaved.splitlines()[segment.end_line_b - 1].strip()
        == "return acc / len(values)"
    )


def test_strip_hash_comment_keeps_code_strings_and_directives() -> None:
    """Only real ``#`` comments are removed."""
    assert strip_hash_comment("x = 1  # note") == "x = 1"
    assert strip_hash_comment("    # whole line") == ""
    assert strip_hash_comment('print("# of items")') == 'print("# of items")'
    assert strip_hash_comment("s = 'a # b'  # c") == "s = 'a # b'"
    assert strip_hash_comment("#include <stdio.h>") == "#include <stdio.h>"
    assert strip_hash_comment("#[derive(Debug)]") == "#[derive(Debug)]"
    assert strip_hash_comment("this.#count += 1;") == "this.#count += 1;"


def test_a_byte_order_mark_on_one_side_does_not_change_a_pair_score() -> None:
    """Pair scores are computed on BOM-free text."""
    from src.backend.application.services.batch_detection_service import (
        _without_bom,
    )

    assert _without_bom({"a.py": "﻿x = 1\n", "b.py": "x = 1\n"}) == {
        "a.py": "x = 1\n",
        "b.py": "x = 1\n",
    }


JAVA = """public class Main {
    static int sum(int[] a) {
        int s = 0;
        for (int i = 0; i < a.length; i++) {
            s += a[i];
        }
        return s;
    }
}
"""


def test_trailing_slash_comments_in_java_still_match() -> None:
    """A Java copy with ``// comment`` on every line is still matched."""
    commented = "\n".join(line + " // step" for line in JAVA.splitlines())
    result = CodeHighlighter().find_matching_segments(
        JAVA, commented, "Main.java", "Copy.java"
    )
    assert result.segments, "the commented Java copy must still show matching code"
    assert result.total_matched_lines_a == 9


def test_python_floor_division_is_never_cut() -> None:
    """``//`` is an operator in Python, so it is only cut for C-family files."""
    assert strip_hash_comment("half = n // 2") == "half = n // 2"
    assert strip_hash_comment("int h = n; // half", slash_comments=True) == "int h = n;"
    assert (
        strip_hash_comment('String u = "http://x"; // c', slash_comments=True)
        == 'String u = "http://x";'
    )
    assert uses_slash_comments("Main.JAVA") and not uses_slash_comments("main.py")
