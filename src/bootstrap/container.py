"""Dependency Container - single wiring location."""
from typing import Dict, Any, Optional

class Container:
    _services = {}
    
    @classmethod
    def register(cls, key, factory): cls._services[key] = factory
    @classmethod
    def resolve(cls, key): return cls._services[key]
    @classmethod
    def init(cls, weights=None, threshold=0.5):
        from src.application.use_cases.detect_submission import DetectSubmission
        cls.register('detect', DetectSubmission(weights, threshold))
    @classmethod
    def detect_submission(cls): return cls.resolve('detect')
