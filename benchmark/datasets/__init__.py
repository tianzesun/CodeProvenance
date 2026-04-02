"""Benchmark datasets (BigCloneBench, Google Code Jam, Xiangtan, etc.)."""
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
