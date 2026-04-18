"""
Proof test: Baseline correction for same-language noise floor.

Tests that the fusion engine correctly distinguishes:
1. Unrelated files → near 0%
2. Plagiarized files (renamed variables) → above threshold
3. Identical files → near 100%
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backend.engines.features.feature_extractor import FeatureExtractor
from src.backend.engines.scoring.fusion_engine import FusionEngine

THRESHOLD = 0.5

# ── Test fixtures ──────────────────────────────────────────────

UNRELATED_A = '''
import numpy as np
import pandas as pd

def calculate_portfolio_returns(weights, returns_matrix):
    weighted_returns = np.dot(weights, returns_matrix)
    return weighted_returns

def sharpe_ratio(returns, risk_free_rate=0.02):
    excess_returns = returns - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns)
'''

UNRELATED_B = '''
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])
'''

PLAGIARISM_A = '''
def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def calculate_sum(data):
    total = 0
    for item in data:
        total += item
    return total

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val
'''

PLAGIARISM_B = '''
def compute_mean(values):
    total = sum(values)
    count = len(values)
    return total / count

def compute_total(values):
    total = 0
    for v in values:
        total += v
    return total

def find_maximum(values):
    max_val = values[0]
    for v in values:
        if v > max_val:
            max_val = v
    return max_val
'''

SAME_ALGO_A = '''
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
'''

SAME_ALGO_B = '''
def sort_array(data):
    n = len(data)
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j] > data[j+1]:
                data[j], data[j+1] = data[j+1], data[j]
    return data

def search_element(data, key):
    left, right = 0, len(data) - 1
    while left <= right:
        mid = (left + right) // 2
        if data[mid] == key:
            return mid
        elif data[mid] < key:
            left = mid + 1
        else:
            right = mid - 1
    return -1
'''


def test_baseline_correction():
    extractor = FeatureExtractor()
    fusion = FusionEngine()

    tests = [
        ("Unrelated files (portfolio vs Flask)", UNRELATED_A, UNRELATED_B, 0.0, 0.2),
        ("Plagiarism (renamed variables)", PLAGIARISM_A, PLAGIARISM_B, 0.5, 1.0),
        ("Same algorithm, different names", SAME_ALGO_A, SAME_ALGO_B, 0.5, 1.0),
        ("Identical files", PLAGIARISM_A, PLAGIARISM_A, 0.8, 1.0),
    ]

    passed = 0
    failed = 0

    print(f"{'Test':<40} {'Score':>7} {'Expected':>15} {'Result':>8}")
    print("-" * 75)

    for name, code_a, code_b, lo, hi in tests:
        features = extractor.extract(code_a, code_b)
        fused = fusion.fuse(features)
        score = fused.final_score
        ok = lo <= score <= hi
        status = "PASS" if ok else "FAIL"
        
        if ok:
            passed += 1
        else:
            failed += 1
        
        print(f"{name:<40} {score:>6.1%}  [{lo:.0%} - {hi:.0%}]  {status:>8}")
        
        # Show engine breakdown
        for ename, escore in sorted(features.as_dict().items(), key=lambda x: -x[1]):
            print(f"    {ename}: {escore:.3f}")

    print("-" * 75)
    print(f"Results: {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    
    success = test_baseline_correction()
    sys.exit(0 if success else 1)
