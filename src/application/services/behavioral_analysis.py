import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import datetime

@dataclass
class KeystrokeEvent:
    timestamp: float  # Seconds since start
    event_type: str   # 'keydown', 'keyup', 'paste'
    key: str          # The key pressed
    position: int     # Character position in the editor

class KeystrokeAnalysisService:
    """
    Behavioral Analysis Service.
    Analyzes code composition patterns (typing speed, bursts, pastes) 
    to detect 'unnatural' authorship and copy-paste behavior.
    """
    
    def __init__(self, threshold_burst_speed: float = 500.0):
        # Characters per minute threshold for 'impossible' typing speed
        self.threshold_burst_speed = threshold_burst_speed

    def analyze_session(self, events: List[KeystrokeEvent]) -> Dict[str, Any]:
        """
        Analyze a sequence of keystroke events for anomalies.
        """
        if not events:
            return {"score": 0.0, "anomalies": []}

        anomalies = []
        total_chars = sum(1 for e in events if e.event_type == 'keydown' and len(e.key) == 1)
        duration_sec = events[-1].timestamp - events[0].timestamp
        
        # 1. Detect Large Pastes
        pastes = [e for e in events if e.event_type == 'paste']
        if pastes:
            for p in pastes:
                anomalies.append({
                    "type": "LARGE_PASTE",
                    "timestamp": p.timestamp,
                    "description": f"A large block of text was pasted at position {p.position}."
                })

        # 2. Detect 'Impossible' Typing Bursts
        # Calculate typing speed in windows
        window_size = 5 # seconds
        for i in range(len(events) - 1):
            window_events = [e for e in events if i <= e.timestamp < i + window_size]
            char_count = sum(1 for e in window_events if e.event_type == 'keydown' and len(e.key) == 1)
            cpm = (char_count / window_size) * 60
            
            if cpm > self.threshold_burst_speed:
                anomalies.append({
                    "type": "TYPING_BURST",
                    "timestamp": events[i].timestamp,
                    "cpm": round(cpm, 2),
                    "description": f"Unnatural typing speed detected: {round(cpm, 2)} CPM."
                })

        # 3. Behavioral Identity (Fingerprinting)
        # Average dwell time (keydown to keyup) and flight time (keyup to next keydown)
        dwell_times = []
        flight_times = []
        # Simplified: in a real system, you'd match keydown/keyup pairs
        
        behavioral_score = len(anomalies) / (total_chars / 100 + 1)
        
        return {
            "behavioral_anomaly_score": min(1.0, behavioral_score),
            "anomalies": anomalies,
            "total_chars": total_chars,
            "duration_minutes": round(duration_sec / 60, 2),
            "is_suspicious": behavioral_score > 0.5
        }
