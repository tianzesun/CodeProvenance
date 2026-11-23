# Overnight report: 23 November 2026

Branch `overnight/2026-11-23` (from `main` at `bbeb12f6`). Unattended run, about 02:00 to 08:30
Toronto time. The goal was release readiness with detection accuracy first. This report covers
what was fixed, what is still open, the risks, and test results before and after. Anything I
did not verify is marked as such.

## Summary

- **8 commits: 7 product fixes and 1 test fix.** Each is small and has its own tests. No
  schema, migration, auth, infra or dependency changes, and no `.env*` file was read.
- **Detection:** added comments (`#`, and `//` in C-family files) no longer hide matched code
  from professors. A UTF-8 byte-order mark (BOM) no longer changes AI or similarity scores, or
  stops starter-code removal.
- **Dashboard:** the dossier's "Download PDF" now gives the dossier (with viva outcomes), not
  the cached originality report. The cases list no longer shows an invented "Risk %".
- **Held back on purpose:** the same comment bug also affects the `coverage` scoring feature.
  The fix is ready, but the shipped learned model was trained on the old values, so it should
  land together with a retrain. See § Held back.
- Thresholds, bands and the model artifact were not changed, as `docs/CURRENT_FOCUS.md` asks.

## Test results, before and after

How the tests were run: the CI settings from `.github/workflows/ci.yml` were reproduced
locally. Postgres 16 ran in a throwaway Docker container on `127.0.0.1:55432`, migrations ran
to head, and `APP_ENV_FILE` pointed at a file that does not exist, so no env file was read.
No Neon or production database was contacted. The shared main-checkout venv was used, and
frontend packages were installed in the worktree with `npm ci` from the existing lockfile,
which was not changed.

| Check | Before (`bbeb12f6`) | After (`HEAD`) |
| --- | --- | --- |
| Unit tests (`pytest tests/unit`) | 2195 passed, **21 failed**, 4 skipped (see note); 2216 / 0 / 4 with the pinned package present | **2224 passed, 0 failed**, 4 skipped (8 new tests), with the pinned package present |
| Integration tests (`tests/integration`, not run in CI) | 35 passed, 3 failed | 36 passed, 2 failed (the two auth-fixture tests, § Still open) |
| `tsc --noEmit` | clean | clean |
| `eslint . --quiet` | clean | clean |
| `next build` | passes (after replacing a symlinked `node_modules`, see note) | passes |
| Ruff on changed files (the CI rule) | — | no new findings in any changed file |
| Ruff, whole `src/backend` (advisory) | 217 findings | 217 findings (unchanged) |
| Student AI false positives (`measure_human_fp.py`, Kaggle, 174 files) | 3.5% at ≥0.40, 3.5% at ≥0.50, 2.9% at ≥0.70 | identical, and no file's score changed (no Kaggle file has a BOM) |

