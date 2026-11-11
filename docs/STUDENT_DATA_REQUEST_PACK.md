# Student-Code Data Request Pack

**One-page ask for course teams** — what IntegrityDesk needs to finish **both** AI-detection
validation and **plagiarism-checker recall validation**, and exactly how to hand it over.
Full methodology lives in `docs/AI_HOLDOUT_COLLECTION.md` (AI detection) and
`docs/BENCHMARK_WORK.md` (plagiarism engine benchmarking); this page is the version
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

The plagiarism checker was measured on ConPlag (911 human-annotated contest
pairs, November 2026; `docs/BENCHMARK_WORK.md` § ConPlag): **2.3%** of innocent
pairs reach the high band (0.65) and **64%** of copies reach the review band
(0.35), on par with JPlag and Dolos. That is contest code, not coursework, so
these numbers still need confirming on your students' code.

---

## Part 2 — Plagiarism-checker recall holdout

### What we need

Professors see a pair when it reaches the **review** band (0.35) and are told it
is a priority at the **high** band (0.65). On contest data (ConPlag) few innocent
pairs reach the high band, but about a third of confirmed copies never reach
review: copies rewritten inside the student's own scaffolding look like
independent work to every engine, and to JPlag and Dolos. Whether that holds for
coursework has only been tested on synthetic and contest data (IR-Plag, ConPlag,
Kaggle). We need a **labelled holdout from real classes** to close this gap.

Unlike the AI-detection holdout (which labels _single submissions_), the
plagiarism holdout labels **pairs** of submissions with a known ground truth.

### What to collect

| Pair type                                                         | Count (pilot) | Count (target) | Ground-truth requirement                                                                       |
| ----------------------------------------------------------------- | ------------: | -------------: | ---------------------------------------------------------------------------------------------- |
| Known **plagiarism** (copy, rename, restructure, paraphrase)      |           ~50 |           ≥300 | Instructor-verified copy/paste, admitted collaboration, or a confirmed paraphrase case         |
| Known **disguised** plagiarism (a subset of the row above)        |          ~10 |            ≥50 | As above, where the copied logic was rewritten or wrapped in the student's own helpers/scaffolding |
| Known **clean** (different students, same assignment, no copying) |           ~50 |           ≥300 | Viva-confirmed independent work, or assignments with no shared code beyond starter scaffolding |

**No borderline cases.** "Maybe they helped each other" is not a label —
ambiguity pollutes the recall measurement.

**Send whole classes.** Include *every* submission to each assignment, not only
the labelled ones. Unlabelled submissions are never used as labels; they let us
measure what a professor sees: how much of a real class lands in each band.
Mark disguised cases with `disguised` in the `notes` column.

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

Please use the folder layout above: the evaluation command reads it directly.
(A single CSV with `file_a,file_b,label,problem_id,notes` is not read by the
command; we would convert it by hand.)

### What happens with the data

1. Scored locally (no cloud upload), one class per assignment folder:
   `python -m src.backend.benchmark.runners.class_evaluation_runner --student-holdout plagiarism_labelled/`
2. Every pair in each class goes through the production scoring path, exactly as
   a professor's check would. The report gives, at the review (0.35) and high
   (0.65) bands: the share of the class shown, copies caught, and clean pairs
   flagged, plus each labelled pair's score and the engines behind it. None of
   this data is in the model's training set, so it is a true holdout.
3. Decision gate: if copies are caught and clean pairs stay out of the high band,
   the bands stay as they are; if not, they are reviewed on _data_, not
   guesswork — per `CURRENT_FOCUS.md`.
4. The dataset stays on the institution's machine; nothing is re-shared.

### Why this matters now

On contest data, false-accusation risk is low, but about a third of confirmed
copies never reach the review band. We do not yet know how many **real
coursework copies** are missed the same way, especially disguised ones. That is
the single biggest unmeasured accuracy risk in the plagiarism checker.
