"""Reproducibility metadata for benchmark results.

Captures git hash, config snapshot, engine versions, dataset versions.
Required for publishable, reproducible research.
"""
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class GitMetadata:
    """Git repository state metadata."""
    commit_hash: str = ""
    branch: str = ""
    is_dirty: bool = False
    remote_url: str = ""
    
    @classmethod
    def capture(cls, repo_path: str = ".") -> "GitMetadata":
        """Capture current git state.
        
        Args:
            repo_path: Path to git repository.
            
        Returns:
            GitMetadata instance.
        """
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            )
            commit_hash = result.stdout.strip()
            
            result = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, check=True
            )
            branch = result.stdout.strip()
            
            result = subprocess.run(
                ["git", "-C", repo_path, "status", "--porcelain"],
                capture_output=True, text=True, check=True
            )
            is_dirty = bool(result.stdout.strip())
            
            result = subprocess.run(
                ["git", "-C", repo_path, "remote", "get-url", "origin"],
                capture_output=True, text=True
            )
            remote_url = result.stdout.strip() if result.returncode == 0 else ""
            
            return cls(
                commit_hash=commit_hash,
                branch=branch,
                is_dirty=is_dirty,
                remote_url=remote_url
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return cls()


@dataclass
class ReproducibilityMetadata:
    """Full reproducibility metadata for a benchmark run."""
    timestamp: str = ""
    git: GitMetadata = field(default_factory=GitMetadata)
    engine_name: str = ""
    engine_version: str = ""
    dataset_name: str = ""
    dataset_version: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    python_version: str = ""
    platform: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    @classmethod
    def capture(
        cls,
        engine_name: str = "",
        engine_version: str = "",
        dataset_name: str = "",
        dataset_version: str = "",
        config: dict[str, Any] | None = None
    ) -> "ReproducibilityMetadata":
        """Capture full reproducibility metadata.
        
        Args:
            engine_name: Detection engine name.
            engine_version: Engine version string.
            dataset_name: Benchmark dataset name.
            dataset_version: Dataset version string.
            config: Configuration snapshot.
            
        Returns:
            ReproducibilityMetadata instance.
        """
        import platform as plat
        import sys
        
        return cls(
            engine_name=engine_name,
            engine_version=engine_version,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            config_snapshot=config or {},
            git=GitMetadata.capture(),
            python_version=sys.version,
            platform=plat.platform()
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Serializable dict.
        """
        return {
            "timestamp": self.timestamp,
            "git": asdict(self.git),
            "engine": {
                "name": self.engine_name,
                "version": self.engine_version
            },
            "dataset": {
                "name": self.dataset_name,
                "version": self.dataset_version
            },
            "config": self.config_snapshot,
            "environment": {
                "python_version": self.python_version,
                "platform": self.platform
            }
        }
    
    def save(self, path: str) -> str:
        """Save metadata to JSON file.
        
        Args:
            path: Output file path.
            
        Returns:
            Path to saved file.
        """
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(output)