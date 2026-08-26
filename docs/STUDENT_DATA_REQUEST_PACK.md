# Student-Code Data Request Pack

**One-page ask for course teams** — what IntegrityDesk needs to finish **both** AI-detection
validation and **plagiarism-checker recall validation**, and exactly how to hand it over.
Full methodology lives in `docs/AI_HOLDOUT_COLLECTION.md` (AI detection) and
`docs/BENCHMARK_SYSTEM.md` (plagiarism engine benchmarking); this page is the version
to send to an instructor.

---

## What we are asking for

Two classes of **real student submissions** from past coursework, anonymised:

| Class                   | Count (pilot) | Count (target) | Ground-truth requirement                                                                                        |
| ----------------------- | ------------: | -------------: | --------------------------------------------------------------------------------------------------------------- |
| Known **AI-authored**   |           ~30 |           ≥300 | Admission, verified incident, or a committed AI workflow (e.g. assignment run where AI use was the instruction) |
| Known **human-written** |           ~30 |           ≥300 | No-AI attestation, viva-confirmed authorship, or pre-2022 course archive                                        |

**No borderline cases.** "Seemed AI-ish" is not a label — ambiguous submissions
pollute the one number we care about: the false-positive rate on real students.

## Why we need it

The ML classifier scores AUC 0.66 on public benchmarks but was trained on
competitive-programming-style code. Before it can be enabled by default we must
measure — on real classroom code — how often it wrongly flags a human student.
That FP rate is the product's trust number; we will not enable on assumption.

## How to package it (folder layout — preferred)

```
labelled/
  ai/                          # known AI-authored submissions
    hw2-matrix-mult/           # one folder per assignment
      problem.txt              # one line: a stable id, e.g. "hw2-matrix-mult"
      submission01.py
      submission02.py
  human/                       # known human-written submissions
    hw2-matrix-mult/
      problem.txt
      submission17.py
```

- The `problem.txt` id is the grouping key: the same problem never appears in
  both training and test folds during validation. Keep it consistent.
- Accepted file types: `.py .java .c .cpp .h .js .ts .go .rs .rb .php .cs .kt .swift`
- Alternatively a single CSV/JSONL with columns `code,label,problem_id,llm`.

## Anonymisation checklist (before sending)

- [ ] Remove student names, emails, IDs and any path or username traces in code comments
- [ ] Replace identifiers with stable pseudonyms if cross-referencing is needed later
- [ ] Keep the assignment/problem grouping intact (needed for leakage-free validation)
- [ ] Confirm course policy / consent covers sharing submissions for tool validation

## What happens with the data

1. Ingested locally with one command (no cloud upload):
   `python -m src.backend.engines.ai.build_student_dataset --input labelled/ --output data/datasets/student`
2. The grouped-holdout benchmark runs and produces a report JSON.
3. Decision gate: the ML classifier is enabled **only** if FP on the human class
   is acceptable at a usable threshold; before/after numbers go on the accuracy
   page (`/api/ai-detect/accuracy`) for anyone to inspect.
4. The dataset stays on the institution's machine; nothing is re-shared.

## Baseline already measured (no new data needed)

The live detector was run over real human code already on disk — see
`docs/HUMAN_FP_BASELINE.md` for current false-positive rates on novice student
Python (Kaggle corpus), student Java (IR-Plag originals), and community Python
(PoolC). The student holdout extends this from "human code" to "_your_ students'
code, with known AI cases".

The plagiarism checker's **false-positive** rate was likewise measured on the
same Kaggle corpus (174 submissions, 14,706 pairs) — see
`reports/human_fp/plagiarism_fp_report_20260825.md`: **0.96% FPR at the production
threshold (0.95)**, well within the 4–5% safe target.

---

## Part 2 — Plagiarism-checker recall holdout

### What we need

The plagiarism engine's **false-positive** rate is now measured and safe (~1% at
threshold 0.95 on real student Python). But **recall** — does it actually catch
real plagiarism at that conservative threshold? — has only been validated on
synthetic/competitive-programming data (IR-Plag, ConPlag). We need a **labelled
holdout of real student plagiarism pairs** to close this gap.

Unlike the AI-detection holdout (which labels _single submissions_), the
plagiarism holdout labels **pairs** of submissions with a known ground truth.

### What to collect

| Pair type                                                         | Count (pilot) | Count (target) | Ground-truth requirement                                                                       |
| ----------------------------------------------------------------- | ------------: | -------------: | ---------------------------------------------------------------------------------------------- |
| Known **plagiarism** (copy, rename, restructure, paraphrase)      |           ~50 |           ≥300 | Instructor-verified copy/paste, admitted collaboration, or a confirmed paraphrase case         |
| Known **clean** (different students, same assignment, no copying) |           ~50 |           ≥300 | Viva-confirmed independent work, or assignments with no shared code beyond starter scaffolding |

**No borderline cases.** "Maybe they helped each other" is not a label —
ambiguity pollutes the recall measurement.

### How to package it

```
plagiarism_labelled/
  hw1-data-structures/                # one folder per assignment
    problem.txt                       # stable id, e.g. "hw1-data-structures"
    pairs.csv                         # file_a,file_b,label,notes
    submissions/
      student001.py
      student002.py
      student003.java
      ...
```

The `pairs.csv` columns:

| Column   | Values                          | Notes                                                          |
| -------- | ------------------------------- | -------------------------------------------------------------- |
| `file_a` | filename                        | Must exist under `submissions/`                                |
| `file_b` | filename                        | Must exist under `submissions/`                                |
| `label`  | `1` (plagiarism) or `0` (clean) | Ground truth                                                   |
| `notes`  | free text                       | Source of truth (e.g. "viva-confirmed", "instructor-admitted") |

The `problem.txt` id is the grouping key for leakage-free grouped holdout —
the same problem never appears in both training and test folds.

Alternatively, a single CSV at the root with columns
`file_a,file_b,label,problem_id,notes` and a `submissions/` directory alongside it.

### What happens with the data

1. Ingested locally (no cloud upload):
   `python -m src.backend.benchmark.runners.learned_fusion_training_runner --student-holdout plagiarism_labelled/`
2. Runs the production `BatchDetectionService` (with the learned-fusion model) on
   the labeled pairs in a grouped-holdout cross-validation, producing a recall /
   precision report.
3. Decision gate: if recall is acceptable at the production threshold (0.95), the
   band stays as-is; if recall is too low, the threshold/bands are reviewed on
   _data_, not guesswork — per `CURRENT_FOCUS.md`.
4. The dataset stays on the institution's machine; nothing is re-shared.

### Why this matters now

The FP baseline proved false-accusation risk is controlled. But the 0.95
threshold is highly conservative — 97.5% of clean pairs score below 0.50. We do
not yet know how many **real plagiarism cases** score below 0.95 and are
therefore missed. That is the recall ceiling — and it is the single biggest
unmeasured accuracy risk in the plagiarism checker.
