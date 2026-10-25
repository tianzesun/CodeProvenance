"""Code most of a class shares is inferred as starter code (MOSS-style)."""

from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
)
from src.backend.engines.mvp import StarterCodeRemover

HANDOUT = '''import csv


def load_rows(path):
    """Read the course CSV into a list of dicts."""
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]
'''

OWN_CODE = [
    "def solve(rows):\n    return sorted(r['student'] for r in rows)\n",
    (
        "def solve(rows):\n    names = set()\n    for r in rows:\n"
        "        names.add(r['id'])\n    return len(names)\n"
    ),
    (
        "def solve(rows):\n    total = 0\n    for r in rows:\n"
        "        total += int(r['mark'])\n    return total\n"
    ),
    "def solve(rows):\n    return max(rows, key=lambda r: float(r['grade']))\n",
    "def solve(rows):\n    i = 0\n    while i < len(rows):\n        i += 2\n    return i\n",
    "def solve(rows):\n    return [r for r in rows if r.get('late') == 'yes']\n",
]


def _cohort() -> list[str]:
    return [HANDOUT + "\n\n" + own for own in OWN_CODE]


def test_handout_shared_by_the_class_is_removed() -> None:
    remover = StarterCodeRemover.from_cohort(_cohort())

    result = remover.remove(_cohort()[0])

    assert remover.inferred_common_lines > 0
    assert "csv.DictReader" not in result.filtered_source
    assert "sorted(r['student'] for r in rows)" in result.filtered_source


def test_small_cohort_infers_nothing() -> None:
    remover = StarterCodeRemover.from_cohort(_cohort()[:3])

    assert remover.inferred_common_lines == 0
    assert not remover.has_starter


def test_code_shared_by_under_half_the_class_is_kept() -> None:
    copied = (
        "def solve(rows):\n    totals = {}\n    for row in rows:\n"
        "        totals[row['s']] = totals.get(row['s'], 0) + 1\n    return totals\n"
    )
    cohort = _cohort()
    cohort[:2] = [HANDOUT + "\n\n" + copied] * 2  # 2 of 6 copy each other
    remover = StarterCodeRemover.from_cohort(cohort)

    assert "totals.get" in remover.remove(cohort[0]).filtered_source


def test_uploaded_starter_code_is_still_used() -> None:
    starter = "def helper(x):\n    y = x * 2\n    z = y + 1\n    return z\n"
    remover = StarterCodeRemover.from_cohort(_cohort()[:2], [starter])

    assert remover.has_starter
    assert "y = x * 2" not in remover.remove(starter + OWN_CODE[0]).filtered_source


def test_service_strips_shared_code_only_when_enabled() -> None:
    submissions = {f"s{i}.py": code for i, code in enumerate(_cohort())}

    def top_score(infer: bool) -> float:
        service = BatchDetectionService(infer_common_code=infer)
        results = service.compare_all_pairs(submissions, use_parallel=False)
        return max(result.score for result in results)

    assert top_score(True) < top_score(False)
