"""Detector adapter implementations for EvalForge v2."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from src.backend.evalforge.core import BaseDetector, DetectionResult


class IntegrityDeskAdapter(BaseDetector):
    """Adapter for IntegrityDesk multi-engine detector."""
    
    @property
    def name(self) -> str:
        return "integritydesk"
    
    @property
    def description(self) -> str:
        return "Multi-engine fusion (AST + N-gram + Winnowing + Embedding + Token)"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.application.services.batch_detection_service import BatchDetectionService
        
        try:
            service = BatchDetectionService()
            result = service.compare_pair(code_a, code_b)
            
            return DetectionResult(
                score=result.score,
                confidence=result.confidence,
                metadata={
                    "ast": result.features.get("ast", 0.0),
                    "fingerprint": result.features.get("fingerprint", 0.0),
                    "embedding": result.features.get("embedding", 0.0),
                    "ngram": result.features.get("ngram", 0.0),
                    "winnowing": result.features.get("winnowing", 0.0),
                }
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


class MOSSAdapter(BaseDetector):
    """Adapter for MOSS (Measure of Software Similarity)."""
    
    @property
    def name(self) -> str:
        return "moss"
    
    @property
    def description(self) -> str:
        return "Token-based Jaccard similarity (Stanford)"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.benchmark.competitors.moss import run_moss_approx
        
        try:
            score = run_moss_approx(code_a, code_b)
            return DetectionResult(
                score=score,
                confidence=0.7,  # MOSS has fixed confidence baseline
                metadata={"engine": "moss"}
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


class JPlagAdapter(BaseDetector):
    """Adapter for JPlag AST-based detector."""
    
    @property
    def name(self) -> str:
        return "jplag"
    
    @property
    def description(self) -> str:
        return "AST structural comparison (KIT)"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.benchmark.competitors.jplag import run_jplag_approx
        
        try:
            score = run_jplag_approx(code_a, code_b)
            return DetectionResult(
                score=score,
                confidence=0.75,
                metadata={"engine": "jplag"}
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


class DolosAdapter(BaseDetector):
    """Adapter for Dolos winnowing-based detector."""
    
    @property
    def name(self) -> str:
        return "dolos"
    
    @property
    def description(self) -> str:
        return "Winnowing fingerprint comparison"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.benchmark.competitors.dolos import run_dolos_approx
        
        try:
            score = run_dolos_approx(code_a, code_b)
            return DetectionResult(
                score=score,
                confidence=0.65,
                metadata={"engine": "dolos"}
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


class NiCadAdapter(BaseDetector):
    """Adapter for NiCad near-miss clone detector."""
    
    @property
    def name(self) -> str:
        return "nicad"
    
    @property
    def description(self) -> str:
        return "Near-miss clone detector with normalization"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.benchmark.competitors.nicad import run_nicad_approx
        
        try:
            score = run_nicad_approx(code_a, code_b)
            return DetectionResult(
                score=score,
                confidence=0.6,
                metadata={"engine": "nicad"}
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


class PMDCPDAdapter(BaseDetector):
    """Adapter for PMD Copy/Paste Detector."""
    
    @property
    def name(self) -> str:
        return "pmd"
    
    @property
    def description(self) -> str:
        return "Copy/Paste duplicate token sequence detector"
    
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        from src.backend.benchmark.competitors.pmd import run_pmd_approx
        
        try:
            score = run_pmd_approx(code_a, code_b)
            return DetectionResult(
                score=score,
                confidence=0.55,
                metadata={"engine": "pmd"}
            )
        except Exception as e:
            return DetectionResult(
                score=0.0,
                confidence=0.0,
                metadata={"error": str(e)}
            )


def get_all_detectors() -> List[BaseDetector]:
    """Get all available detector adapters."""
    return [
        IntegrityDeskAdapter(),
        MOSSAdapter(),
        JPlagAdapter(),
        DolosAdapter(),
        NiCadAdapter(),
        PMDCPDAdapter(),
    ]


def get_detector(name: str) -> Optional[BaseDetector]:
    """Get detector by name."""
    for d in get_all_detectors():
        if d.name == name:
            return d
    return None