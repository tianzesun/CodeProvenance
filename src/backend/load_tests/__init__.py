"""Load testing configuration and scripts for IntegrityDesk.

This module provides load testing capabilities for:
1. API endpoint performance testing
2. Plagiarism detection pipeline throughput
3. Concurrent user simulation
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""

    base_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"
    users: int = 100
    spawn_rate: int = 10
    run_time: str = "1m"
    hatch_rate: int = 1
    thresholds: dict[str, str] = None

    def __post_init__(self):
        if self.thresholds is None:
            self.thresholds = {
                "p95_response_time": "500ms",
                "p99_response_time": "1000ms",
                "error_rate": "1%",
                "max_requests_per_second": "50",
            }


class PlagiarismDetectionLoadTest:
    """Load test scenarios for plagiarism detection API."""

    def __init__(self, config: LoadTestConfig):
        self.config = config

    def get_test_payload(self, scenario: str = "small") -> dict[str, Any]:
        """Generate test payload for different scenarios."""

        code_samples = {
            "small": """
def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
""",
            "medium": """
class TreeNode:
    def __init__(self, value=0, left=None, right=None):
        self.val = value
        self.left = left
        self.right = right

def max_path_sum(root):
    if not root:
        return 0
    left_max = max_path_sum(root.left)
    right_max = max_path_sum(root.right)
    return max(left_max, right_max) + root.val
""",
            "large": """
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

def train_model(data_path):
    df = pd.read_csv(data_path)
    X = df.drop('target', axis=1)
    y = df['target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X_train, y_train)
    return model.score(X_test, y_test)
""",
        }

        code = code_samples.get(scenario, code_samples["small"])

        return {
            "code_a": code,
            "code_b": code.replace("def ", "def_") if scenario == "small" else code,
            "domain": "code",
        }


# Locust test script
LOCUST_SCRIPT = '''
from locust import HttpUser, task, between, events
import json
import random

class PlagiarismDetectionUser(HttpUser):
    wait_time = between(1, 3)
    base_url = "http://localhost:8000"
    
    def on_start(self):
        """Initialize user session"""
        pass
    
    @task(50)
    def check_similarity_small(self):
        """Check similarity for small code samples"""
        code = \'\'\'
def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
\'\'\'
        payload = {
            "code_a": code,
            "code_b": code.replace("def ", "def_"),
            "domain": "code"
        }
        with self.client.post("/api/v1/similarity/check", 
                              json=payload, 
                              catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "verdict" in data:
                    response.success()
                else:
                    response.failure("Missing verdict in response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(30)
    def check_similarity_medium(self):
        """Check similarity for medium code samples"""
        code = \'\'\'
class TreeNode:
    def __init__(self, value=0, left=None, right=None):
        self.val = value
        self.left = left
        self.right = right

def max_path_sum(root):
    if not root:
        return 0
    return max(max_path_sum(root.left), max_path_sum(root.right)) + root.val
\'\'\'
        payload = {
            "code_a": code,
            "code_b": code,
            "domain": "code"
        }
        self.client.post("/api/v1/similarity/check", json=payload)
    
    @task(10)
    def get_results(self):
        """Fetch recent results"""
        self.client.get("/api/v1/results?limit=10")
    
    @task(5)
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")

class AdminUser(HttpUser):
    wait_time = between(5, 10)
    
    @task
    def get_settings(self):
        self.client.get("/api/v1/settings")
    
    @task
    def get_users(self):
        self.client.get("/api/v1/users")
'''


# k6 test script
K6_SCRIPT = r"""
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const similarityTrend = new Trend("similarity_check_duration");
const errorCounter = new Counter("errors");

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "1m", target: 50 },
    { duration: "1m", target: 100 },
    { duration: "30s", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    "http_req_duration": ["p(95)<500", "p(99)<1000"],
    "errors": ["count<100"],
    "http_req_failed": ["rate<0.01"],
  },
};

export default function () {
  const code = \`def find_max(numbers):
    if not numbers:
      return None
    max_val = numbers[0]
    for num in numbers:
      if num > max_val:
        max_val = num
    return max_val\`;

  const payload = JSON.stringify({
    code_a: code,
    code_b: code.replace("def ", "def_"),
    domain: "code",
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const res = http.post("http://localhost:8000/api/v1/similarity/check", payload, params);
  
  similarityTrend.add(res.timings.duration);
  
  check(res, {
    "status is 200": (r) => r.status === 200,
    "has verdict": (r) => r.json() && "verdict" in r.json(),
  }) || errorCounter.add(1);

  sleep(1);
}
"""


def create_locustfile(output_path: str) -> None:
    """Create locust test file."""
    with open(output_path, "w") as f:
        f.write(LOCUST_SCRIPT)


def create_k6_script(output_path: str) -> None:
    """Create k6 test script."""
    with open(output_path, "w") as f:
        f.write(K6_SCRIPT)


def create_load_test_config(output_path: str) -> None:
    """Create load test configuration file."""
    config = {
        "base_url": "http://localhost:8000",
        "api_prefix": "/api/v1",
        "load_test": {
            "users": 100,
            "spawn_rate": 10,
            "run_time": "1m",
            "hatch_rate": 1,
        },
        "thresholds": {
            "p95_response_time": "500ms",
            "p99_response_time": "1000ms",
            "error_rate": "1%",
            "max_requests_per_second": "50",
        },
        "scenarios": [
            {
                "name": "small_files",
                "weight": 50,
                "description": "Small code file similarity checks",
            },
            {
                "name": "medium_files",
                "weight": 30,
                "description": "Medium code file similarity checks",
            },
            {
                "name": "results_fetch",
                "weight": 10,
                "description": "Fetch recent results",
            },
            {
                "name": "health_check",
                "weight": 5,
                "description": "Health check endpoint",
            },
        ],
    }

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    import os

    tests_dir = os.path.join(os.path.dirname(__file__), "load_tests")
    os.makedirs(tests_dir, exist_ok=True)

    create_locustfile(os.path.join(tests_dir, "locustfile.py"))
    create_k6_script(os.path.join(tests_dir, "load_test.js"))
    create_load_test_config(os.path.join(tests_dir, "config.json"))

    print(f"Load test files created in {tests_dir}")