Notes:
- **The 21 unit failures were environmental.** They were all in auth and registration tests.
  `argon2-cffi==25.1.0` is pinned in `requirements.txt` (PR #48) but was missing from the
  shared venv. I installed the pinned version into a private overlay directory
  (`PYTHONPATH`), not into the venv, and all 41 tests in those files then passed. **Action:**
  run `pip install -r requirements.txt` in the main venv.
- **`next build` and a symlinked `node_modules`:** Turbopack refuses a `node_modules` symlink
  that points outside the project, so the build needs a real install.
- **Student FP at ≥0.40:** this run gives 3.5%, and the 6 Nov re-measure gave 5.2%. ≥0.70 agrees
  at 2.9%. I did not chase the difference. Both runs had the CodeGPT checkpoint cached.
- **Integration failures before:** one was a flaky test, fixed (§ Fixed, 8). The other two call
  auth-protected endpoints without signing in (§ Still open).

## Fixed

Detection and evidence first, then dashboard flows.

1. **`7dea59fb` Added `#` comments hid matched code.** The side-by-side highlighter aligned raw
   lines. A copy with `# comment` added to each line, or a comment line between copied lines,
   shared no identical lines with its source. The pair still scored CRITICAL, but the
   professor saw **no matched code**. Blank and comment-only lines are now left out of the
   alignment, and trailing `#` comments are cut. String contents, `#include`-style directives
   and Rust attributes are kept, and reported line numbers are still the original file's.
   This is display only: matching blocks do not feed scores.
2. **`5de73784` Same gap for Java and other C-family files with `//` comments.** In a probe, a
   Java copy scored 0.953 and showed 0 matched blocks; it now shows 1. The cut is limited to
   C-family extensions, so Python floor division (`n // 2`) is never touched.
3. **`df6b1d21` A BOM changed the AI score.** Uploads are decoded as plain `utf-8`, so files
   saved by Notepad and some other Windows editors start with U+FEFF. On 60 real Kaggle student
   files, adding a BOM moved the AI probability by up to **0.16** and pushed **2 of 60** across
   a band (0.813 to 0.649). The orchestrator now drops a leading BOM. CRLF line endings and a
   missing final newline were already score-neutral (measured). Tabs vs spaces move scores by
   up to 0.11 with no band flips; I left that alone because indentation style is a legitimate
   style signal.
4. **`430fa9da` A BOM on one file shifted pair scores.** An unrelated Kaggle pair went from 0.116
   to 0.183 when one side had a BOM. `compare_all_pairs` and `compare_pairs`, and the cohort
   used for shared-code removal, now drop it, and all four BOM combinations score the same. No
   training corpus contains a BOM (Kaggle, ConPlag, IR-Plag and AIGCodeSet checked), so this
   makes live scoring match training rather than introducing skew.
5. **`4c69401b` A starter file saved with a BOM kept its first line.** That line was not
   recognised in the students' copies. Starter sources are now BOM-free too.
6. **`e114c54e` Dossier "Download PDF" gave the wrong document.** It linked to
   `/report/{id}/download-pdf`, the **cached originality report**, so the PDF taken to a hearing
   left out viva outcomes and pair decisions. The link was switched there on 14 Sep (`5f5106d2`).
   The proxy for the dossier PDF route already existed, and on 25 Oct that route was rebuilt
   to always use live data. The button now links to `/dossier/{id}/download-pdf`.
7. **`7fe93475` Cases list showed an invented "Risk %".** The values were derived from priority
   (HIGH = "92%", MEDIUM = "72%") because the list endpoint returns no score, and next to real
   similarity percentages they read as detection scores. The column now says "Priority" and
   shows the priority; sorting is unchanged. The case detail page already labelled this badge
   correctly.
8. **`26ae62a4` (test) Flaky integration test.** `test_v1_analyze_flow` inserted a pair with
   random UUIDs in API order, which violates `ck_no_duplicate_pairs` (a < b) about half the time.
   The app sorts pairs before writing them; the test now does the same, and passed 6 of 6 runs.

## Held back: the same comment bug in the `coverage` score feature

`FeatureExtractor._non_noise_normalized_lines` skips only `//`, `/*` and `*` comment lines. In
the probe a Python copy with trailing `#` comments got `coverage = 0.0`. Its learned score fell
from 1.0 to 0.91, and the legacy fusion hard gate vetoed it ("matching code covers only 0%").
The fix is ready: reuse the highlighter's line filter (patch below, 7 lines). It went into the
scratch evaluation but **not into this branch**, because:

- The shipped learned model was trained on the old coverage values, and coverage has a
  coefficient of about 2.24 logits, so changing the feature without retraining shifts live
  scores away from what the model saw in training.
- Measured on raw labelled pairs, coverage rises for Kaggle copies (47 of 99, mean +0.053)
  **and** for innocent pairs (51 of 193, mean +0.026, up to +0.53 logits for one pair). ConPlag
  (Java/C++) is unchanged: 0 of 911 pairs change. That is effectively a band change, and band
  changes are gated on the student holdout.
- Full-pipeline class evaluation on Kaggle, before and after (`class_evaluation_runner
  --datasets kaggle_student_code`, all 15,051 pairs, base `bbeb12f6` vs base + patch, same
  machine). **Without a retrain the patch makes things worse:**

  | | AUC | Pairs shown ≥0.35 | Recall ≥0.35 / ≥0.65 | Labelled innocent ≥0.65 |
  | --- | ---: | ---: | ---: | ---: |
  | Before | 0.880 | 7.3% | 98.0% / 95.0% | 57.0% |
  | After (patch, no retrain) | 0.867 | 8.6% | 98.0% / 95.0% | 57.5% |

  Of the labelled pairs, 15 of 99 copies and 47 of 193 innocent pairs scored higher, and one
  innocent pair crossed a band. Recall did not move. That confirms holding the patch back
  until a retrain. (Kaggle labels are in-sample and partly wrong, see `docs/BENCHMARK_WORK.md`,
  but the direction is clear.) The baseline AUC of 0.880 is close to the 25 Oct 0.874.

**Recommendation:** apply the patch on the GPU host, retrain learned fusion
(`docs/FUSION_TRAINING_WORKFLOW.md`), then rerun the ConPlag and Kaggle class evaluations
before shipping.

```diff
diff --git a/src/backend/engines/features/feature_extractor.py b/src/backend/engines/features/feature_extractor.py
index 19d7ff04..9217098d 100644
--- a/src/backend/engines/features/feature_extractor.py
+++ b/src/backend/engines/features/feature_extractor.py
@@ -766,17 +766,14 @@ class FeatureExtractor:
         Coverage is measured over these lines so clones that are renamed or
         lightly reformatted still register as overlapping; blank lines and
         comment banners are noise and would otherwise fragment the matching.
+
+        Uses the highlighter's own line filter, so coverage and the matched code
+        shown to professors agree. That filter also drops ``#`` comment lines and
+        trailing ``#`` comments: only ``//`` / ``/*`` / ``*`` lines were skipped
+        before, so a Python copy with a comment added to each line had coverage
+        0.0 and the fusion hard gate vetoed it as "no evidence".
         """
-        normalized = []
-        for line in code.splitlines():
-            normalized_line = highlighter._normalize_identifiers(line.rstrip())
-            compact = normalized_line.replace(" ", "").replace("\t", "")
-            if not compact:
-                continue
-            if compact.startswith(("//", "/*", "*")):
-                continue
-            normalized.append(normalized_line)
-        return normalized
+        return highlighter._code_lines(code.splitlines())[1]
 
     def _counter_cosine(self, left: Counter[str], right: Counter[str]) -> float:
         """Return cosine similarity for sparse counter features."""
```

## Dashboard map

The map was built by a code-reading pass over every `src/frontend/app/**/page.tsx` and the
backend routes. I did not click through every page. The items marked fixed above were checked
by hand.

**Working (frontend call matches a served route and its fields):** upload (files/ZIP, status
polling, courses/assignments), results (pairs, pair review, open a case, share, every report
export), cases list and detail (status, assign, notes, export, share), dossier (JSON, viva
save, and now its PDF), AI detector (run, history, results, false-positive baseline, AI
originality PDF, accuracy page), analytics, reports (evidence packets, semester summary),
courses and admin, settings, benchmark, compare-tools, datasets, error analysis,
false-positive-rate validation, history, login, reset password, verify email.

| Page | Status | Detail |
| --- | --- | --- |
| `/dossier/[id]` Download PDF | **Fixed** | See Fixed, item 6 |
| `/cases` Risk column | **Fixed** | See Fixed, item 7 |
| `/upload` engine weight sliders | Stubbed (by design) | `engine_weights` is sent, but no upload handler accepts it (`server.py:8055`, `8162`). The page already says the learned model uses fixed weights and shows the sliders as inactive, so this matters only if the learned artifact is missing. Not changed. |
| `/cases/[id]` evidence panel | Stubbed | "Detailed evidence isn't shown on this page yet." The sample code is off by default and labelled. Wiring real evidence needs `cases.py` to return the linked pairs (job, files, score), which must respect the new analysis-access checks, so I left it for review. Suggested first step: return `job_id`/`file_a`/`file_b` per linked result only when the viewer has job access, and link each one to `/results/{job}`. |
| `/reports` Department Statistics | Missing (honest) | Marked "Coming soon". |
| `/evidence-view`, `/cluster-detection`, `/historical-fingerprint` | Broken (orphaned) | They call routers that `server.py` never mounts, and `/clusters` and `/alerts` don't exist even in those routers. Nothing in the app links to these pages; they are reachable only by URL. Mounting unaudited routers would expose endpoints without a tenant and access review, so I left them alone. **Recommendation:** remove the pages, or review and mount the routers. |
| Unused code | Info | `components/benchmark/BenchmarkWorkbench.tsx` and `lib/mockIntegrityData.ts` are imported nowhere. |

## Still open

- **Coverage feature fix plus retrain** (above).
- **Two integration tests predate auth enforcement:** `test_professor_journey::
  test_upload_completes_and_reports_exist` and `test_benchmark_tool_errors::
  test_pan_benchmark_reports_tool_errors_with_ground_truth`. Both get a 401 and need a
  signed-in client fixture. I didn't write one because it means creating sessions in tests,
  which is close to the auth code I was asked not to touch. Neither is in CI.
- **AST feature is a "how much shared structure" score, not a similarity:** identical small
  files get `ast = 0.445`, because the score saturates on node counts
  (`ast_multi_layer.compute_ast_layer_scores`). This is consistent with how the model was
  trained (negative coefficient), so it is not a live bug. It would need a retrain to change,
  and is noted only so nobody reads `ast` as a similarity.
- **Very large files (over 10,000 lines):** the chunked path pairs chunks by position. A copy
  with code inserted at the top could misalign and be missed. This was a deliberate
  performance trade-off; I didn't measure it.
- **Possible cross-workspace listing:** `GET /api/admin/users` (`server.py:6412`) returns all
  users with no tenant or organisation filter (confirmed in the code; not run). It is
  admin-only, so this is fine if "admin" means platform operator. If workspace admins are meant
  to see only their own workspace, it leaks the user list across workspaces. This is
  auth-adjacent, so I didn't change it. Please decide and review.
- **Shared Redis:** the benchmark runs first wrote UniXcoder embedding cache entries to the
  local dev Redis (db 0, `integritydesk:unixcoder:*`, about 200 keys, keyed by file content).
  Those values are what the app would compute anyway. Later runs used db 15.

## Risks of the changes on this branch

- Fixes 1, 2 and 5 change what is highlighted, not scores. Fix 2 relies on file extensions, so a
  C-family file with an unusual extension just keeps the old behaviour.
- Fixes 3 and 4 change scores only for files that start with a BOM; none of the training or
  benchmark corpora do.
- Fix 6 depends on `/dossier/{id}/download-pdf` producing a PDF in each deployment. Without
  weasyprint it returns print-ready HTML, which the unit test covers, but I didn't render a real
  PDF in a browser.
- No change was exercised end to end in a running app (backend plus Next) tonight. The evidence
  is unit and integration tests, probes through the production `BatchDetectionService` and
  `AIDetectionOrchestrator`, a type check and a production build.
