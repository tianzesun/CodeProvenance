# Student-Code Data Request Pack

**One-page ask for course teams** — what IntegrityDesk needs to finish AI-detection
validation, and exactly how to hand it over. Full methodology lives in
`docs/AI_HOLDOUT_COLLECTION.md`; this page is the version to send to an instructor.

---

## What we are asking for

Two classes of **real student submissions** from past coursework, anonymised:

| Class | Count (pilot) | Count (target) | Ground-truth requirement |
| --- | ---: | ---: | --- |
| Known **AI-authored** | ~30 | ≥300 | Admission, verified incident, or a committed AI workflow (e.g. assignment run where AI use was the instruction) |
| Known **human-written** | ~30 | ≥300 | No-AI attestation, viva-confirmed authorship, or pre-2022 course archive |

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
(PoolC). The student holdout extends this from "human code" to "*your* students'
code, with known AI cases".
