import hashlib
from pathlib import Path
from typing import Set, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class DatasetFingerprinter:
    """
    Handles dataset fingerprinting to prevent contamination and leakage.
    Provides methods to generate unique identifiers for code samples and 
    check for overlaps between datasets.
    """
    
    def __init__(self):
        self._fingerprints: Dict[str, str] = {} # filename -> hash

    def compute_content_hash(self, content: str) -> str:
        """
        Compute a stable SHA-256 hash of the code content.
        Normalizes whitespace to ensure consistency.
        """
        # Simple normalization: strip and collapse whitespace
        normalized = " ".join(content.split())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def fingerprint_directory(self, directory_path: Path) -> Dict[str, str]:
        """
        Fingerprints all files in a directory.
        Returns a mapping of relative path to content hash.
        """
        fingerprints = {}
        for file_path in directory_path.rglob('*'):
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        rel_path = str(file_path.relative_to(directory_path))
                        fingerprints[rel_path] = self.compute_content_hash(content)
                except Exception as e:
                    logger.error(f"Failed to fingerprint {file_path}: {e}")
        return fingerprints

class ContaminationChecker:
    """
    Checks for overlaps and leakage between datasets.
    """
    
    def __init__(self, fingerprinter: Optional[DatasetFingerprinter] = None):
        self.fingerprinter = fingerprinter or DatasetFingerprinter()
        self.dataset_fingerprints: Dict[str, Dict[str, str]] = {}

    def add_dataset(self, name: str, directory_path: Path):
        """Adds a dataset for overlap checking."""
        self.dataset_fingerprints[name] = self.fingerprinter.fingerprint_directory(directory_path)

    def check_overlaps(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Checks for identical files across all added datasets.
        Returns a report of overlaps.
        """
        overlaps = {}
        dataset_names = list(self.dataset_fingerprints.keys())
        
        for i in range(len(dataset_names)):
            for j in range(i + 1, len(dataset_names)):
                ds1_name = dataset_names[i]
                ds2_name = dataset_names[j]
                ds1_f = self.dataset_fingerprints[ds1_name]
                ds2_f = self.dataset_fingerprints[ds2_name]
                
                # Find identical hashes
                ds1_hashes = set(ds1_f.values())
                ds2_hashes = set(ds2_f.values())
                common_hashes = ds1_hashes.intersection(ds2_hashes)
                
                if common_hashes:
                    key = f"{ds1_name} <-> {ds2_name}"
                    overlaps[key] = []
                    for h in common_hashes:
                        files1 = [f for f, hv in ds1_f.items() if hv == h]
                        files2 = [f for f, hv in ds2_f.items() if hv == h]
                        overlaps[key].append({
                            "hash": h,
                            "ds1_files": files1,
                            "ds2_files": files2
                        })
        return overlaps

    def get_deduplicated_dataset(self, dataset_path: Path, reference_datasets: List[Path]) -> List[Path]:
        """
        Returns a list of files in dataset_path that do NOT exist in any of the reference_datasets.
        """
        ref_hashes = set()
        for ref_path in reference_datasets:
            ref_f = self.fingerprinter.fingerprint_directory(ref_path)
            ref_hashes.update(ref_f.values())
            
        current_f = self.fingerprinter.fingerprint_directory(dataset_path)
        unique_files = []
        for rel_path, h in current_f.items():
            if h not in ref_hashes:
                unique_files.append(dataset_path / rel_path)
        
        return unique_files
