"""Reproducibility Module - Scientific integrity enforcement.

This module provides:
1. Reproducibility hashing (dataset + code + config)
2. Golden dataset locking (versioned, immutable datasets)
3. Run fingerprinting (unique identifier for each run)

Every run must produce a reproducibility hash.
If anything changes → result is different run.
No ambiguity.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .versioning import VersionManifest, create_version_manifest


@dataclass(frozen=True)
class ReproducibilityHash:
    """Reproducibility hash for a run.
    
    Attributes:
        dataset_hash: Hash of the dataset.
        code_version: Git commit hash or code version.
        config_hash: Hash of configuration.
        combined_hash: Combined hash of all components.
        timestamp: ISO timestamp of creation.
    """
    dataset_hash: str
    code_version: str
    config_hash: str
    combined_hash: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dataset_hash": self.dataset_hash,
            "code_version": self.code_version,
            "config_hash": self.config_hash,
            "combined_hash": self.combined_hash,
            "timestamp": self.timestamp,
        }
    
    def save(self, path: Path) -> None:
        """Save hash to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> ReproducibilityHash:
        """Load hash from file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


@dataclass
class GoldenDataset:
    """Golden dataset - versioned and immutable.
    
    Attributes:
        name: Dataset name.
        version: Version string.
        path: Path to dataset.
        hash: Hash of dataset contents.
        created_at: ISO timestamp of creation.
        is_locked: Whether dataset is locked (immutable).
    """
    name: str
    version: str
    path: Path
    hash: str
    created_at: str
    is_locked: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "path": str(self.path),
            "hash": self.hash,
            "created_at": self.created_at,
            "is_locked": self.is_locked,
        }
    
    def save(self, path: Path) -> None:
        """Save dataset metadata to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> GoldenDataset:
        """Load dataset metadata from file."""
        with open(path) as f:
            data = json.load(f)
        data["path"] = Path(data["path"])
        return cls(**data)
    
    def verify(self) -> bool:
        """Verify dataset integrity."""
        if not self.path.exists():
            return False
        computed_hash = compute_directory_hash(self.path)
        return computed_hash == self.hash


def compute_file_hash(path: Path) -> str:
    """Compute hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_directory_hash(path: Path) -> str:
    """Compute hash of a directory."""
    hasher = hashlib.sha256()
    files = sorted(path.rglob("*"))
    for file_path in files:
        if file_path.is_file():
            rel_path = file_path.relative_to(path)
            hasher.update(str(rel_path).encode())
            try:
                file_hash = compute_file_hash(file_path)
                hasher.update(file_hash.encode())
            except (PermissionError, OSError):
                # Skip files that can't be read (e.g., permission denied)
                # Use a placeholder hash for unreadable files
                hasher.update(b"UNREADABLE")
    return hasher.hexdigest()


def compute_config_hash(config: Dict[str, Any]) -> str:
    """Compute hash of configuration."""
    config_json = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_json.encode()).hexdigest()


def compute_reproducibility_hash(
    dataset_path: Path,
    code_version: str,
    config: Dict[str, Any],
) -> ReproducibilityHash:
    """Compute reproducibility hash."""
    dataset_hash = compute_directory_hash(dataset_path)
    config_hash = compute_config_hash(config)
    combined = f"{dataset_hash}:{code_version}:{config_hash}"
    combined_hash = hashlib.sha256(combined.encode()).hexdigest()
    return ReproducibilityHash(
        dataset_hash=dataset_hash,
        code_version=code_version,
        config_hash=config_hash,
        combined_hash=combined_hash,
        timestamp=datetime.now().isoformat(),
    )


def create_golden_dataset(
    name: str,
    version: str,
    path: Path,
) -> GoldenDataset:
    """Create a golden dataset."""
    if not path.exists():
        raise ValueError(f"Dataset path does not exist: {path}")
    dataset_hash = compute_directory_hash(path)
    return GoldenDataset(
        name=name,
        version=version,
        path=path,
        hash=dataset_hash,
        created_at=datetime.now().isoformat(),
        is_locked=True,
    )


def verify_golden_dataset(dataset: GoldenDataset) -> bool:
    """Verify a golden dataset."""
    if not dataset.is_locked:
        return False
    return dataset.verify()


@dataclass
class RunFingerprint:
    """Unique fingerprint for a benchmark run.
    
    Attributes:
        run_id: Unique run identifier.
        reproducibility_hash: Reproducibility hash.
        version_manifest: Version manifest.
        created_at: ISO timestamp of creation.
    """
    run_id: str
    reproducibility_hash: ReproducibilityHash
    version_manifest: VersionManifest
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "reproducibility_hash": self.reproducibility_hash.to_dict(),
            "version_manifest": self.version_manifest.to_dict(),
            "created_at": self.created_at,
        }
    
    def save(self, path: Path) -> None:
        """Save fingerprint to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> RunFingerprint:
        """Load fingerprint from file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            run_id=data["run_id"],
            reproducibility_hash=ReproducibilityHash(**data["reproducibility_hash"]),
            version_manifest=VersionManifest.load_from_dict(data["version_manifest"]),
            created_at=data["created_at"],
        )


def create_run_fingerprint(
    run_id: str,
    dataset_path: Path,
    code_version: str,
    config: Dict[str, Any],
) -> RunFingerprint:
    """Create a run fingerprint."""
    reproducibility_hash = compute_reproducibility_hash(
        dataset_path=dataset_path,
        code_version=code_version,
        config=config,
    )
    version_manifest = create_version_manifest(run_id=run_id)
    return RunFingerprint(
        run_id=run_id,
        reproducibility_hash=reproducibility_hash,
        version_manifest=version_manifest,
        created_at=datetime.now().isoformat(),
    )


def verify_run_fingerprint(fingerprint: RunFingerprint) -> List[str]:
    """Verify a run fingerprint."""
    from .versioning import validate_manifest
    return validate_manifest(fingerprint.version_manifest)
