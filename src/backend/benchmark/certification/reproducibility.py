"""Reproducibility tracking for certification reports.

Ensures results can be exactly reproduced by tracking:
- Dataset version hash
- Code commit hash
- Configuration hash
- Random seed
- Environment information

This is what makes certification reports auditable and credible.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np


@dataclass(frozen=True)
class ReproducibilityInfo:
    """Complete reproducibility information.

    Attributes:
        dataset_hash: Hash of the dataset used.
        code_commit: Git commit hash of the code.
        config_hash: Hash of configuration used.
        random_seed: Random seed used for reproducibility.
        python_version: Python version.
        numpy_version: NumPy version.
        scipy_version: SciPy version.
        platform: Operating system platform.
        timestamp: Timestamp of evaluation.
        environment: Additional environment information.
    """
    dataset_hash: str = ""
    code_commit: str = ""
    config_hash: str = ""
    random_seed: int = 42
    python_version: str = ""
    numpy_version: str = ""
    scipy_version: str = ""
    platform: str = ""
    timestamp: str = ""
    environment: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "REPRODUCIBILITY STATEMENT",
            "=" * 60,
            f"Dataset Hash: {self.dataset_hash or 'N/A'}",
            f"Code Commit: {self.code_commit or 'N/A'}",
            f"Config Hash: {self.config_hash or 'N/A'}",
            f"Random Seed: {self.random_seed}",
            f"Python Version: {self.python_version}",
            f"NumPy Version: {self.numpy_version}",
            f"SciPy Version: {self.scipy_version}",
            f"Platform: {self.platform}",
            f"Timestamp: {self.timestamp}",
        ]

        if self.environment:
            lines.append("")
            lines.append("Additional Environment:")
            for key, value in self.environment.items():
                lines.append(f"  {key}: {value}")

        lines.append("=" * 60)
        return "\n".join(lines)


def compute_file_hash(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """Compute hash of a file.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of the file hash.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_directory_hash(
    directory: Union[str, Path],
    pattern: str = "*.py",
    algorithm: str = "sha256",
) -> str:
    """Compute hash of all files in a directory.

    Args:
        directory: Path to the directory.
        pattern: Glob pattern for files to include.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of combined hash.
    """
    directory = Path(directory)
    if not directory.exists():
        return ""

    hasher = hashlib.new(algorithm)
    files = sorted(directory.rglob(pattern))

    for file_path in files:
        if file_path.is_file():
            # Include file path in hash for ordering
            hasher.update(str(file_path.relative_to(directory)).encode())
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)

    return hasher.hexdigest()


def compute_config_hash(config: Dict[str, Any], algorithm: str = "sha256") -> str:
    """Compute hash of configuration dictionary.

    Args:
        config: Configuration dictionary.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of config hash.
    """
    # Sort keys for consistent hashing
    config_str = json.dumps(config, sort_keys=True, default=str)
    return hashlib.new(algorithm, config_str.encode()).hexdigest()


def compute_data_hash(
    data: Union[np.ndarray, List[Any]],
    algorithm: str = "sha256",
) -> str:
    """Compute hash of data array or list.

    Args:
        data: Data to hash.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of data hash.
    """
    if isinstance(data, np.ndarray):
        data_bytes = data.tobytes()
    else:
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_bytes = data_str.encode()

    return hashlib.new(algorithm, data_bytes).hexdigest()


def get_git_commit_hash() -> str:
    """Get current git commit hash.

    Returns:
        Git commit hash or empty string if not in a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return ""


def get_git_branch() -> str:
    """Get current git branch name.

    Returns:
        Branch name or empty string if not in a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return ""


def get_package_version(package_name: str) -> str:
    """Get version of an installed package.

    Args:
        package_name: Name of the package.

    Returns:
        Version string or empty string if not installed.
    """
    try:
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except (importlib.metadata.PackageNotFoundError, ImportError):
        pass

    return ""


