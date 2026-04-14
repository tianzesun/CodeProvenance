from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import logging
import datetime
from .fingerprint import DatasetFingerprinter, ContaminationChecker

logger = logging.getLogger(__name__)

class DatasetGovernance:
    """
    Formal governance layer for datasets.
    Ensures reproducibility, integrity, and non-contamination.
    """
    
    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self.fingerprinter = DatasetFingerprinter()
        self.contamination_checker = ContaminationChecker(self.fingerprinter)
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r') as f:
                return json.load(f)
        return {"datasets": {}}

    def _save_metadata(self):
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def register_dataset(self, name: str, path: Path, version: str, description: str):
        """Register a new dataset and check for contamination."""
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
            
        # 1. Fingerprint and check for contamination
        fingerprints = self.fingerprinter.fingerprint_directory(path)
        
        # Add all existing datasets to contamination checker
        for ds_name, ds_info in self.metadata["datasets"].items():
            self.contamination_checker.add_dataset(ds_name, Path(ds_info["path"]))
            
        self.contamination_checker.add_dataset(name, path)
        overlaps = self.contamination_checker.check_overlaps()
        
        # 2. Update metadata
        self.metadata["datasets"][name] = {
            "path": str(path),
            "version": version,
            "description": description,
            "registered_at": datetime.datetime.now().isoformat(),
            "file_count": len(fingerprints),
            "content_hash": self.fingerprinter.compute_content_hash(json.dumps(fingerprints, sort_keys=True))
        }
        
        if overlaps:
            logger.warning(f"Contamination detected for dataset {name}: {overlaps.keys()}")
            self.metadata["datasets"][name]["overlaps"] = overlaps
            
        self._save_metadata()
        return overlaps

    def validate_all(self):
        """Re-validate all registered datasets."""
        for name, info in self.metadata["datasets"].items():
            path = Path(info["path"])
            if not path.exists():
                logger.error(f"Dataset {name} missing at {path}")
                continue
            
            # Re-check fingerprints
            current_f = self.fingerprinter.fingerprint_directory(path)
            current_hash = self.fingerprinter.compute_content_hash(json.dumps(current_f, sort_keys=True))
            
            if current_hash != info["content_hash"]:
                logger.error(f"Dataset {name} content changed! Expected: {info['content_hash']}, Got: {current_hash}")
                info["integrity_fail"] = True
            else:
                info["integrity_fail"] = False
                
        self._save_metadata()
