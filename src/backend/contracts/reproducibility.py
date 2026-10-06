"""Reproducibility Module - Scientific integrity enforcement.

1. Reproducibility hashing (dataset + code + config)
2. Golden dataset locking (versioned, immutable datasets)
3. Run fingerprinting

If anything changes -> result is a different run.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import hashlib
import json
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._io import read_json, utc_now_iso, write_json_atomic
from .versioning import VersionManifest, create_version_manifest, validate_manifest

_CHUNK_SIZE = 1024 * 1024


def _lp(b: bytes) -> bytes:
    """Length-prefix so concatenated fields can never be ambiguous."""
    return len(b).to_bytes(8, "big") + b


# --- hashing primitives -----------------------------------------------------------


def compute_file_hash(path: Path) -> str:
    """SHA-256 of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_directory_hash(
    path: Path,
    *,
    exclude: Iterable[str] = (),
    skip_unreadable: bool = False,
) -> str:
    """SHA-256 over relative paths + file contents.

    Args:
        path: Directory (or a single file) to hash.
        exclude: fnmatch patterns on POSIX-style relative paths, e.g. ``"*.pyc"``.
        skip_unreadable: If False (default) unreadable files raise. Silently
            substituting a placeholder let content changes go undetected.

    Raises:
        FileNotFoundError: If ``path`` doesn't exist.
        OSError: If a file can't be read and ``skip_unreadable`` is False.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if path.is_file():  # previously hashed to the constant "empty directory" digest
        return compute_file_hash(path)

    patterns = tuple(exclude)
    entries: list[tuple[str, Path]] = []
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        # POSIX separators + NFC => same hash on Linux, Windows and macOS.
        rel = unicodedata.normalize("NFC", p.relative_to(path).as_posix())
        if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            continue
        entries.append((rel, p))
    entries.sort(key=lambda e: e[0])  # sort by string, not OS-specific Path ordering

    hasher = hashlib.sha256()
    for rel, p in entries:
        hasher.update(_lp(rel.encode("utf-8")))
        try:
            digest = compute_file_hash(p)
        except OSError:
            if not skip_unreadable:
                raise
            digest = "UNREADABLE"
        hasher.update(_lp(digest.encode("ascii")))
    return hasher.hexdigest()


def _canonical_default(o: Any) -> Any:
    if isinstance(o, Path):
        return o.as_posix()
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=repr)
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    raise TypeError(
        f"Config value of type {type(o).__name__} is not hashable deterministically"
    )


def compute_config_hash(config: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON. Rejects NaN/Infinity and unknown object types
    rather than hashing a non-deterministic repr."""
    config_json = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_canonical_default,
    )
    return hashlib.sha256(config_json.encode("utf-8")).hexdigest()


def _combine(dataset_hash: str, code_version: str, config_hash: str) -> str:
    # JSON list, not "a:b:c": a ':' inside code_version could forge collisions.
    payload = json.dumps([dataset_hash, code_version, config_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- reproducibility hash ---------------------------------------------------------


@dataclass(frozen=True)
class ReproducibilityHash:
    """Reproducibility hash for a run."""

    dataset_hash: str
    code_version: str
    config_hash: str
    combined_hash: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())

    @classmethod
    def load(cls, path: Path) -> ReproducibilityHash:
        return cls(**read_json(path))


def compute_reproducibility_hash(
    dataset_path: Path,
    code_version: str,
    config: dict[str, Any],
    *,
    exclude: Iterable[str] = (),
) -> ReproducibilityHash:
    dataset_hash = compute_directory_hash(dataset_path, exclude=exclude)
    config_hash = compute_config_hash(config)
    return ReproducibilityHash(
        dataset_hash=dataset_hash,
        code_version=code_version,
        config_hash=config_hash,
        combined_hash=_combine(dataset_hash, code_version, config_hash),
        timestamp=utc_now_iso(),
    )


# --- golden dataset ---------------------------------------------------------------


@dataclass(frozen=True)  # frozen: "immutable" was only a docstring before
class GoldenDataset:
    """Golden dataset - versioned and immutable.

    ``exclude`` is stored so verification re-hashes exactly what creation hashed.
    """

    name: str
    version: str
    path: Path
    hash: str
    created_at: str
    is_locked: bool = True
    exclude: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "path": str(self.path),
            "hash": self.hash,
            "created_at": self.created_at,
            "is_locked": self.is_locked,
            "exclude": list(self.exclude),
        }

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())

    @classmethod
    def load(cls, path: Path) -> GoldenDataset:
        data = read_json(path)
        data["path"] = Path(data["path"])
        data["exclude"] = tuple(data.get("exclude", ()))  # old files lack this key
        return cls(**data)

    def verify(self) -> bool:
        """True if the dataset on disk still matches the recorded hash."""
        try:
            return compute_directory_hash(self.path, exclude=self.exclude) == self.hash
        except OSError:
            return False


