我给你一套Production-level Evaluator Architecture（可扩展、可复现、可对标JPlag/MOSS级系统）。

一、核心目标（先定标准）

生产级 evaluator 不是“算 F1”，而是：

一个可复现实验、可横向对比、可持续演进的评估平台

必须满足：

可复现（Reproducible）
可对比（Comparable）
可扩展（Extensible）
可审计（Auditable）
二、总体架构（标准工业分层）
                    ┌──────────────────────┐
                    │   Experiment Layer   │
                    │  (benchmark runner)  │
                    └─────────┬────────────┘
                              ↓
┌────────────────────────────────────────────────┐
│            Evaluation Orchestrator             │
│  - dataset manager                            │
│  - tool runner                                │
│  - result collector                           │
└───────────────┬───────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           Normalization Layer                  │
│  - unify outputs (JPlag/MOSS/custom)          │
│  - canonical pair mapping                     │
│  - deduplication                              │
└───────────────┬───────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           Scoring Layer                        │
│  - similarity → ranking                       │
│  - thresholding (adaptive)                    │
│  - PR / ROC computation                       │
└───────────────┬───────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           Metrics Layer                        │
│  - F1 / Precision / Recall                    │
│  - MAP / MRR / Top-K                          │
│  - calibration metrics                        │
└───────────────┬───────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           Analysis Layer                       │
│  - FN/FP classification                       │
│  - error taxonomy                            │
│  - dataset bias detection                    │
└───────────────┬───────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           Reporting Layer                      │
│  - JSON (machine)                            │
│  - CSV (comparison)                          │
│  - HTML dashboard                            │
│  - plots (PR curve, F1 curve)               │
└────────────────────────────────────────────────┘
三、核心组件设计（必须实现）
1️⃣ Evaluation Orchestrator（总控）
职责
- 运行所有 tools
- 收集 raw outputs
- dispatch to normalizer
输入
{
  "dataset": "bigclonebench",
  "tools": ["uniguard", "jplag", "moss"]
}
输出
raw_results/
2️⃣ Normalization Layer（最关键🔥）
目标

把所有工具输出统一为：

(pair, similarity)
支持格式
工具	格式
JPlag	XML
MOSS	HTML
custom	JSON
统一结构
{
  "pair": ["A.java", "B.java"],
  "similarity": 0.83
}
必须做：
canonical pair
deduplication
path normalization
3️⃣ Scoring Layer（决策核心）
输入
normalized pairs
输出
binary predictions OR ranked list
功能
1️⃣ thresholding
similarity >= t → positive
2️⃣ ranking
sort by similarity
3️⃣ PR curve generator
4️⃣ threshold optimizer
4️⃣ Metrics Layer（评估核心）
分类指标
Precision
Recall
F1
Accuracy (optional)
排序指标（必须）
MAP
MRR
Top-K Precision
Top-K Recall
calibration（高级）
Brier Score
ECE (Expected Calibration Error)

👉 用于判断 similarity 是否可信

5️⃣ Analysis Layer（你系统的“智能部分”🔥）
FN/FP taxonomy
FN:
 - structural change
 - semantic rewrite
 - obfuscation
FP analysis
FP causes:
 - common library code
 - boilerplate
 - template similarity
dataset bias detection
- too many easy clones
- imbalance
- leakage
6️⃣ Reporting Layer（必须工业级）
输出三层结构
1️⃣ machine-readable
metrics.json
2️⃣ comparison table
tool,f1,map,top10
3️⃣ visual dashboard
PR curve
F1 vs threshold
MAP curve
四、关键设计原则（非常重要）
1️⃣ Separation of Concerns（必须）
evaluation ≠ normalization ≠ metrics
2️⃣ Reproducibility

必须记录：

dataset version
threshold method
tool version
random seed
3️⃣ Tool Agnostic Design（核心）
JPlag / MOSS / UniGuard → same interface
4️⃣ Dataset Independence
evaluator must not depend on dataset structure
五、推荐目录结构（生产级）
benchmark/
├── orchestrator/
├── normalizer/
├── scorer/
├── metrics/
├── analysis/
├── reporting/
├── datasets/
├── configs/
└── runs/
六、运行流程（完整 pipeline）
1. load config
2. run tools
3. normalize outputs
4. build ground truth mapping
5. compute ranking
6. threshold sweep (PR curve)
7. compute metrics (F1/MAP/Top-K)
8. analyze FN/FP
9. generate report
七、你现在系统的升级路径
当前：
single evaluator script
目标：
modular evaluation platform
中间阶段：
+ normalization layer
+ MAP
+ PR optimizer
最终：
full benchmark platform (JPlag-like)
八、一个关键现实判断

如果你做到这一层：

你已经不只是在“做检测算法”

你是在做：

Plagiarism Detection Benchmark Infrastructure

九、最关键一句话（系统级理解）

Evaluator 不再是函数，而是一个“实验操作系统”
