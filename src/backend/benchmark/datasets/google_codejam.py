"""
Google Code Jam Dataset Loader / Generator.

Generates a Code Jam-style dataset with:
- 3 problems (count words, sort scores, palindrome check)
- Multiple implementation variants per problem
- Labeled plagiarism pairs (similar vs different)

Expected structure:
    google_codejam/
    └── submissions/
        ├── problem_A/python/solution_0.py ...
        ├── problem_B/python/solution_0.py ...
        └── problem_C/python/solution_0.py ...
    └── ground_truth.json
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from dataclasses import dataclass, field


@dataclass
class CodeJamSubmission:
    """A code submission."""
    path: str
    problem: str
    source_code: str = ""


@dataclass
class CodeJamPair:
    """A pair of submissions with plagiarism label."""
    file1: str
    file2: str
    label: int  # 1 = plagiarized, 0 = original
    problem: str = ""


def generate_dataset(data_dir: Path = Path("benchmark/data/google_codejam")) -> List[CodeJamPair]:
    """Generate a Code Jam-style dataset with plagiarism labels.
    
    Args:
        data_dir: Output directory.
        
    Returns:
        List of CodeJamPair objects.
    """
    sub_dir = data_dir / "submissions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    
    problems = [
        ("problem_A", "count_words", [
            ("def solve(t):\n    return len(t.split())\n\nif __name__ == '__main__':\n    t = input()\n    print(solve(t))\n", "Split"),
            ("import re\ndef solve(t):\n    return len(re.findall(r'\\w+', t))\n\nt = input()\nprint(solve(t))\n", "Regex"),
            ("def solve(t):\n    c, w = 0, False\n    for ch in t:\n        if ch == ' ' and w: w = False\n        elif ch != ' ': c += 1; w = True\n    return c\n\nprint(solve(input()))\n", "Manual"),
        ]),
        ("problem_B", "sort_scores", [
            ("def solve(x):\n    n = len(x)\n    for i in range(n):\n        for j in range(n-i-1):\n            if x[j] > x[j+1]: x[j], x[j+1] = x[j+1], x[j]\n    return x\n\nprint(solve(list(map(int, input().split()))))\n", "Bubble"),
            ("def solve(x): return sorted(x)\n\nprint(solve(list(map(int, input().split()))))\n", "Sorted"),
            ("def solve(x):\n    x.sort()\n    return x\n\nprint(solve(list(map(int, input().split()))))\n", "In-place"),
        ]),
        ("problem_C", "palindrome", [
            ("def solve(s): return s == s[::-1]\n\ns = input().strip()\nprint('YES' if solve(s) else 'NO')\n", "Slice"),
            ("def solve(s):\n    l, r = 0, len(s) - 1\n    while l < r:\n        if s[l] != s[r]: return False\n        l += 1; r -= 1\n    return True\n\nprint('YES' if solve(input().strip()) else 'NO')\n", "Pointers"),
            ("def check(s): return s == s[::-1]\n\nt = input().strip()\nprint('YES' if check(t) else 'NO')\n", "Copied-Slice"),
        ]),
    ]
    
    pairs = []
    
    for problem_id, name, solutions in problems:
        prob_dir = sub_dir / problem_id / "python"
        prob_dir.mkdir(parents=True, exist_ok=True)
        
        for i, (code, name_tag) in enumerate(solutions):
            (prob_dir / f"solution_{i}.py").write_text(code)
        
        # All pairs
        for i in range(len(solutions)):
            for j in range(i + 1, len(solutions)):
                label = 0
                if problem_id == 'problem_C' and i == 0 and j == 2:
                    label = 1  # Copied-Slice plagiarized from Slice
                pairs.append(CodeJamPair(
                    file1=f"{problem_id}/python/solution_{i}.py",
                    file2=f"{problem_id}/python/solution_{j}.py",
                    label=label,
                    problem=problem_id,
                ))
    
    # Ground truth
    gt = {
        "pairs": [
            {"file1": p.file1, "file2": p.file2, "label": p.label, "problem": p.problem}
            for p in pairs
        ],
        "problem_count": len(problems),
        "solution_count": sum(len(s) for _, _, s in problems),
    }
    (data_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return pairs


class GoogleCodeJamDataset:
    """Loader for Code Jam-style dataset."""
    
    def __init__(self, data_dir: Path = Path("benchmark/data/google_codejam")):
        self.data_dir = data_dir
        self.submissions_dir = data_dir / "submissions"
        self.gt_file = data_dir / "ground_truth.json"
        self._pairs: List[CodeJamPair] = []

    def load(self, max_pairs: Optional[int] = None) -> List[CodeJamPair]:
        if not self.gt_file.exists():
            return generate_dataset(self.data_dir)
        
        gt = json.loads(self.gt_file.read_text())
        pairs = [
            CodeJamPair(
                file1=p['file1'], file2=p['file2'],
                label=p.get('label', 0), problem=p.get('problem', ''),
            )
            for p in gt.get('pairs', [])
        ]
        if max_pairs:
            pairs = pairs[:max_pairs]
        self._pairs = pairs
        return pairs
    
    def get_stats(self) -> Dict[str, Any]:
        subs = list(self.submissions_dir.rglob("*.py")) if self.submissions_dir.exists() else []
        return {
            "name": "Google Code Jam",
            "submissions": len(subs),
            "ground_truth": self.gt_file.exists(),
            "loaded_pairs": len(self._pairs),
        }
    
    def check_availability(self) -> Dict[str, bool]:
        return {
            "data_dir": self.data_dir.exists(),
            "submissions_dir": self.submissions_dir.exists(),
            "ground_truth": self.gt_file.exists(),
        }