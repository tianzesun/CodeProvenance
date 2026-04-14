"""Benchmark datasets (BigCloneBench, Google Code Jam, Xiangtan, etc.).

Provides formal metadata contracts for cross-dataset comparison:
- DatasetMetadata: Contract for dataset metadata
- DatasetContract: Base class for all dataset loaders
- CloneType: Standardized clone types
- Difficulty: Dataset difficulty levels
- DatasetValidator: Validates datasets against schema
"""
# Schema and validators
from src.backend.benchmark.datasets.schema import (
    DatasetContract,
    DatasetMetadata,
    CloneType,
    Difficulty,
    CodePair,
    CanonicalDataset,
)
from src.backend.benchmark.datasets.validators import DatasetValidator

# Dataset loaders
from src.backend.benchmark.datasets.bigclonebench import BigCloneBenchDataset
from src.backend.benchmark.datasets.google_codejam import GoogleCodeJamDataset
from src.backend.benchmark.datasets.xiangtan import XiangtanDataset
from src.backend.benchmark.datasets.codesearchnet import CodeSearchNetDataset
from src.backend.benchmark.datasets.codesearchnet_java import CodeSearchNetJavaDataset
from src.backend.benchmark.datasets.codesearchnet_misc import CodeSearchNetMiscDataset
from src.backend.benchmark.datasets.code_similarity_dataset import CodeSimilarityDataset
from src.backend.benchmark.datasets.codexglue_clone import CodeXGLUECloneDataset
from src.backend.benchmark.datasets.codexglue_defect import CodeXGLUEDefectDataset
from src.backend.benchmark.datasets.poj104 import POJ104Dataset

__all__ = [
    # Schema and validators
    'DatasetContract',
    'DatasetMetadata',
    'CloneType',
    'Difficulty',
    'CodePair',
    'CanonicalDataset',
    'DatasetValidator',
    # Dataset loaders
    'BigCloneBenchDataset',
    'GoogleCodeJamDataset',
    'XiangtanDataset',
    'CodeSearchNetDataset',
    'CodeSearchNetJavaDataset',
    'CodeSearchNetMiscDataset',
    'CodeSimilarityDataset',
    'CodeXGLUECloneDataset',
    'CodeXGLUEDefectDataset',
    'POJ104Dataset',
]
