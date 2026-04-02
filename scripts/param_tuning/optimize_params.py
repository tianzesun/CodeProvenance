"""
参数自动调优框架 - Parameter Auto-Tuning Framework.

支持两种调参方法:
1. GridSearch: 穷举所有参数组合，精确但计算量大
2. Bayesian Optimization: 使用scikit-optimize库，高效搜索最优参数

Usage:
    # GridSearch
    python scripts/param_tuning/optimize_params.py --method grid --dataset synthetic
    
    # Bayesian Optimization
    python scripts/param_tuning/optimize_params.py --method bayesian --n_calls 50
    
    # 自定义参数范围
    python scripts/param_tuning/optimize_params.py --method grid --thresholds 0.1,0.3,0.5,0.7,0.9

输出:
    - results/param_tuning/grid_search_results.csv (所有组合的结果)
    - results/param_tuning/best_params.json (最优参数)
    - results/param_tuning/optimization_plot.png (可视化)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd
import itertools

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from src.engines.similarity.structural_ast_similarity import StructuralASTSimilarity


# ============================================================================
# Default Parameter Grid
# ============================================================================

# 相似阈值: 0.1 ~ 0.9, 步长 0.05 (16个值)
DEFAULT_THRESHOLDS = [round(v, 2) for v in np.arange(0.10, 0.95, 0.05)]

# Token窗口大小: 5 ~ 50, 步长5 (10个值)
DEFAULT_TOKEN_WINDOWS = list(range(5, 55, 5))

# 权重alpha: 0.0 ~ 1.0, 步长0.1 (11个值)
DEFAULT_ALPHAS = [round(v, 2) for v in np.arange(0.0, 1.05, 0.1)]

# 完整参数网格 (约1760组合，实际按需要选择子集)
DEFAULT_PARAM_GRID = {
    "similarity_threshold": DEFAULT_THRESHOLDS[:8],  # 取前8个减少计算量
    "ted_weight": [0.1, 0.2, 0.25, 0.3, 0.4],
    "tree_kernel_weight": [0.05, 0.1, 0.15, 0.2, 0.25],
    "cfg_weight": [0.05, 0.1, 0.15, 0.2],
    "dfg_weight": [0.05, 0.1, 0.15, 0.2],
    "pattern_weight": [0.05, 0.1, 0.15, 0.2],
    "tree_kernel_decay": [0.3, 0.4, 0.5, 0.6, 0.7],
    "pattern_min_subtree_size": [2, 3, 4, 5],
    "path_max_length": [6, 8, 10, 12],
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TuningResult:
    """单次参数组合的评估结果."""
    params: Dict[str, Any]
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    tn: int
    fn: int
    eval_time_seconds: float


@dataclass
class OptimizationSummary:
    """调优结果汇总."""
    best_params: Dict[str, Any]
    best_f1: float
    best_precision: float
    best_recall: float
    total_combinations: int
    total_time_seconds: float
    top_5_results: List[Dict[str, Any]]
    method: str


# ============================================================================
# Evaluation Functions
# ============================================================================

def evaluate_params(
    params: Dict[str, Any],
    dataset,
) -> TuningResult:
    """
    评估一组参数在数据集上的表现.
    
    Args:
        params: 参数字典
        dataset: 合成数据集 (SyntheticDataset)
    
    Returns:
        TuningResult with metrics
    """
    start_time = time.time()
    
    # 创建算法实例并设置参数
    algo = StructuralASTSimilarity()
    algo.set_params(**params)
    
    threshold = params.get("similarity_threshold", 0.5)
    
    # 在所有数据对上评估
    tp = fp = tn = fn = 0
    
    for pair in dataset.pairs:
        try:
            parsed_a = _code_to_parsed(pair.code_a)
            parsed_b = _code_to_parsed(pair.code_b)
            
            score = algo.compare(parsed_a, parsed_b)
            score = max(0.0, min(1.0, score))
            
            predicted = 1 if score >= threshold else 0
            actual = pair.label  # 1=clone, 0=non-clone
            
            if predicted == 1 and actual == 1:
                tp += 1
            elif predicted == 1 and actual == 0:
                fp += 1
            elif predicted == 0 and actual == 0:
                tn += 1
            else:
                fn += 1
        except Exception:
            # On error, treat as non-match
            if pair.label == 1:
                fn += 1
            else:
                tn += 1
    
    elapsed = time.time() - start_time
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    
    return TuningResult(
        params=params.copy(),
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        eval_time_seconds=elapsed,
    )


def _code_to_parsed(code: str) -> Dict[str, Any]:
    """
    将代码字符串转换为解析表示.
    
    简单的token-based解析，实际使用时可替换为真正的AST解析器.
    """
    import tokenize
    import io
    
    tokens = []
    try:
        token_stream = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in token_stream:
            tokens.append({
                "type": tokenize.tok_name.get(tok.type, "UNKNOWN"),
                "value": tok.string,
                "line": tok.start[0],
            })
    except tokenize.TokenError:
        # Fallback: simple whitespace tokenization
        tokens = [{"type": "WORD", "value": t, "line": 0} for t in code.split()]
    
    return {"tokens": tokens, "language": "python"}


# ============================================================================
# GridSearch
# ============================================================================

def run_grid_search(
    param_grid: Dict[str, List[Any]],
    dataset,
    output_dir: str = "results/param_tuning",
    max_combinations: Optional[int] = None,
) -> OptimizationSummary:
    """
    执行GridSearch参数扫描.
    
    Args:
        param_grid: 参数字典，key为参数名，value为候选值列表
        dataset: 评估数据集
        output_dir: 输出目录
        max_combinations: 最大组合数限制 (None=无限制)
    
    Returns:
        OptimizationSummary
    """
    print("=" * 70)
    print("GRID SEARCH PARAMETER OPTIMIZATION")
    print("=" * 70)
    
    # 生成所有参数组合
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    all_combinations = list(itertools.product(*values))
    
    total = len(all_combinations)
    if max_combinations:
        # 随机抽样如果组合太多
        if total > max_combinations:
            indices = np.random.choice(total, max_combinations, replace=False)
            all_combinations = [all_combinations[i] for i in indices]
            total = len(all_combinations)
            print(f"Sampled {total} combinations from {len(itertools.product(*values))} total")
    
    print(f"\nTotal parameter combinations: {total}")
    print(f"Parameter dimensions: {len(keys)}")
    for k, v in param_grid.items():
        print(f"  {k}: {len(v)} values")
    
    results: List[TuningResult] = []
    start_time = time.time()
    
    for i, combo in enumerate(all_combinations):
        params = dict(zip(keys, combo))
        result = evaluate_params(params, dataset)
        results.append(result)
        
        if (i + 1) % 10 == 0 or i == total - 1:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            eta = avg_time * (total - i - 1)
            print(
                f"  Progress: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%) | "
                f"Best F1: {max(r.f1 for r in results):.4f} | "
                f"ETA: {eta:.0f}s"
            )
    
    total_elapsed = time.time() - start_time
    
    # 转换为DataFrame并保存
    df = pd.DataFrame([asdict(r) for r in results])
    # 展开params列
    params_df = pd.DataFrame(df['params'].tolist())
    df = pd.concat([params_df, df.drop(columns=['params'])], axis=1)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 保存完整结果
    csv_file = output_path / "grid_search_results.csv"
    df.to_csv(csv_file, index=False)
    print(f"\nResults saved to: {csv_file}")
    
    # 找最优参数
    best_idx = df['f1'].idxmax()
    best_row = df.loc[best_idx]
    
    # 保存最优参数
    best_params = {k: best_row[k] for k in keys}
    best_params_file = output_path / "best_params.json"
    
    summary = OptimizationSummary(
        best_params=best_params,
        best_f1=float(best_row['f1']),
        best_precision=float(best_row['precision']),
        best_recall=float(best_row['recall']),
        total_combinations=total,
        total_time_seconds=total_elapsed,
        top_5_results=df.nlargest(5, 'f1').to_dict(orient='records'),
        method="grid_search",
    )
    
    with open(best_params_file, 'w') as f:
        json.dump(asdict(summary), f, indent=2, default=str)
    print(f"Best params saved to: {best_params_file}")
    
    # 打印Top 5
    print(f"\n{'='*70}")
    print("TOP 5 PARAMETER COMBINATIONS")
    print(f"{'='*70}")
    top5 = df.nlargest(5, 'f1')
    for rank, (_, row) in enumerate(top5.iterrows(), 1):
        print(f"\n  Rank #{rank}: F1={row['f1']:.4f}")
        print(f"    Precision: {row['precision']:.4f}, Recall: {row['recall']:.4f}")
        for k in keys:
            print(f"    {k}: {row[k]}")
    
    # 参数重要性分析
    print(f"\n{'='*70}")
    print("PARAMETER IMPORTANCE (by correlation with F1)")
    print(f"{'='*70}")
    for k in keys:
        if df[k].dtype in [np.float64, np.int64, float, int]:
            corr = df[k].corr(df['f1'])
            print(f"  {k}: {corr:.4f}")
    
    return summary


# ============================================================================
# Bayesian Optimization (using scikit-optimize)
# ============================================================================

def run_bayesian_optimization(
    param_space: Dict[str, Any],
    dataset,
    n_calls: int = 50,
    n_initial_points: int = 10,
    output_dir: str = "results/param_tuning",
) -> OptimizationSummary:
    """
    使用scikit-optimize执行贝叶斯优化.
    
    Args:
        param_space: 参数空间定义
        dataset: 评估数据集
        n_calls: 总评估次数
        n_initial_points: 初始随机点数
        output_dir: 输出目录
    
    Returns:
        OptimizationSummary
    """
    try:
        from skopt import gp_minimize
        from skopt.space import Real, Integer, Categorical
        from skopt.utils import use_named_args
    except ImportError:
        print("Error: scikit-optimize not installed.")
        print("Install with: pip install scikit-optimize")
        print("Falling back to grid search...")
        # Fallback to grid search
        return run_grid_search(DEFAULT_PARAM_GRID, dataset, output_dir)
    
    print("=" * 70)
    print("BAYESIAN OPTIMIZATION")
    print("=" * 70)
    print(f"Total evaluations: {n_calls}")
    print(f"Initial random points: {n_initial_points}")
    
    # 定义搜索空间
    dimensions = []
    for param_name, param_def in param_space.items():
        if isinstance(param_def, dict):
            low = param_def.get("low", 0.0)
            high = param_def.get("high", 1.0)
            if param_def.get("type") == "int":
                dimensions.append(Integer(low, high, name=param_name))
            else:
                dimensions.append(Real(low, high, name=param_name))
        elif isinstance(param_def, (list, tuple)):
            if all(isinstance(v, (int, float)) for v in param_def):
                dimensions.append(Real(min(param_def), max(param_def), name=param_name))
            else:
                dimensions.append(Categorical(param_def, name=param_name))
    
    param_names = [d.name for d in dimensions]
    print(f"Search space dimensions: {len(dimensions)}")
    for d in dimensions:
        print(f"  {d.name}: {d}")
    
    # 目标函数 (负F1因为是最小化)
    @use_named_args(dimensions)
    def objective(**params):
        result = evaluate_params(params, dataset)
        return -result.f1  # 负号因为gp_minimize是最小化
    
    # 运行优化
    start_time = time.time()
    opt_result = gp_minimize(
        func=objective,
        dimensions=dimensions,
        n_calls=n_calls,
        n_initial_points=n_initial_points,
        random_state=42,
        verbose=True,
    )
    total_elapsed = time.time() - start_time
    
    # 处理结果
    best_params = dict(zip(param_names, opt_result.x))
    best_f1 = -opt_result.fun
    
    print(f"\n{'='*70}")
    print("BEST PARAMETERS FOUND")
    print(f"{'='*70}")
    for k, v in best_params.items():
        print(f"  {k}: {v}")
    print(f"\n  Best F1: {best_f1:.4f}")
    print(f"  Total time: {total_elapsed:.1f}s")
    
    # 保存结果
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 从优化历史中提取结果
    results_data = []
    for i, (x_val, y_val) in enumerate(zip(opt_result.x_iters, opt_result.func_vals)):
        params = dict(zip(param_names, x_val))
        f1 = -y_val
        results_data.append({
            "iteration": i + 1,
            "f1": f1,
            **params,
        })
    
    df = pd.DataFrame(results_data)
    csv_file = output_path / "bayesian_optimization_results.csv"
    df.to_csv(csv_file, index=False)
    
    # 保存最优参数
    summary = OptimizationSummary(
        best_params=best_params,
        best_f1=best_f1,
        best_precision=0.0,  # 需要额外评估
        best_recall=0.0,
        total_combinations=n_calls,
        total_time_seconds=total_elapsed,
        top_5_results=df.nlargest(5, 'f1').to_dict(orient='records'),
        method="bayesian_optimization",
    )
    
    with open(output_path / "best_params_bayesian.json", 'w') as f:
        json.dump(asdict(summary), f, indent=2, default=str)
    
    # 绘制收敛曲线
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # 收敛曲线
        cumulative_best = np.minimum.accumulate(opt_result.func_vals)
        axes[0].plot(-cumulative_best, 'b-', linewidth=2)
        axes[0].set_xlabel('Iteration')
        axes[0].set_ylabel('Best F1 Score')
        axes[0].set_title('Bayesian Optimization Convergence')
        axes[0].grid(True, alpha=0.3)
        
        # 参数值分布
        numeric_params = [k for k in param_names 
                         if df[k].dtype in [np.float64, np.int64]]
        if numeric_params:
            sample_param = numeric_params[0]
            axes[1].scatter(df[sample_param], df['f1'], alpha=0.5, s=20)
            axes[1].set_xlabel(sample_param)
            axes[1].set_ylabel('F1 Score')
            axes[1].set_title(f'F1 vs {sample_param}')
            axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plot_file = output_path / "optimization_plot.png"
        plt.savefig(plot_file, dpi=150)
        plt.close()
        print(f"Plot saved to: {plot_file}")
    except ImportError:
        print("matplotlib not available, skipping plot generation")
    
    return summary


# ============================================================================
# Simple Threshold Optimization (快速阈值搜索)
# ============================================================================

def optimize_threshold_only(
    dataset,
    algorithm: Optional[StructuralASTSimilarity] = None,
    thresholds: Optional[List[float]] = None,
) -> Tuple[float, float]:
    """
    仅优化相似阈值，固定其他参数.
    
    Args:
        dataset: 评估数据集
        algorithm: 算法实例 (None=使用默认参数)
        thresholds: 候选阈值列表
    
    Returns:
        (best_threshold, best_f1)
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    if algorithm is None:
        algorithm = StructuralASTSimilarity()
    
    # 先计算所有对的相似度分数
    print("Computing similarity scores for all pairs...")
    pairs_with_scores: List[Tuple[float, int]] = []
    
    for pair in dataset.pairs:
        parsed_a = _code_to_parsed(pair.code_a)
        parsed_b = _code_to_parsed(pair.code_b)
        score = algorithm.compare(parsed_a, parsed_b)
        pairs_with_scores.append((score, pair.label))
    
    print(f"Computed {len(pairs_with_scores)} scores, evaluating thresholds...")
    
    best_threshold = 0.5
    best_f1 = 0.0
    
    for t in thresholds:
        tp = fp = tn = fn = 0
        for score, label in pairs_with_scores:
            predicted = 1 if score >= t else 0
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 0:
                tn += 1
            else:
                fn += 1
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
    
    print(f"Best threshold: {best_threshold:.2f}")
    print(f"Best F1: {best_f1:.4f}")
    
    return best_threshold, best_f1


