"""Leaderboard system for benchmark results.

Provides persistent tracking and display of benchmark results across runs.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class LeaderboardEntry:
    """A single entry on the leaderboard."""
    engine: str
    dataset: str
    precision: float
    recall: float
    f1: float
    map_score: float = 0.0
    mrr_score: float = 0.0
    ndcg: float = 0.0
    timestamp: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    version: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class Leaderboard:
    """Manages benchmark leaderboard.
    
    Usage:
        lb = Leaderboard("leaderboard.json")
        lb.add_entry(LeaderboardEntry(...))
        lb.save()
    """
    
    def __init__(self, path: str = "reports/leaderboard/leaderboard.json"):
        self.path = Path(path)
        self.entries: List[LeaderboardEntry] = []
        self._load()
    
    def _load(self) -> None:
        """Load existing leaderboard data."""
        if self.path.exists():
            with open(self.path, 'r') as f:
                data = json.load(f)
                self.entries = [LeaderboardEntry(**e) for e in data.get('entries', [])]
    
    def add(self, entry: LeaderboardEntry) -> None:
        """Add a new entry to the leaderboard.
        
        Args:
            entry: LeaderboardEntry to add.
        """
        self.entries.append(entry)
    
    def rank_by(self, metric: str = "f1", n: int = -1) -> List[LeaderboardEntry]:
        """Get entries ranked by a specific metric.
        
        Args:
            metric: Metric to rank by.
            n: Number of top entries (-1 for all).
            
        Returns:
            Sorted list of entries.
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda x: getattr(x, metric, 0),
            reverse=True
        )
        return sorted_entries[:n] if n > 0 else sorted_entries
    
    def best_for_dataset(self, dataset: str, metric: str = "f1") -> Optional[LeaderboardEntry]:
        """Get best entry for a specific dataset.
        
        Args:
            dataset: Dataset name.
            metric: Metric to rank by.
            
        Returns:
            Best LeaderboardEntry or None.
        """
        dataset_entries = [e for e in self.entries if e.dataset == dataset]
        if not dataset_entries:
            return None
        return max(dataset_entries, key=lambda x: getattr(x, metric, 0))
    
    def save(self) -> str:
        """Save leaderboard to file.
        
        Returns:
            Path to saved file.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_updated": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "entries": [asdict(e) for e in self.entries]
        }
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)
        return str(self.path)
    
    def to_report(self, metric: str = "f1") -> Dict[str, Any]:
        """Generate a report from the leaderboard.
        
        Args:
            metric: Metric to rank by.
            
        Returns:
            Report dict.
        """
        ranked = self.rank_by(metric)
        return {
            "metric": metric,
            "total_entries": len(self.entries),
            "top_10": [asdict(e) for e in ranked[:10]],
            "all": [asdict(e) for e in ranked]
        }