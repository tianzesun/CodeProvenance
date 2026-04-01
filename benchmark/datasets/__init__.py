"""Benchmark datasets (BigCloneBench, Google Code Jam, Xiangtan, etc.)."""
from benchmark.datasets.bigclonebench import BigCloneBenchDataset
from benchmark.datasets.google_codejam import GoogleCodeJamDataset
from benchmark.datasets.xiangtan import XiangtanDataset

__all__ = ['BigCloneBenchDataset', 'GoogleCodeJamDataset', 'XiangtanDataset']