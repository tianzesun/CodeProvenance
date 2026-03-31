我会给你一套可工程落地 + 可用于训练数据生成的 FN 自动分类系统设计。

一、核心目标（先讲清本质）

你的 FN（False Negative）不是“错误”，而是：

最有价值的训练数据来源

因此目标不是简单分类，而是：

FN → 分类 → 结构化标签 → 转为训练样本 → 提升模型
二、FN 自动分类系统整体架构
analysis/
├── fn_collector.py          # 收集FN
├── fn_classifier/           # 分类核心
│   ├── rules.py             # 规则分类（第一层）
│   ├── ml_classifier.py     # ML分类（第二层）
│   └── taxonomy.py          # 分类体系定义
├── feature_extractor.py     # 特征提取
├── dataset_builder.py       # 生成训练数据
└── reports/
三、FN 分类体系（Taxonomy）🔥

这是整个系统最关键的设计，必须标准化。

一级分类（必须固定）
FN Categories:
1. lexical_variation        # 词法层变化
2. structural_variation     # 结构变化
3. semantic_variation       # 语义变化
4. obfuscation              # 混淆
5. ai_generated             # AI生成代码
6. cross_language           # 跨语言
7. noise                    # 数据噪声/标注错误
二级分类（建议）
1️⃣ lexical_variation
variable_renaming
formatting_change
comment_change
2️⃣ structural_variation
statement_reordering
loop_transformation
function_inlining
function_splitting
3️⃣ semantic_variation（最难）
algorithm_equivalent
logic_rewrite
4️⃣ obfuscation
dead_code_insertion
control_flow_flattening
opaque_predicates
5️⃣ ai_generated
llm_style_pattern
over-generalized code
四、FN 分类流程（标准 pipeline）
FN pairs
   ↓
Feature Extraction
   ↓
Rule-based Classification（快速）
   ↓
ML Classification（补充）
   ↓
Multi-label tagging
   ↓
输出结构化数据
五、特征提取设计（核心）
1️⃣ 基础特征（必须）
token_similarity
ast_similarity
length_ratio
2️⃣ 结构特征
tree_edit_distance
num_functions
nesting_depth
3️⃣ 词法特征
identifier_overlap
keyword_distribution
4️⃣ AI特征（高级）
perplexity
repetition_score
style_uniformity
六、规则分类器（第一层，必须先做）
示例规则（直接可实现）
规则1：变量改名
if:
  token_similarity low
  AND ast_similarity high
then:
  lexical_variation.variable_renaming
规则2：结构变化
if:
  ast_similarity medium
  AND token_similarity low
then:
  structural_variation
规则3：混淆
if:
  length_ratio > 1.5
  AND many unused variables
then:
  obfuscation.dead_code_insertion
规则4：AI生成
if:
  very high consistency
  low variation
  repetitive patterns
then:
  ai_generated
七、ML 分类器（第二层）
什么时候用？

当规则无法判断：

unknown / ambiguous FN
模型形式
input: (code1, code2)
output: category label
推荐：
CodeBERT / CodeT5
multi-label classification
八、输出格式（必须标准化）
{
  "file1": "A.java",
  "file2": "B.java",
  "labels": [
    "lexical_variation.variable_renaming"
  ],
  "features": {
    "token_similarity": 0.3,
    "ast_similarity": 0.8
  }
}
九、训练数据生成（核心目标）
从 FN → 训练数据
正样本（clone）
FN → label = 1
负样本（非clone）
FP → label = 0
构造数据集
{
  "code1": "...",
  "code2": "...",
  "label": 1,
  "category": "structural_variation"
}
十、自动数据增强（高级）
用 FN 生成更多样本
示例：
原 FN: variable renaming

生成：

rename again
partial rename
mixed rename + reorder

👉 用于扩大训练集

十一、报告输出（必须）
统计分布
FN Breakdown:
- lexical: 40%
- structural: 30%
- semantic: 20%
- AI: 10%
作用

👉 告诉你：

系统弱在哪

十二、一个非常关键的认知
❗不要做“单标签分类”

FN 很可能是：

variable_renaming + reordering

👉 必须：

multi-label
十三、工程落地优先级
🔴 第一阶段（必须）
FN收集
规则分类（简单规则）
输出标签
🟠 第二阶段
feature extractor
分类统计
🟡 第三阶段
ML classifier
自动数据生成
十四、最终闭环（你要的终极系统）
Benchmark
   ↓
FN 提取
   ↓
FN 分类
   ↓
生成训练数据
   ↓
模型训练
   ↓
重新 Benchmark
十五、最后一句话（非常关键）

FN 不是失败，而是你系统进化的燃料
