#!/bin/bash
"""
Benchmark Runner Quick Start Script

Usage:
  ./run_benchmarks.sh                    # Run all available benchmarks
  ./run_benchmarks.sh synthetic          # Run only synthetic dataset
  ./run_benchmarks.sh bigclonebench moss # Run BigCloneBench with MOSS algorithm
"""

set -e

# Activate virtual environment
source venv/bin/activate

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 IntegrityDesk Comprehensive Benchmark Suite${NC}"
echo -e "${BLUE}=================================================${NC}"

# Check if datasets exist
echo -e "\n${YELLOW}📊 Checking available datasets...${NC}"
datasets=(
    "data/datasets/bigclonebench:BigCloneBench"
    "data/datasets/poj104:POJ-104"
    "data/datasets/synthetic:Synthetic"
    "data/datasets/kaggle_student_code:Kaggle Student"
    "data/datasets/IR-Plag-Dataset:IR-Plag"
    "data/big_datasets/AI-SOCO:AI-SOCO"
    "data/datasets/MGTBench:MGTBench"
    "data/datasets/AICD-Bench:AICD-Bench"
)

available_datasets=()
for dataset_info in "${datasets[@]}"; do
    path="${dataset_info%%:*}"
    name="${dataset_info##*:}"

    if [ -d "$path" ]; then
        echo -e "  ✅ $name"
        available_datasets+=("$name")
    else
        echo -e "  ❌ $name (not found)"
    fi
done

echo -e "\n${GREEN}Available datasets: ${#available_datasets[@]}${NC}"

# Determine which datasets to run
if [ $# -eq 0 ]; then
    echo -e "\n${YELLOW}🏃 Running benchmarks on ALL available datasets...${NC}"
    python benchmark_runner.py
elif [ $# -eq 1 ]; then
    echo -e "\n${YELLOW}🏃 Running benchmarks on $1 dataset...${NC}"
    # For single dataset, we'd need to modify the runner
    echo "Single dataset mode not implemented yet. Run all with: ./run_benchmarks.sh"
else
    echo -e "\n${YELLOW}🏃 Running $2 algorithm on $1 dataset...${NC}"
    # For specific algorithm/dataset, we'd need to modify the runner
    echo "Specific mode not implemented yet. Run all with: ./run_benchmarks.sh"
fi

echo -e "\n${GREEN}✅ Benchmark complete! Check reports/benchmarks/ for results.${NC}"</content>
<parameter name="filePath">/home/tsun/Documents/CodeProvenance/run_benchmarks.sh