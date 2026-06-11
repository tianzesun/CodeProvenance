#!/bin/bash
# IntegrityDesk Test Runner

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

case "${1:-unit}" in
  unit)
    echo "Running fast unit tests..."
    pytest tests/unit/ -m unit -xvs
    ;;

  integration)
    echo "Running integration tests..."
    pytest tests/integration/ -m integration -xvs
    ;;

  all)
    echo "Running all tests (unit + integration)..."
    pytest tests/unit/ tests/integration/ -xvs
    ;;

  slow)
    echo "Running slow tests..."
    pytest tests/ -m slow -xvs
    ;;

  gpu)
    echo "Running GPU tests..."
    pytest tests/ -m gpu -xvs
    ;;

  benchmark)
    echo "Running full benchmark suite (this will take ~4 hours)..."
    python benchmark/benchmark_suite.py
    ;;

  coverage)
    echo "Running test coverage report..."
    pytest tests/unit/ tests/integration/ --cov=src.backend --cov-report=term --cov-report=html
    ;;

  *)
    echo "Usage: ./test.sh [unit|integration|all|slow|gpu|benchmark|coverage]"
    ;;
esac
