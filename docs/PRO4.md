一、总体设计原则（必须遵守）
1️⃣ 统一语义，而不是统一格式

不同工具输出：

JPlag → XML / JSON（结构化）
MOSS → HTML（半结构化）

👉 你的目标不是“解析它们”，而是：

把它们转成同一个“语义模型”

2️⃣ 所有工具必须输出同一个结构（强制）

定义标准：

{
  "tool": "jplag",
  "dataset": "bigclonebench",
  "pairs": [
    {
      "file1": "...",
      "file2": "...",
      "similarity": 0.85,
      "matches": [...]
    }
  ]
}
3️⃣ 路径标准化（非常容易踩坑）

必须统一：

student1/A.java
student2/A.java

而不是：

/home/tsun/data/student1/A.java

👉 否则 evaluator 会错判

二、解析架构设计（标准模块）
parsers/
├── base_parser.py        # 抽象类（必须）
├── jplag_parser.py       # JPlag实现
├── moss_parser.py        # MOSS实现
└── utils.py              # 公共处理
三、Base Parser（统一接口设计）

这是最关键的设计。

标准接口（逻辑定义）
class BaseParser:

    def parse(self, input_path) -> StandardOutput:
        """
        输入：工具输出目录/文件
        输出：统一格式（StandardOutput）
        """

    def normalize_path(self, path) -> str:
        """
        统一路径格式
        """

    def extract_pairs(self, raw_data):
        """
        提取 file1, file2, similarity
        """
四、JPlag 输出解析规范
1️⃣ JPlag 输出结构（典型）

JPlag通常输出：

results.xml
或 JSON（新版本）

XML结构类似：

<match>
  <file1>student1/A.java</file1>
  <file2>student2/A.java</file2>
  <similarity>0.87</similarity>
</match>
2️⃣ 解析规则（必须统一）
字段映射
JPlag	标准
file1	file1
file2	file2
similarity	similarity
3️⃣ 注意事项（非常重要）
⚠️ 坑1：路径包含绝对路径
/home/user/data/student1/A.java

👉 必须转：

student1/A.java
⚠️ 坑2：重复 pair

JPlag 可能输出：

A-B
B-A

👉 必须去重：

(A,B) == (B,A)
⚠️ 坑3：相似度范围

JPlag：

0–100

👉 必须归一化：

similarity / 100
4️⃣ 输出示例
{
  "tool": "jplag",
  "pairs": [
    {
      "file1": "student1/A.java",
      "file2": "student2/A.java",
      "similarity": 0.87
    }
  ]
}
五、MOSS 输出解析规范（难点）🔥
1️⃣ MOSS 输出特点

MOSS 输出：

HTML 页面
无标准 API
每一行是一个 match
2️⃣ HTML结构（简化）
<tr>
  <td>student1/A.java (85%)</td>
  <td>student2/A.java (87%)</td>
</tr>
What is this?
3️⃣ 解析规则（核心）
Step 1：提取文件名
student1/A.java
student2/A.java
Step 2：提取相似度
85%, 87%

👉 必须统一为：

similarity = min(85, 87) / 100
❗ 为什么用 min？

因为：

MOSS 是非对称的
A 对 B ≠ B 对 A

👉 使用 min 是学术上更保守、更稳定的做法

4️⃣ 去重规则（必须）

同样：

(A,B) == (B,A)
5️⃣ 输出示例
{
  "tool": "moss",
  "pairs": [
    {
      "file1": "student1/A.java",
      "file2": "student2/A.java",
      "similarity": 0.85
    }
  ]
}
六、统一后处理（Critical Step）

所有 parser 输出后，必须经过：

1️⃣ Pair Canonicalization（标准化）
(file1, file2) → sorted tuple

例如：

(A, B) → (A, B)
(B, A) → (A, B)
2️⃣ 去重
只保留最高 similarity
3️⃣ 过滤（可选）
similarity < threshold → 删除
七、错误处理（必须设计）
1️⃣ 空输出
if no pairs:
    return []
2️⃣ 文件不存在

必须 fail fast：

raise ParserError("Missing output file")
3️⃣ HTML结构变化（MOSS）

👉 必须：

try:
    parse
except:
    fallback regex
八、最终统一接口（非常关键）

你最终应该有一个统一调用方式：

parse_tool_output(tool_name, path) → StandardOutput
九、一个现实中的“致命错误”（必须避免）

很多人会这样做：

❌ 用不同工具的“原始相似度”直接对比

这是错误的。

为什么？
JPlag → token-based
MOSS → fingerprint-based

👉 相似度本身不可比

正确做法：

✅ 用 threshold → 转二分类 → 再算 F1

十、总结一句话（核心思想）

Parser 的职责不是“读文件”，而是“消除工具差异”
