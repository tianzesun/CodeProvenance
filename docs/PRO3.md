一、benchmark.yaml（系统控制中心）

这是你所有 benchmark 的“唯一入口配置”。

✅ 标准版本（可直接使用）
# pipeline/config/benchmark.yaml

experiment:
  name: "baseline_v1"
  description: "Initial benchmark vs competitors"
  version: "1.0"

datasets:
  - name: "bigclonebench"
    path: "benchmark/datasets/bigclone/"
    language: "java"
  - name: "ocd"
    path: "benchmark/datasets/ocd/"
    language: "java"
  - name: "source_plag"
    path: "benchmark/datasets/source_plag/"
    language: "java"

tools:
  uniguard:
    enabled: true
    command: "python src/pipeline/detect.py --input {dataset} --output {output}"
  
  jplag:
    enabled: true
    command: "java -jar tools/jplag.jar -l java -r {output} {dataset}"
  
  moss:
    enabled: false
    command: "python tools/moss_client/moss.py -m {moss_id} {files}"
  
  nicad:
    enabled: false
    command: "tools/nicad/bin/nicad functions java {dataset}"

evaluation:
  threshold: 0.5
  metrics:
    - precision
    - recall
    - f1

output:
  report_dir: "benchmark/reports/"
  save_raw: true
  save_csv: true
  save_json: true

runtime:
  parallel: true
  max_workers: 8
🔥 这个设计的意义（非常重要）

它解决了：

❌ 写死路径
❌ 写死工具
❌ 无法复现实验

变成：

✅ 一键切换实验配置

二、统一输出格式（系统“协议”）

这是你系统最关键的“契约（contract）”。

✅ 标准输出（所有工具必须转换成这个）
{
  "pairs": [
    {
      "file1": "student1/A.java",
      "file2": "student2/A.java",
      "similarity": 0.87,
      "matches": [
        {
          "start1": 10,
          "end1": 30,
          "start2": 12,
          "end2": 32
        }
      ]
    }
  ]
}
🔥 强制要求

无论来源：

你自己的系统
JPlag
MOSS

👉 都必须转成这个格式

为什么必须统一？

否则你会遇到：

XML（JPlag）
HTML（MOSS）
JSON（你自己的）

👉 最终你会被格式拖死，而不是算法

三、Ground Truth 标准（评估基准）
{
  "pairs": [
    {
      "file1": "student1/A.java",
      "file2": "student2/A.java",
      "label": 1
    }
  ]
}
解释
字段	含义
label=1	抄袭
label=0	非抄袭
四、Evaluator 设计（核心逻辑）

这是整个 benchmark 的“裁判”。

✅ 输入
predictions.json
ground_truth.json
✅ 输出
{
  "precision": 0.91,
  "recall": 0.88,
  "f1": 0.895
}
🔥 核心逻辑（必须统一）
Step 1：二值化（threshold）
similarity >= threshold → 1
else → 0
Step 2：构造集合
Predicted = {(file1, file2)}
Truth     = {(file1, file2)}
Step 3：计算指标
TP = intersection(Predicted, Truth)
FP = Predicted - Truth
FN = Truth - Predicted
Step 4：计算
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2PR / (P + R)
五、报告输出标准（必须固定）
CSV（核心对比）
tool,precision,recall,f1
uniguard,0.91,0.88,0.895
jplag,0.87,0.85,0.86
JSON（详细）
{
  "experiment": "baseline_v1",
  "dataset": "bigclonebench",
  "results": {
    "uniguard": {...},
    "jplag": {...}
  }
}
六、benchmark.py 应该做什么（最终职责）
执行流程（必须严格）
for dataset in datasets:
    for tool in tools:
        run_tool()
        normalize_output()

    evaluate_all_tools()
    save_report()
七、你现在必须完成的三步（不要跳）
✅ Step 1：实现“统一输出转换器”

为每个工具写：

parsers/
 ├── uniguard_parser.py
 ├── jplag_parser.py
 └── moss_parser.py
✅ Step 2：实现 evaluator（最关键）

一个函数：

evaluate(predictions, truth, threshold)
✅ Step 3：跑第一次 benchmark

输出：

uniguard vs jplag F1
