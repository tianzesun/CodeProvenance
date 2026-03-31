"""BigCloneBench runner for CodeProvenance."""
from typing import Dict, List, Any, Optional
from pathlib import Path
from benchmark.runners.base_runner import BaseRunner, BenchmarkPair


class BigCloneBenchRunner(BaseRunner):
    def __init__(self, threshold: float = 0.5, clone_types: Optional[List[int]] = None):
        super().__init__(name="BigCloneBench", threshold=threshold)
        self.clone_types = clone_types

    def load_dataset(self, dataset_path: Path) -> List[BenchmarkPair]:
        pairs = []
        pairs_file = dataset_path / "pairs" / "pairs.txt"
        if not pairs_file.exists():
            raise FileNotFoundError(f"Pairs file not found: {pairs_file}")
        with open(pairs_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) < 5:
                    continue
                file_a, func_a, file_b, func_b = parts[0], parts[1], parts[2], parts[3]
                clone_type = int(parts[4])
                if self.clone_types and clone_type not in self.clone_types:
                    continue
                path_a = dataset_path / "source" / file_a
                path_b = dataset_path / "source" / file_b
                if not path_a.exists() or not path_b.exists():
                    continue
                pairs.append(BenchmarkPair(
                    id=f"bc_{line_num}",
                    code_a=path_a.read_text(),
                    code_b=path_b.read_text(),
                    language='java',
                    is_clone=True,
                    clone_type=clone_type,
                ))
        return pairs

    def preprocess_code(self, code: str) -> str:
        import re
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'[ \t]+', ' ', code)
        return code.strip()

    def run_comparison(self, pair: BenchmarkPair, similarity_threshold: float = 0.5) -> float:
        from src.core.analyzer.code_analyzer import CodeAnalyzer
        analyzer = CodeAnalyzer(threshold=0.0, enable_deep_analysis=True, enable_ai_detection=False)
        result = analyzer.compare_codes(pair.code_a, pair.code_b, 'java', 'java')
        return result.overall_score