def collect_environment_info() -> Dict[str, str]:
    """Collect environment information.

    Returns:
        Dictionary with environment details.
    """
    env_info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_implementation": platform.python_implementation(),
    }

    # Add CUDA information if available
    try:
        import torch
        if torch.cuda.is_available():
            env_info["cuda_version"] = torch.version.cuda
            env_info["gpu_count"] = str(torch.cuda.device_count())
            env_info["gpu_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass

    # Add memory information
    try:
        import psutil
        env_info["total_memory_gb"] = f"{psutil.virtual_memory().total / (103**3):.1f}"
    except ImportError:
        pass

    return env_info


def compute_reproducibility_hash(
    dataset_hash: str = "",
    config: Optional[Dict[str, Any]] = None,
    random_seed: int = 42,
) -> str:
    """Compute combined reproducibility hash.

    Args:
        dataset_hash: Hash of the dataset.
        config: Configuration dictionary.
        random_seed: Random seed used.

    Returns:
        Combined hash for reproducibility verification.
    """
    components = []

    if dataset_hash:
        components.append(f"dataset:{dataset_hash}")

    if config:
        config_hash = compute_config_hash(config)
        components.append(f"config:{config_hash}")

    code_commit = get_git_commit_hash()
    if code_commit:
        components.append(f"code:{code_commit}")

    components.append(f"seed:{random_seed}")

    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()


def collect_reproducibility_info(
    dataset_hash: str = "",
    config: Optional[Dict[str, Any]] = None,
    random_seed: int = 42,
    include_code_hash: bool = True,
    code_directory: Optional[Union[str, Path]] = None,
) -> ReproducibilityInfo:
    """Collect complete reproducibility information.

    Args:
        dataset_hash: Hash of the dataset used.
        config: Configuration dictionary.
        random_seed: Random seed used.
        include_code_hash: Whether to include code directory hash.
        code_directory: Path to code directory (defaults to src/).

    Returns:
        ReproducibilityInfo with all tracking information.
    """
    # Get code commit
    code_commit = get_git_commit_hash()

    # Get config hash
    config_hash = ""
    if config:
        config_hash = compute_config_hash(config)

    # Get Python package versions
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    numpy_version = get_package_version("numpy") or np.__version__
    scipy_version = get_package_version("scipy")

    # Get platform
    platform_info = f"{platform.system()} {platform.release()}"

    # Get timestamp
    timestamp = datetime.now().isoformat()

    # Collect environment info
    environment = collect_environment_info()

    # Add git branch if available
    git_branch = get_git_branch()
    if git_branch:
        environment["git_branch"] = git_branch

    # Add code directory hash if requested
    if include_code_hash:
        if code_directory is None:
            code_directory = Path(__file__).parent.parent.parent / "src"
        if Path(code_directory).exists():
            code_hash = compute_directory_hash(code_directory, "*.py")
            if code_hash:
                environment["code_directory_hash"] = code_hash[:16]

    return ReproducibilityInfo(
        dataset_hash=dataset_hash,
        code_commit=code_commit,
        config_hash=config_hash,
        random_seed=random_seed,
        python_version=python_version,
        numpy_version=numpy_version,
        scipy_version=scipy_version,
        platform=platform_info,
        timestamp=timestamp,
        environment=environment,
    )


def verify_reproducibility(
    info: ReproducibilityInfo,
    current_config: Optional[Dict[str, Any]] = None,
    current_seed: int = 42,
) -> Dict[str, Any]:
    """Verify that current environment matches reproducibility info.

    Args:
        info: Original reproducibility information.
        current_config: Current configuration to compare.
        current_seed: Current random seed.

    Returns:
        Dictionary with verification results.
    """
    verification = {
        "matches": True,
        "differences": [],
        "warnings": [],
    }

    # Check code commit
    current_commit = get_git_commit_hash()
    if info.code_commit and current_commit:
        if info.code_commit != current_commit:
            verification["matches"] = False
            verification["differences"].append(
                f"Code commit changed: {info.code_commit[:8]} → {current_commit[:8]}"
            )

    # Check config hash
    if current_config and info.config_hash:
        current_config_hash = compute_config_hash(current_config)
        if info.config_hash != current_config_hash:
            verification["matches"] = False
            verification["differences"].append("Configuration has changed")

    # Check random seed
    if info.random_seed != current_seed:
        verification["warnings"].append(
            f"Random seed changed: {info.random_seed} → {current_seed}"
        )

    # Check Python version
    current_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if info.python_version and current_python != info.python_version:
        verification["warnings"].append(
            f"Python version changed: {info.python_version} → {current_python}"
        )

    return verification