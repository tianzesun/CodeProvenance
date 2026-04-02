"""Benchmark datasets (BigCloneBench, Google Code Jam, Xiangtan, etc.).

Provides formal metadata contracts for cross-dataset comparison:
- DatasetMetadata: Contract for dataset metadata
- DatasetContract: Base class for all dataset loaders
- CloneType: Standardized clone types
- Difficulty: Dataset difficulty levels
- DatasetValidator: Validates datasets against schema
"""
# Schema and validators
from benchmark.datasets.schema import (
    DatasetContract,
    DatasetMetadata,
    CloneType,
    Difficulty,
    CodePair,
    CanonicalDataset,
)
from benchmark.datasets.validators import DatasetValidator

# Dataset loaders
from benchmark.datasets.bigclonebench import BigCloneBenchDataset
from benchmark.datasets.google_codejam import GoogleCodeJamDataset
from benchmark.datasets.xiangtan import XiangtanDataset
from benchmark.datasets.codesearchnet import CodeSearchNetDataset
from benchmark.datasets.codesearchnet_java import CodeSearchNetJavaDataset
from benchmark.datasets.codesearchnet_misc import CodeSearchNetMiscDataset
from benchmark.datasets.code_similarity_dataset import CodeSimilarityDataset
from benchmark.datasets.codexglue_clone import CodeXGLUECloneDataset
from benchmark.datasets.codexglue_defect import CodeXGLUEDefectDataset
from benchmark.datasets.poj104 import POJ104Dataset

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
