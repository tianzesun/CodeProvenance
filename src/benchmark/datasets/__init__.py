"""Benchmark datasets (BigCloneBench, Google Code Jam, Xiangtan, etc.).

Provides formal metadata contracts for cross-dataset comparison:
- DatasetMetadata: Contract for dataset metadata
- DatasetContract: Base class for all dataset loaders
- CloneType: Standardized clone types
- Difficulty: Dataset difficulty levels
- DatasetValidator: Validates datasets against schema
"""
# Schema and validators
from src.benchmark.datasets.schema import (
    DatasetContract,
    DatasetMetadata,
    CloneType,
    Difficulty,
    CodePair,
    CanonicalDataset,
)
from src.benchmark.datasets.validators import DatasetValidator

# Dataset loaders
from src.benchmark.datasets.bigclonebench import BigCloneBenchDataset
from src.benchmark.datasets.google_codejam import GoogleCodeJamDataset
from src.benchmark.datasets.xiangtan import XiangtanDataset
from src.benchmark.datasets.codesearchnet import CodeSearchNetDataset
from src.benchmark.datasets.codesearchnet_java import CodeSearchNetJavaDataset
from src.benchmark.datasets.codesearchnet_misc import CodeSearchNetMiscDataset
from src.benchmark.datasets.code_similarity_dataset import CodeSimilarityDataset
from src.benchmark.datasets.codexglue_clone import CodeXGLUECloneDataset
from src.benchmark.datasets.codexglue_defect import CodeXGLUEDefectDataset
from src.benchmark.datasets.poj104 import POJ104Dataset

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
