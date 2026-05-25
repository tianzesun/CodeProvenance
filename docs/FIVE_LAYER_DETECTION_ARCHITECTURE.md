# Five-Layer Detection Architecture

IntegrityDesk should rank cases by professor review value, not by a raw average similarity score.

## Layer A: Token / Winnowing Engine

Purpose: catch direct copying, identifier renaming, formatting changes, and literal edits.

Pipeline:
- Normalize code
- Remove comments
- Remove whitespace
- Normalize identifiers
- Normalize literals
- Tokenize
- Build k-grams
- Select winnowing fingerprints
- Compare fingerprints

This is the baseline MOSS/Dolos-style layer.

## Layer B: AST Structure Engine

Purpose: catch structural similarity when text differs.

Pipeline:
- Parse code into AST
- Normalize identifiers and literals
- Remove boilerplate nodes
- Extract AST paths, subtree hashes, and AST shingles
- Compare tree/subtree structure

Professor-facing evidence must include:
- Same function decomposition
- Same branch order
- Same loop nesting
- Same exception handling
- Same helper function pattern

## Layer C: Program Dependence / Control Flow Engine

Purpose: detect semantic-preserving rewrites that traditional token tools miss.

Signals:
- CFG similarity
- DFG similarity
- Call graph similarity
- Input-output behavior similarity
- Edge-case behavior similarity

Targets:
- Variable/function renames
- Function splitting or merging
- Statement reordering
- `while` rewritten as `for`
- AI-assisted rewrite attacks

## Layer D: Runtime Behavior Engine

Purpose: produce evidence professors trust.

Generate:
- Normal cases
- Edge cases
- Random cases
- Property-based tests
- Mutation tests

Compare:
- Same wrong outputs
- Same edge-case bugs
- Same exception behavior
- Same timeout pattern
- Same floating-point error

Same rare bugs should receive a strong rank boost.

## Layer E: Historical / Classroom Context Engine

Purpose: reduce false positives and catch prior-term reuse.

Signals:
- Starter code database
- Previous semester database
- Student historical coding fingerprint
- Assignment template detector
- Common solution detector
- Known public snippet detector

Rules:
- High starter-code overlap lowers risk.
- Common solution cluster lowers risk.
- Shared rare error raises risk.
- Previous-term structural match raises risk.
- Student style shift is supporting evidence only.

## Evidence Fusion Ranker

Do not use:

```text
final_score = 0.4 token + 0.3 ast + 0.3 embedding
```

Use:
- Rule-based guardrails in front of scoring
- Learned ranker behind the guardrails
- Queue objective optimized for top-k professor review

Feature payload:
- `token_similarity`
- `ast_similarity`
- `cfg_similarity`
- `dfg_similarity`
- `runtime_bug_similarity`
- `identifier_rename_score`
- `boilerplate_overlap`
- `starter_code_overlap`
- `previous_term_match`
- `rare_pattern_score`
- `common_solution_score`
- `student_style_shift`

Training objectives:
- Precision@10
- Precision@20
- NDCG@20
- Recall at fixed false-positive rate

The product goal is not "code looks similar." The goal is:

> This case is worth a professor's time.

## MVP Route

Highest-value first implementation:
1. Starter code removal
2. Identifier/literal normalization
3. AST subtree hashing
4. Same wrong-answer / same-bug detection
5. Precision@20 ranking

Code entry points:
- `src/backend/engines/mvp/starter_code.py`
- `src/backend/engines/mvp/normalization.py`
- `src/backend/engines/mvp/ast_subtree.py`
- `src/backend/engines/mvp/same_bug.py`
- `src/backend/engines/mvp/precision_ranking.py`
- `src/backend/engines/mvp/pipeline.py`

The MVP pipeline emits ranker-ready features:
- `fingerprint`
- `winnowing`
- `ast`
- `runtime_bug_similarity`
- `edge_case_behavior_similarity`
- `identifier_rename_score`
- `starter_code_overlap`

## Accuracy Proof System

Before release, IntegrityDesk must prove that ranked cases are worth professor
time. Do not certify the platform with F1 alone.

Benchmark categories:
- Direct copy
- Renamed identifiers
- Reordered functions
- Split or merged functions
- `while` to `for` rewrite
- AI rewrite
- Same-bug cases
- Previous-semester reuse
- Starter-code hard negatives
- Common-solution hard negatives

Required comparison:
- MOSS
- JPlag
- Dolos
- Layer A only
- Layer A + B
- Layer A + B + C
- Layer A + B + C + D
- Full system with Layer E
- Full system without guardrails

Release gates:
- Precision@10 >= 0.90
- Precision@20 >= 0.85
- Hard-negative false positive rate <= 0.03
- Starter-code false positives reduced by >= 0.70
- Same-bug recall >= 0.85
- Previous-term recall >= 0.90
- Embedding-only high-risk count == 0

Shadow mode:
- Run on real course data for 4-8 weeks.
- Do not affect students.
- Ask professors and TAs to label each Top-N case as worth reviewing or not.
- Track median review time and confirmation/dismissal decisions.
- Use the feedback to calibrate the ranker before production release.