# ============================================================================
# Entry Point
# ============================================================================

def main() -> int:
    """主入口."""
    parser = argparse.ArgumentParser(
        description="Parameter Optimization for CodeProvenance"
    )
    parser.add_argument(
        "--method",
        choices=["grid", "bayesian", "threshold"],
        default="threshold",
        help="Optimization method (default: threshold)",
    )
    parser.add_argument(
        "--dataset",
        choices=["synthetic", "custom"],
        default="synthetic",
        help="Dataset to use (default: synthetic)",
    )
    parser.add_argument(
        "--output-dir",
        default="results/param_tuning",
        help="Output directory (default: results/param_tuning)",
    )
    parser.add_argument(
        "--n-calls",
        type=int,
        default=50,
        help="Number of evaluations for Bayesian optimization",
    )
    parser.add_argument(
        "--max-combinations",
        type=int,
        default=None,
        help="Max combinations for GridSearch (None=all)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--type1", type=int, default=30, help="Type-1 pairs count"
    )
    parser.add_argument(
        "--type2", type=int, default=30, help="Type-2 pairs count"
    )
    parser.add_argument(
        "--type3", type=int, default=30, help="Type-3 pairs count"
    )
    parser.add_argument(
        "--type4", type=int, default=20, help="Type-4 pairs count"
    )
    parser.add_argument(
        "--non-clone", type=int, default=100, help="Non-clone pairs count"
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Comma-separated threshold values (e.g., 0.1,0.3,0.5,0.7,0.9)",
    )
    
    args = parser.parse_args()
    np.random.seed(args.seed)
    
    # 生成数据集
    print("=" * 70)
    print("GENERATING DATASET")
    print("=" * 70)
    generator = SyntheticDatasetGenerator(seed=args.seed)
    dataset = generator.generate_pair_count(
        type1=args.type1,
        type2=args.type2,
        type3=args.type3,
        type4=args.type4,
        non_clone=args.non_clone,
    )
    print(f"Dataset stats: {dataset.stats()}")
    
    # 解析自定义阈值
    custom_thresholds = None
    if args.thresholds:
        custom_thresholds = [float(v) for v in args.thresholds.split(",")]
    
    # 执行调优
    if args.method == "grid":
        param_grid = DEFAULT_PARAM_GRID.copy()
        if custom_thresholds:
            param_grid["similarity_threshold"] = custom_thresholds
        
        summary = run_grid_search(
            param_grid=param_grid,
            dataset=dataset,
            output_dir=args.output_dir,
            max_combinations=args.max_combinations,
        )
    
    elif args.method == "bayesian":
        # 贝叶斯优化的参数空间
        param_space = {
            "similarity_threshold": {"low": 0.1, "high": 0.9},
            "ted_weight": {"low": 0.05, "high": 0.5},
            "tree_kernel_weight": {"low": 0.0, "high": 0.3},
            "cfg_weight": {"low": 0.0, "high": 0.3},
            "dfg_weight": {"low": 0.0, "high": 0.3},
            "pattern_weight": {"low": 0.0, "high": 0.3},
            "tree_kernel_decay": {"low": 0.2, "high": 0.8},
            "pattern_min_subtree_size": {"low": 2, "high": 5, "type": "int"},
            "path_max_length": {"low": 4, "high": 12, "type": "int"},
        }
        summary = run_bayesian_optimization(
            param_space=param_space,
            dataset=dataset,
            n_calls=args.n_calls,
            output_dir=args.output_dir,
        )
    
    elif args.method == "threshold":
        algo = StructuralASTSimilarity()
        thresholds = custom_thresholds or DEFAULT_THRESHOLDS
        best_t, best_f = optimize_threshold_only(
            dataset=dataset,
            algorithm=algo,
            thresholds=thresholds,
        )
        
        # 保存结果
        output_path = Path(args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        summary = OptimizationSummary(
            best_params={"similarity_threshold": best_t},
            best_f1=best_f,
            best_precision=0.0,
            best_recall=0.0,
            total_combinations=len(thresholds),
            total_time_seconds=0.0,
            top_5_results=[],
            method="threshold_optimization",
        )
        
        with open(output_path / "best_params_threshold.json", 'w') as f:
            json.dump(asdict(summary), f, indent=2)
    
    else:
        print(f"Unknown method: {args.method}")
        return 1
    
    print(f"\n{'='*70}")
    print("OPTIMIZATION COMPLETE")
    print(f"'='*70}")
    print(f"Results saved to: {args.output_dir}/")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())