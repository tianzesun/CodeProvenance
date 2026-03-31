一、Evaluator 的本质（必须先统一认知）

你的系统最终不是输出“相似度”，而是：

对“文件对是否构成抄袭”的判断能力

因此：

相似度 → 阈值 → 二分类 → 再评估
二、核心定义（严格数学语义）
1️⃣ 基本集合
Truth (T)      = 所有真实抄袭对
Predicted (P)  = 系统判断为抄袭的对
2️⃣ 三个核心集合
TP = P ∩ T
FP = P - T
FN = T - P
3️⃣ 指标
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2PR / (P + R)
三、最关键问题：什么算“一个 pair”？🔥
❗ 标准定义（必须固定）
(file1, file2) = 一个 submission-level pair

👉 即：

student1/A.java
student2/A.java

算一个 pair

❌ 禁止做法（很多人会犯错）
按“代码块 match”算 TP

👉 这是错误的，会严重扭曲 F1

四、Evaluator 边界情况（重点）
1️⃣ 对称性问题（必须解决）
问题：
(A, B) vs (B, A)
规范：
(A, B) == (B, A)

👉 统一：

pair = tuple(sorted([file1, file2]))
2️⃣ 多匹配问题（One-to-Many）
场景：
A 抄 B
A 抄 C
Truth：
(A,B), (A,C)
Predicted：
(A,B)
结果：
TP = 1
FN = 1

👉 不能算 TP=2

3️⃣ Partial Match（部分匹配）
场景：
实际抄袭（Truth = 1）
系统检测 similarity = 0.49
threshold = 0.5
判定：
→ FN（漏检）

👉 即使“很接近”，也必须算错

为什么这么严格？

否则：

❌ 不同系统 threshold 不同 → 无法比较

4️⃣ 多文件抄袭（Multi-file case）🔥
场景：
student1/
  A.java
  B.java

student2/
  A.java
  B.java
两种 Truth 定义（必须选一个）
✅ 推荐（严格版）
(A,A), (B,B)

👉 file-level evaluation

❌ 不推荐（但常见）
(student1, student2)

👉 submission-level

为什么？

file-level：

更细粒度
更公平
可解释
5️⃣ 重复预测（Duplicate Predictions）
场景：
(A,B) similarity=0.8
(A,B) similarity=0.9
规范：
保留最高 similarity
6️⃣ 非对称相似度（MOSS 特有）🔥
场景：
A→B = 90%
B→A = 70%
规范（必须统一）：
similarity = min(90, 70) = 70%
为什么？
更保守
防止高估检测能力
7️⃣ 阈值边界（Critical）
问题：
similarity == threshold ?
规范（必须固定）：
>= threshold → Positive
<  threshold → Negative
❗ 禁止：
> threshold

👉 否则边界不一致

8️⃣ 文件路径不一致（致命问题）
场景：
Truth: student1/A.java
Pred : A.java
结果：
→ FP + FN（双重错误）
解决：

必须统一：

normalize_path()
9️⃣ 空预测（Empty Prediction）
场景：
Predicted = ∅
Truth ≠ ∅
结果：
TP = 0
FP = 0
FN = |T|
Recall = 0

👉 正确行为

10️⃣ 全预测（Over-predict）
场景：
Predicted = 所有 pairs
结果：
Recall = 1
Precision → 很低

👉 用于检测“作弊模型”

五、Evaluator 标准流程（最终规范）
1. normalize paths
2. canonicalize pairs (A,B)
3. deduplicate (keep max similarity)
4. threshold → binary
5. build sets P and T
6. compute TP / FP / FN
7. compute metrics
六、你必须额外输出的分析（高级）
1️⃣ False Positive 列表
[
  (A,B), (C,D)
]
2️⃣ False Negative 列表（最重要）

👉 用于训练

七、一个“行业级坑”（必须知道）

很多系统会：

❌ 调 threshold 让 F1 看起来更高

正确做法：

必须：

固定 threshold（如 0.5）

或：

画 PR 曲线 / ROC 曲线
八、最终标准（一句话总结）

Evaluator 的职责不是“算分”，而是“定义什么叫正确”
