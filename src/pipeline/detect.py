"""Detection Pipeline - ONLY calls Orchestrator (never bypasses to engines)."""
from typing import Dict, List, Optional
from pathlib import Path
import json

def run_detection(pairs: List[Dict], code_store: Dict[str, str],
                  weights: Optional[Dict] = None, threshold: float = 0.5) -> List[Dict]:
    """
    Run detection pipeline.
    MUST use Orchestrator ONLY - never call engines/fusion/decision directly.
    """
    from src.core.orchestrator import Orchestrator
    from src.core.models import CodePair
    
    code_pairs = [CodePair(id=p.get("id",""), a=p.get("a",""), b=p.get("b",""), label=p.get("label",-1)) for p in pairs]
    orchestrator = Orchestrator(weights=weights, threshold=threshold)
    results = orchestrator.run(code_pairs, code_store)
    return [{"pair_id": r.pair_id, "score": r.score, "decision": r.decision, "confidence": r.confidence} for r in results]
