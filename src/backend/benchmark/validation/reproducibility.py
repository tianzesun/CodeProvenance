"""Reproducibility manifest system for benchmark runs.

Enables exact reproduction of benchmark results by capturing all parameters,
versions, seeds, and checksums needed to recreate a run.
"""
from __future__ import annotations

import json
import hashlib
import platform
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


@dataclass
class DependencyInfo:
    """Information about a single dependency."""
    name: str
    version: str
    location: Optional[str] = None


@dataclass
class ToolVersionInfo:
    """Version information for a plagiarism detection tool."""
    tool_id: str
    version: str
    git_hash: Optional[str] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    memory_limit_mb: int = 4096


@dataclass
class RandomSeedInfo:
    """Random seeds used in the benchmark run."""
    numpy_seed: int = 42
    python_seed: int = 42
    torch_seed: Optional[int] = None
    tensorflow_seed: Optional[int] = None
    tool_specific_seeds: Dict[str, int] = field(default_factory=dict)


@dataclass
class DatasetChecksum:
    """Checksum information for a dataset."""
    dataset_id: str
    sha256_hash: str
    file_count: int
    total_size_bytes: int
    pair_count: int


@dataclass
class BenchmarkParameters:
    """Parameters used in the benchmark run."""
    threshold: float = 0.5
    timeout_seconds: int = 300
    memory_limit_mb: int = 4096
    batch_size: int = 32
    embedding_device: str = "auto"  # "auto", "cuda", "cpu"
    embedding_batch_size: int = 32
    max_workers: int = 4
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReproducibilityManifest:
    """Complete manifest for reproducing a benchmark run.

    This manifest captures all information needed to exactly reproduce
    a benchmark run, including versions, seeds, parameters, and checksums.
    """

    # Run identification
    run_id: str
    timestamp: str  # ISO-8601 format
    description: str = ""

    # Environment
    codeprovenance_version: str = ""  # Git hash or version tag
    python_version: str = ""
    platform_system: str = ""
    platform_release: str = ""

    # Dependencies
    dependencies: List[DependencyInfo] = field(default_factory=list)

    # Tool versions
    tool_versions: List[ToolVersionInfo] = field(default_factory=list)

    # Random seeds
    random_seeds: RandomSeedInfo = field(default_factory=RandomSeedInfo)

    # Dataset information
    dataset_checksums: List[DatasetChecksum] = field(default_factory=list)

    # Benchmark parameters
    parameters: BenchmarkParameters = field(default_factory=BenchmarkParameters)

    # Results location
    results_path: str = ""
    results_checksum: Optional[str] = None

    # Metadata
    created_by: str = "benchmark-system"
    notes: str = ""

    @classmethod
    def create_current(
        cls,
        run_id: str,
        description: str = "",
        codeprovenance_version: str = "",
    ) -> ReproducibilityManifest:
        """Create a manifest with current environment information.

        Args:
            run_id: Unique identifier for this run
            description: Human-readable description of the run
            codeprovenance_version: Git hash or version tag

        Returns:
            ReproducibilityManifest with current environment info
        """
        return cls(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            description=description,
            codeprovenance_version=codeprovenance_version,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            platform_system=platform.system(),
            platform_release=platform.release(),
        )

    def add_dependency(
        self,
        name: str,
        version: str,
        location: Optional[str] = None,
    ) -> None:
        """Add a dependency to the manifest.

        Args:
            name: Package name
            version: Package version
            location: Optional installation location
        """
        self.dependencies.append(
            DependencyInfo(name=name, version=version, location=location)
        )

    def add_tool_version(
        self,
        tool_id: str,
        version: str,
        git_hash: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
        memory_limit_mb: int = 4096,
    ) -> None:
        """Add tool version information.

        Args:
            tool_id: Tool identifier
            version: Tool version
            git_hash: Optional git commit hash
            configuration: Optional tool configuration dict
            timeout_seconds: Timeout for tool execution
            memory_limit_mb: Memory limit in MB
        """
        self.tool_versions.append(
            ToolVersionInfo(
                tool_id=tool_id,
                version=version,
                git_hash=git_hash,
                configuration=configuration or {},
                timeout_seconds=timeout_seconds,
                memory_limit_mb=memory_limit_mb,
            )
        )

    def add_dataset_checksum(
        self,
        dataset_id: str,
        sha256_hash: str,
        file_count: int,
        total_size_bytes: int,
        pair_count: int,
    ) -> None:
        """Add dataset checksum information.

        Args:
            dataset_id: Dataset identifier
            sha256_hash: SHA256 hash of dataset
            file_count: Number of files in dataset
            total_size_bytes: Total size in bytes
            pair_count: Number of code pairs
        """
        self.dataset_checksums.append(
            DatasetChecksum(
                dataset_id=dataset_id,
                sha256_hash=sha256_hash,
                file_count=file_count,
                total_size_bytes=total_size_bytes,
                pair_count=pair_count,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary.

        Returns:
            Dictionary representation of manifest
        """
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "description": self.description,
            "environment": {
                "codeprovenance_version": self.codeprovenance_version,
                "python_version": self.python_version,
                "platform": {
                    "system": self.platform_system,
                    "release": self.platform_release,
                },
            },
            "dependencies": [asdict(d) for d in self.dependencies],
            "tool_versions": [asdict(t) for t in self.tool_versions],
            "random_seeds": asdict(self.random_seeds),
            "dataset_checksums": [asdict(d) for d in self.dataset_checksums],
            "parameters": asdict(self.parameters),
            "results": {
                "path": self.results_path,
                "checksum": self.results_checksum,
            },
            "metadata": {
                "created_by": self.created_by,
                "notes": self.notes,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert manifest to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str | Path) -> None:
        """Save manifest to JSON file.

        Args:
            path: File path to save to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str | Path) -> ReproducibilityManifest:
        """Load manifest from JSON file.

        Args:
            path: File path to load from

        Returns:
            ReproducibilityManifest instance
        """
        path = Path(path)
        with open(path, "r") as f:
            data = json.load(f)

        # Reconstruct manifest from dict
        manifest = cls(
            run_id=data["run_id"],
            timestamp=data["timestamp"],
            description=data.get("description", ""),
            codeprovenance_version=data["environment"]["codeprovenance_version"],
            python_version=data["environment"]["python_version"],
            platform_system=data["environment"]["platform"]["system"],
            platform_release=data["environment"]["platform"]["release"],
        )

        # Add dependencies
        for dep in data.get("dependencies", []):
            manifest.add_dependency(
                name=dep["name"],
                version=dep["version"],
                location=dep.get("location"),
            )

        # Add tool versions
        for tool in data.get("tool_versions", []):
            manifest.add_tool_version(
                tool_id=tool["tool_id"],
                version=tool["version"],
                git_hash=tool.get("git_hash"),
                configuration=tool.get("configuration"),
                timeout_seconds=tool.get("timeout_seconds", 300),
                memory_limit_mb=tool.get("memory_limit_mb", 4096),
            )

        # Set random seeds
        seeds = data.get("random_seeds", {})
        manifest.random_seeds = RandomSeedInfo(
            numpy_seed=seeds.get("numpy_seed", 42),
            python_seed=seeds.get("python_seed", 42),
            torch_seed=seeds.get("torch_seed"),
            tensorflow_seed=seeds.get("tensorflow_seed"),
            tool_specific_seeds=seeds.get("tool_specific_seeds", {}),
        )

        # Add dataset checksums
        for dataset in data.get("dataset_checksums", []):
            manifest.add_dataset_checksum(
                dataset_id=dataset["dataset_id"],
                sha256_hash=dataset["sha256_hash"],
                file_count=dataset["file_count"],
                total_size_bytes=dataset["total_size_bytes"],
                pair_count=dataset["pair_count"],
            )

        # Set parameters
        params = data.get("parameters", {})
        manifest.parameters = BenchmarkParameters(
            threshold=params.get("threshold", 0.5),
            timeout_seconds=params.get("timeout_seconds", 300),
            memory_limit_mb=params.get("memory_limit_mb", 4096),
            batch_size=params.get("batch_size", 32),
            embedding_device=params.get("embedding_device", "auto"),
            embedding_batch_size=params.get("embedding_batch_size", 32),
            max_workers=params.get("max_workers", 4),
            custom_params=params.get("custom_params", {}),
        )

        # Set results info
        results = data.get("results", {})
        manifest.results_path = results.get("path", "")
        manifest.results_checksum = results.get("checksum")

        # Set metadata
        metadata = data.get("metadata", {})
        manifest.created_by = metadata.get("created_by", "benchmark-system")
        manifest.notes = metadata.get("notes", "")

        return manifest


def calculate_file_checksum(file_path: str | Path, algorithm: str = "sha256") -> str:
    """Calculate checksum of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm ("sha256", "md5", etc.)

    Returns:
        Hex digest of file hash
    """
    file_path = Path(file_path)
    hash_obj = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def calculate_directory_checksum(
    dir_path: str | Path, algorithm: str = "sha256"
) -> str:
    """Calculate checksum of all files in a directory.

    Args:
        dir_path: Path to directory
        algorithm: Hash algorithm ("sha256", "md5", etc.)

    Returns:
        Hex digest of combined hash
    """
    dir_path = Path(dir_path)
    hash_obj = hashlib.new(algorithm)

    # Sort files for consistent ordering
    for file_path in sorted(dir_path.rglob("*")):
        if file_path.is_file():
            file_hash = calculate_file_checksum(file_path, algorithm)
            hash_obj.update(file_hash.encode())

    return hash_obj.hexdigest()
