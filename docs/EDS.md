我给你一套工程可落地 + 可持续优化 + 可做论文的融合策略。

一、核心问题本质

你有三类信号：

S_f = fingerprint similarity   （Winnowing / token）
S_a = AST similarity           （结构）
S_s = semantic similarity      （AI embedding）

问题是：

如何组合它们，得到最终相似度 S_final

二、最错误的做法（必须避免）
S = (S_f + S_a + S_s) / 3

❌ 这是“平均主义”，会严重拉低效果

三、正确思路：分层融合（Layered Fusion）🔥
总体结构
Layer 1: 基础信号（S_f, S_a, S_s）
        ↓
Layer 2: 特征工程（features）
        ↓
Layer 3: 融合模型（fusion）
        ↓
S_final
四、Layer 1：信号标准化（必须）
统一范围
所有 similarity ∈ [0,1]
典型问题
信号	问题
fingerprint	对重排不敏感
AST	对小改动敏感
semantic	可能误判

👉 所以不能直接用

五、Layer 2：特征工程（关键）

不要只用 3 个 similarity，必须扩展：

基础特征（必须）
features = [
  S_f,
  S_a,
  S_s,
]
增强特征（强烈建议）
features += [
  abs(S_f - S_a),        # 差异信号
  max(S_f, S_a, S_s),    # 强信号
  min(S_f, S_a, S_s),    # 弱信号
]
结构辅助特征
features += [
  length_ratio,
  num_tokens_diff,
]

👉 最终：

~8–12 维 feature vector
六、Layer 3：融合策略（3种级别）
1️⃣ Level 1：加权规则（MVP）
推荐公式（直接可用）
S_final =
  w_f * S_f +
  w_a * S_a +
  w_s * S_s
推荐权重（经验值）
w_f = 0.4
w_a = 0.35
w_s = 0.25
为什么？
fingerprint → 稳定（主力）
AST → 结构补充
AI → 兜底（防绕过）
⚠️ 必须加规则增强
规则1：强匹配优先
if S_f > 0.8:
    S_final += 0.1
规则2：一致性增强
if S_f > 0.6 and S_a > 0.6:
    boost
规则3：冲突惩罚
if S_f high but S_a very low:
    penalty
2️⃣ Level 2：Logistic Regression（推荐）
思路
input: feature vector
output: probability of plagiarism
优势
自动学习权重
可解释
易训练
输出
P(plagiarism) ∈ [0,1]

👉 直接当 S_final

3️⃣ Level 3：Learning-to-Rank（高级）
用于：

优化：

Top-K / MAP
方法：
pairwise ranking loss
triplet loss

👉 用于提升排序质量（不是基础）

七、动态权重（非常重要）
不同场景，权重必须变化
场景1：简单抄袭
S_f ↑ → 权重大
场景2：重构代码
S_a ↑ → 权重大
场景3：AI生成
S_s ↑ → 权重大
实现方法（简单版）
if S_f < 0.3:
    increase S_s weight

👉 这叫：

adaptive weighting

八、最终决策（Binary）
S_final >= threshold → plagiarism
threshold 建议：
0.5（benchmark）
0.6–0.7（实际系统）
九、一个非常关键的优化点（90%→95%）
❗“一致性信号”是关键

如果：

S_f, S_a, S_s 都高

👉 几乎必定抄袭

如果：

只有一个高

👉 很可能误判

实现：
consistency = variance(S_f, S_a, S_s)

👉 variance 越小 → 越可信

十、完整融合流程（最终版）
compute S_f, S_a, S_s
   ↓
build feature vector
   ↓
apply fusion model
   ↓
apply rules (boost / penalty)
   ↓
S_final
   ↓
threshold → classification
十一、工程实现建议（非常具体）
第一阶段（你现在就该做）
加权融合（0.4 / 0.35 / 0.25）
加3条规则（boost/penalty）
第二阶段
收集 FN / FP
用 Logistic Regression 训练
第三阶段
加 ranking loss（MAP优化）
十二、你当前系统会发生什么提升？

如果你现在：

F1 ≈ 0.85

加入融合后：

→ 0.90（很容易）
→ 0.93–0.95（合理）
十三、最后一句话（核心认知）

单一算法决定“下限”，融合策略决定“上限”
