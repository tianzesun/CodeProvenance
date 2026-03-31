一、核心认知（必须统一）

你的系统输出本质是：

(file1, file2, similarity) → 排序列表

👉 所以：

你不是分类器，而是排序系统（Ranking System）

二、Top-K 评估（工程最重要）
1️⃣ 定义

给定排序结果：

ranked_pairs = [(A,B), (C,D), (E,F), ...]

取前 K 个：

Top-K = ranked_pairs[:K]
2️⃣ Top-K Precision（必须实现）
公式
Precision@K = (# of relevant pairs in Top-K) / K
示例
Top-5:
[(A,B), (C,D), (X,Y), (M,N), (P,Q)]

Truth:
(A,B), (X,Y)
Precision@5 = 2 / 5 = 0.4
3️⃣ Top-K Recall（可选但建议）
公式
Recall@K = (# of relevant pairs in Top-K) / (total relevant pairs)
示例
Truth total = 4
Top-5 hit = 2

Recall@5 = 2 / 4 = 0.5
4️⃣ 为什么 Top-K 非常重要？

现实中老师：

不看全部结果
只看前 10–20 个

👉 所以：

Top-K 比 F1 更接近真实使用价值

三、MAP（Mean Average Precision）🔥

这是你必须实现的“高级指标”。

1️⃣ 直观理解

MAP 衡量：

正确结果是否排在前面

2️⃣ 单个查询的 AP（Average Precision）
定义

对于一个排序列表：

ranked list:
1: (A,B) ❌
2: (X,Y) ✅
3: (C,D) ❌
4: (M,N) ✅
计算步骤
Step 1：只在“命中时”计算 Precision
位置2命中 → Precision@2 = 1/2 = 0.5
位置4命中 → Precision@4 = 2/4 = 0.5
Step 2：求平均
AP = (0.5 + 0.5) / 2 = 0.5
3️⃣ MAP（多个查询）

如果有多个 dataset / queries：

MAP = mean(AP_i)
4️⃣ 数学公式（标准）
AP = Σ (Precision@k × rel(k)) / (# relevant)

其中：

rel(k) = 1 if relevant else 0
四、在你系统中的“查询定义”（关键）
❗问题：什么是“query”？

你有两种选择：

✅ 推荐（标准做法）
每个 submission = 一个 query

例如：

Query = student1/A.java
Candidates = 所有其他文件

👉 然后排序：

(A,B), (A,C), (A,D), ...
❌ 不推荐
全局 pair list

👉 会破坏 MAP 语义

五、完整评估结构（你应该实现）
1️⃣ 输入
{
  "pairs": [
    {"file1": "A", "file2": "B", "similarity": 0.9}
  ]
}
2️⃣ 转换为 Query 结构
A → [(A,B), (A,C), ...]
B → [(B,A), (B,D), ...]
3️⃣ 对每个 Query 排序
按 similarity 降序
4️⃣ 对每个 Query 计算 AP
5️⃣ 求 MAP
六、你必须实现的函数接口（标准）
Top-K
top_k_precision(predictions, truth, k)
top_k_recall(predictions, truth, k)
MAP
mean_average_precision(predictions, truth)
七、边界情况（必须处理）
1️⃣ 没有 relevant（关键）
Truth = ∅
规范：
AP = 0（或跳过）

👉 推荐：

跳过该 query
2️⃣ Top-K > 总结果数
K = min(K, len(predictions))
3️⃣ 重复 pair（必须提前处理）

👉 否则 MAP 错误

4️⃣ 对称性（再次强调）
(A,B) == (B,A)
八、最终你应该输出的报告（升级版）
CSV
tool,F1@0.5,Precision@10,Precision@20,MAP
uniguard,0.89,0.80,0.75,0.82
jplag,0.85,0.72,0.70,0.76
JSON（详细）
{
  "dataset": "bigclonebench",
  "metrics": {
    "f1@0.5": 0.89,
    "precision@10": 0.80,
    "map": 0.82
  }
}
九、非常关键的一点（很多人忽略）
❗F1 vs MAP 的区别
指标	本质
F1	分类能力
Top-K	用户体验
MAP	排序质量

👉 你要同时优化三者，而不是只看 F1

十、工程落地建议（直接可做）
第一优先级

实现：

precision@10
precision@20
第二优先级

实现：

MAP（按 query 分组）
第三优先级

输出：

per-query AP（用于分析）
十一、最后一句话（核心认知）

真正优秀的检测系统，不只是“找对”，而是“把最可疑的排在最前面”
