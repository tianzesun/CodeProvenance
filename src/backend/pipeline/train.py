"""Training Pipeline - Model training workflow."""
from typing import Dict, List, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json


@dataclass
class TrainingConfig:
    dataset_path: Path
    model_name: str = 'codebert'
    output_dir: Path = Path("ml/checkpoints")
    num_epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 2e-5


@dataclass
class TrainingOutput:
    model_path: Path
    metrics: Dict[str, Any]
    checkpoint_paths: List[Path]
    training_time: float
    model_name: str


class TrainingPipeline:
    def __init__(self, config: TrainingConfig):
        self.config = config

    def run(self) -> TrainingOutput:
        import time
        start = time.time()
        if not self.config.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.config.dataset_path}")
        return TrainingOutput(model_path=self.config.output_dir / f"{self.config.model_name}_latest",
                              metrics={'status': 'stub', 'epochs': 0}, checkpoint_paths=[],
                              training_time=time.time() - start, model_name=self.config.model_name)

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        checkpoints = []
        if self.config.output_dir.exists():
            for d in self.config.output_dir.iterdir():
                if d.is_dir():
                    info = d / "training_info.json"
                    if info.exists():
                        with open(info) as f:
                            data = json.load(f)
                            data['path'] = str(d)
                            checkpoints.append(data)
        return checkpoints
