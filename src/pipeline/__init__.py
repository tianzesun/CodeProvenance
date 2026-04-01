"""Pipeline layer - orchestrates detection and benchmark workflows."""
from src.pipeline.detect import run_detection
from src.pipeline.train import TrainingPipeline, TrainingConfig
__all__ = ['run_detection', 'TrainingPipeline', 'TrainingConfig']
