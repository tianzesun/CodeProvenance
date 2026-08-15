# Validating the ML classifier on student code — holdout collection guide

**Goal:** enable the AI-detector's ML classifier (currently disabled for
false-positive safety) by validating it on the product's real input: short,
assignment-style student code. The tooling is done; this page is the
**data-acquisition checklist** for the remaining blocker.

## Why a holdout is required

- The classifier was trained on AIGCodeSet (competitive-programming style,
  2,795 AI + 4,541 human Python samples). On short, terse *student* code it
  broke 3 precision regression tests (`test_ai_detector_orchestrator_precision.py`)
  — it flags too many human submissions as AI.
- Enabling it before validating on a student-code distribution would raise
  false-positive rates against real students. That is the one number that
  matters for institutional trust (Turnitin's own docs, and independent
  analyses, treat FP rate as the critical safety metric).

## What to collect

A labelled holdout of student submissions. Each sample is one submission.
Target: **at least 300 AI-authored and 300 human-authored samples**, ideally
≥1,000 total, spanning several courses/assignments so the model sees real
variety.

### Source folders (recommended layout)

```
labelled/
  ai/        (student submissions KNOWN to be AI-generated / heavily assisted)
    assignment-safe-name/
      problem.txt        # optional but recommended: stable problem identity
      submission1.py
      submission2.py
    ...
  human/     (student submissions KNOWN to be human-written, no assistance)
    ...
```

- `ai/` and `human/` determine the label (1 and 0).
- `problem.txt` (one line, any stable id like `hw2-matrix-mult`) becomes the
  grouping key for leakage-free grouped holdout. Same problem must never appear
  in both train and test. When absent, the file stem is used instead.
- Files may be nested under per-assignment subfolders.
- Accepted extensions: `.py .java .c .cpp .h .js .ts .go .rs .rb .php .cs .kt .swift`.

### Alternative: a single CSV or JSONL

Columns: `code` (one submission per row), `label` (`1` = AI, `0` = human),
optional `problem_id`, `llm`, `submission_id`.

```csv
code,label,problem_id,llm
"def sum_list(xs):
    total = 0
    for x in xs:
        total += x
    return total
",0,hw1,STUDENT
```

## Label semantics (important)

- **ai:** the submission is known to be substantially AI-generated or
  heavily AI-assisted. Suspicion is *not* a label — get ground truth
  (e.g. an instructor interview, a known-cheating case, or a batch where the
  student admitted/used a committed AI workflow).
- **human:** the submission is known to be human-written with no AI
  assistance. This is the class you must not smear — the FP rate on it is the
  product's risk number.
- Do NOT include borderline cases in the holdout; ambiguity pollutes the
  validation numbers.

## Whose code to collect

The AI examples should match how students actually use AI in *your* courses:
- direct ChatGPT/Claude/Copilot outputs for the actual assignment prompts,
- tool-assisted solutions, lightly edited,
- (safest) reproduced from real incidents with permission and anonymisation.

Human examples can be past coursework archives (with permission), anonymised.

## Ingest and validate

```bash
# Folder layout or records.csv / records.jsonl
python -m src.backend.engines.ai.build_student_dataset \
    --input path/to/labelled --output data/datasets/student

# Same grouped-holdout methodology as the AIGCodeSet run
python -m src.backend.engines.ai.benchmark_classifier \
    --dataset-dir data/datasets/student
```

Round-trip for sanity (optional): re-ingest the AIGCodeSet with the same tool
and confirm the numbers match `data/datasets/aigcodeset/benchmark_report.json`
— that proves the pipeline and benchmark are identical, so the student numbers
are comparable.

## Decision gate before enabling

Only if the student-holdout run shows **acceptable FP at a usable threshold do
you enable** the classifier:

1. Set `classification.enabled: true` in `src/backend/engines/ai/ai_ensemble_config.yaml`.
2. Re-run `test_ai_detector_orchestrator_precision.py` — the 3 currently-failing
   precision cases must inform whether the classifier needs the new data seeded
   into it, a threshold change, or stays off.
3. Record the before/after numbers in the accuracy page
   (`/api/ai-detect/accuracy`) so the evidence is visible alongside the
   heuristic.
4. PR must include the student-holdout benchmark report JSON.

## Minimum viable scope

If getting 600+ labeled samples is impractical now, a smaller first batch is
still useful: **~60–100 solidly-labelled samples** (the classifier needs ≥10,
but FP confidence needs more). Ship that as a "pilot holdout"; document that
confidence is limited until it reaches ~600.