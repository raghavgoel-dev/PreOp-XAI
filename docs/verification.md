# Implementation verification - 17 October 2026

## Outcome

The complete persisted synthetic campaign passed on source commit
`a0a75fcb6054836870c3d060a5267b15fbbca8db`. No source/config/lock changes were made
during that final campaign. The real EPIC raw audit also passed.

This proves software behavior, not clinical endpoint approval or actual study
performance. All reported demonstration results use artificial patients.
Real-data modeling remains blocked pending the specified qualified reviews.

## Success criteria and actual invocations

| Scenario | Binary observable | Result and evidence |
|---|---|---|
| `uv run --locked preop-xai demo --output artifacts/demo` | Exit 0; both endpoints finish frozen evaluation and report; completion JSON says passed | PASS. `artifacts/demo/demo_complete.json`, `report.md`, both endpoint `evaluation_complete.json`; terminal session `bash_16` exited 0 |
| `uv run --locked preop-xai audit --config configs/study.yaml` | Exit 0 and actual-source audit JSON/inventories/checksums exist | PASS. `artifacts/study/audit/audit.json`; terminal session `bash_18` exited 0 |
| `uv run --locked preop-xai train --endpoint mortality --config configs/study.yaml` | Exit 1 before data/model access; clinical-review requirement | PASS. Actual stderr starts `Clinical review required: verify age, ASA, anesthesia boundary...` |
| `uv run --locked preop-xai train --endpoint mortality --config artifacts/demo/study.yaml` | Exit 1 before mutation of the frozen experiment | PASS. Actual stderr: `Analysis is frozen. Use a new output directory for a protocol amendment.` |
| `uv run --locked preop-xai evaluate --endpoint mortality --partition test --config artifacts/demo/study.yaml` | Exit 1 on repeated test unlock | PASS. Actual stderr: `Test evaluation already unlocked; reuse frozen outputs, not reruns.` |
| `uv run --locked pytest -q` | All scientific regressions pass, none skipped | PASS. 28 passed, 3 warnings, 6.69 seconds |
| `uv run --locked ruff check .` | Exit 0 | PASS. `All checks passed!` |
| `uv run --locked ruff format --check .` | Exit 0, no formatting changes needed | PASS. `31 files already formatted` |
| `uv tool run basedpyright --pythonpath .venv/Scripts/python.exe --level error src/preop_xai` | Exit 0, no semantic errors | PASS. `0 errors, 0 warnings, 0 notes` |

The final combined checks ran in terminal session `bash_17`, exit 0. The built-in
LSP tool retained a stale missing-executable status after installation; the
installed standalone server supplied the successful semantic diagnostics.
The three test warnings are unsuppressed third-party SHAP/Matplotlib color-map
deprecations, not skipped or weakened checks.

## Synthetic pipeline evidence

The demonstration generates 600 artificial patients. Its fixed assignment has
420 training, 90 validation and 90 test patients. Both endpoints use the same
patient assignment and both model families use identical observations within
each endpoint.

The command executes the actual persisted workflow: raw adapters/audit, cohort,
labels, features, leakage checks, saved partitions, full 3-candidate LR and
12-candidate XGBoost searches, validation calibration/threshold, explanations,
stability, hash seal, single test evaluation and report. It does not substitute
the quick-candidate smoke mode for the final searches.

For **each** of `artifacts/demo/mortality/` and `artifacts/demo/respiratory/`:

- `performance.csv` contains four finite rows: LR/XGBoost, raw/calibrated.
- `metrics.json` records `bootstrap_resamples: 1000`, calibration/bin counts,
  threshold performance, prevalence reference and undefined-resample counts.
- `intervals.csv` records metric and paired model-difference intervals.
- `explain.json` records raw and calibrated-logit additivity as true for both
  models, the fixed 64-patient training background and SHAP 0.51.0 settings.
- `stability.json` records ten successful refits for each model, paired draws
  and 45 pairwise stability comparisons per model: forty refits overall.
- `selection.json`, `lr_coefficients.csv`, `models.joblib` and `xgboost.json`
  preserve fitted choices, encodings, transformations and native tree models.
- `freeze.json` identifies commit `a0a75fc` and the sealed input hashes.
- `evaluation_started.json` and `evaluation_complete.json` record the single
  successful test unlock.

The respiratory demonstration emitted nonpositive recalibration-slope warnings
for both models. These are retained as reliability failures, not hidden or
used to retune the test predictions.

The top-level manifest records observed Python/software/OS/hardware, seed,
source/config/lock hashes and raw-input checksums. Patient-level arrays,
partitions and models are private ignored artifacts, not Git deliverables.

## Visual inspection

Opened actual PNG files using the image-capable `read` tool:

- `artifacts/demo/mortality/figures/lr_global.png`
- `artifacts/demo/mortality/figures/xgboost_beeswarm.png`
- `artifacts/demo/mortality/private/xgboost_local_FN.png`
- `artifacts/demo/mortality/calibration.png`

PASS: visible plotted data, readable/unclipped labels, no overlap or missing
glyphs, and the intended raw/calibrated-logit and probability axes. The report
indexes aggregate figures; individual local figures remain private.

## Actual-source audit

The actual EPIC audit reproduced 65,728 information rows, 39,685 distinct MRNs,
64,354 distinct operation identifiers and 29,079,344 laboratory rows. It found
1,374 duplicated operation keys, ten with conflicting records. These are raw
source counts, not final cohort size or endpoint event counts.

Literal `None` is preserved, and schemas/coding/lab inventories plus timing
flags are available for review. `data_dictionary.md` records aggregate findings.
The local lab table has no result-release timestamp. No review flag or source
mapping was changed to claim that availability or respiratory semantics had
been clinically verified.

## Regression findings and self-review

The checks caught and corrected a read-only pandas index during unknown-label
assignment, float32 arithmetic in an independent SHAP expectation, and inherited
nonserializable cohort exclusion metadata in Parquet features. A running
campaign also correctly rejected test access when a source hash changed.
That incomplete campaign was removed; the final committed-source campaign
completed without changing or bypassing the seal.

Self-review confirmed: index selection precedes outcome availability; missing
ASA/discharge do not select a later operation; ambiguous first timestamps are
quarantined; source labels/identifiers cannot enter the feature boundary;
transforms are fitted within training folds; calibration cannot refit base
models; both bootstraps preserve pairing; SHAP is additive on log-odds, not
probability; all sensitive outputs stay ignored.

HEAVY tier held because this introduced scientific data/model contracts.
No `ulw-plan` review gate was triggered; this is recorded self-review, not
independent reviewer approval. VitalDB, a web application and extra model
families remain outside the core scope.

## Cleanup and preservation

All campaign/check/audit command sessions exited; no browser, server, container
or listening-port resource was started. Failed-worker QA files and superseded
synthetic campaign directories were removed with absence checks.

The project environment, authorized raw data and final ignored audit/demo
artifacts are intentional deliverables. Shared caches are not deleted.
Final run-root/cache teardown and Git-state receipts are recorded in
`completion-log.md`.
