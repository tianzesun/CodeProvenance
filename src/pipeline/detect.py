"""Detection Pipeline - Code similarity detection workflow."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
from src.engines.fusion.engine import FusionEngine


@dataclass
class DetectionOutput:
    job_id: str
    status: str
    pairs_analyzed: int
    suspicious_pairs: List[Dict[str, Any]]
    all_results: List[Dict[str, Any]]
    execution_time: float


class DetectionPipeline:
    def __init__(self, fusion_engine: Optional[FusionEngine] = None, threshold: float = 0.5):
        self.fusion_engine = fusion_engine or FusionEngine()
        self.threshold = threshold

    def run(self, code_samples: Dict[str, str], languages: Optional[Dict[str, str]] = None,
            threshold: Optional[float] = None) -> DetectionOutput:
        import time
        start_time = time.time()
        threshold = threshold or self.threshold
        all_results, suspicious = [], []
        files = list(code_samples.keys())
        for i, fa in enumerate(files):
            for fb in files[i + 1:]:
                lang = (languages or {}).get(fa, 'auto') if languages else 'auto'
                try:
                    result = self.fusion_engine.compare(code_samples[fa], code_samples[fb], language=lang)
                    pair = {'file_a': fa, 'file_b': fb, 'score': result.score, 'confidence': result.confidence,
                            'is_suspicious': result.score >= threshold, 'details': result.details}
                    all_results.append(pair)
                    if result.score >= threshold:
                        suspicious.append(pair)
                except Exception as e:
                    all_results.append({'file_a': fa, 'file_b': fb, 'error': str(e)})
        suspicious.sort(key=lambda x: x.get('score', 0), reverse=True)
        return DetectionOutput(job_id=f"det_{int(datetime.now().timestamp())}", status='completed',
                               pairs_analyzed=len(all_results), suspicious_pairs=suspicious,
                               all_results=all_results, execution_time=time.time() - start_time)

    def save(self, output: DetectionOutput, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump({'job_id': output.job_id, 'status': output.status, 'pairs_analyzed': output.pairs_analyzed,
                       'suspicious_pairs': output.suspicious_pairs, 'all_results': output.all_results,
                       'generated_at': datetime.now().isoformat()}, f, indent=2)