def create_golden_dataset(
    name: str,
    version: str,
    path: Path,
    *,
    exclude: Iterable[str] = (),
) -> GoldenDataset:
    path = Path(path)
    if not path.exists():
        raise ValueError(f"Dataset path does not exist: {path}")
    exclude_t = tuple(exclude)
    return GoldenDataset(
        name=name,
        version=version,
        path=path,
        hash=compute_directory_hash(path, exclude=exclude_t),
        created_at=utc_now_iso(),
        is_locked=True,
        exclude=exclude_t,
    )


def verify_golden_dataset(dataset: GoldenDataset) -> bool:
    if not dataset.is_locked:
        return False
    return dataset.verify()


# --- run fingerprint --------------------------------------------------------------


@dataclass
class RunFingerprint:
    """Fingerprint for a benchmark run."""

    run_id: str
    reproducibility_hash: ReproducibilityHash
    version_manifest: VersionManifest
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "reproducibility_hash": self.reproducibility_hash.to_dict(),
            "version_manifest": self.version_manifest.to_dict(),
            "created_at": self.created_at,
        }

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())

    @classmethod
    def load(cls, path: Path) -> RunFingerprint:
        data = read_json(path)
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
    config: dict[str, Any],
    *,
    exclude: Iterable[str] = (),
) -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        reproducibility_hash=compute_reproducibility_hash(
            dataset_path, code_version, config, exclude=exclude
        ),
        version_manifest=create_version_manifest(run_id=run_id),
        created_at=utc_now_iso(),
    )


def verify_run_fingerprint(
    fingerprint: RunFingerprint,
    *,
    dataset_path: Path | None = None,
    code_version: str | None = None,
    config: dict[str, Any] | None = None,
    exclude: Iterable[str] = (),
) -> list[str]:
    """Verify a fingerprint; returns error messages (empty if valid).

    Always checks the schema manifest. Also re-checks dataset / code version /
    config when supplied (previously only the manifest was checked, so a
    changed dataset still "verified").
    """
    errors = validate_manifest(fingerprint.version_manifest)
    rh = fingerprint.reproducibility_hash

    if dataset_path is not None:
        try:
            actual = compute_directory_hash(dataset_path, exclude=exclude)
        except OSError as e:
            errors.append(f"Dataset unreadable: {e}")
        else:
            if actual != rh.dataset_hash:
                errors.append(
                    f"Dataset hash mismatch: expected {rh.dataset_hash}, got {actual}"
                )
    if code_version is not None and code_version != rh.code_version:
        errors.append(
            f"Code version mismatch: expected {rh.code_version}, got {code_version}"
        )
    if config is not None:
        actual_cfg = compute_config_hash(config)
        if actual_cfg != rh.config_hash:
            errors.append(
                f"Config hash mismatch: expected {rh.config_hash}, got {actual_cfg}"
            )

    if _combine(rh.dataset_hash, rh.code_version, rh.config_hash) != rh.combined_hash:
        errors.append(
            "combined_hash does not match its components (record tampered or corrupt)"
        )
    return errors
