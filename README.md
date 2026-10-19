# PreOp-XAI

Reproducible research software for comparing regularized Logistic Regression
and XGBoost using preanesthetic MOVER EPIC information. The implementation follows
the project plan and research synopsis dated 17 October 2026.

## Setup

Install `uv`, then run from this repository:

```sh
uv sync --locked
uv run --locked python --version
uv run --locked preop-xai --help
```

Python is pinned to the observed `3.11.9` release. `uv.lock` freezes dependencies.
The full laboratory source is scanned lazily; no waveform files or GPU are needed.

## Run a complete synthetic demonstration

```sh
uv run --locked preop-xai demo --output artifacts/demo
```

This generates 600 artificial patients and exercises the same persisted stages,
full training-CV searches, both endpoint pipelines, calibration, grouped SHAP,
ten paired bootstrap refits per model/endpoint, genuine hash-based experiment
freeze, and 1,000 paired evaluation bootstraps. Outputs are ignored by Git.
The report is `artifacts/demo/report.md`. These are software checks, not clinical
results. Nonpositive calibration slopes are reported, never optimized away.
Use a new output directory for a new campaign; existing evidence is not overwritten.

Execution success is separate from predictive reliability. Read the
[measured calibration diagnosis and readiness audit](docs/reliability-audit.md)
and [saved-model inference contract](docs/inference.md). New campaigns produce
`status.json`, endpoint `calibration.json`, and versioned `bundle.json` metadata.
The `predict` command loads fitted preprocessing and models without retraining;
invalid calibration is rejected unless raw-only research output is explicitly
requested. Synthetic results and threshold classifications are not clinical advice.

## Authorized MOVER EPIC analysis

Place authorized CSV files in `data/EPIC_EMR/EMR`, or copy
`configs/local.example.yaml` to ignored `configs/local.yaml` and configure paths.
Run the audit before changing review flags:

```sh
uv run --locked preop-xai audit --config configs/study.yaml
```

The shipped configuration deliberately blocks clinical modeling. Reviewers must
verify age, ASA, anesthesia boundaries, static predictor provenance, outcome
dispositions and hospitalization linkage and record reviewer/evidence fields.
Review exact lab identities, specimen compatibility, unit conversions and bounds
in `feature_map.yaml`. The local lab source has collection times but no release
time: either provide verified release timestamps or explicitly adopt/disclose
the 24-hour collection-time proxy. Do not describe the latter as fully verified
availability.

Respiratory is disabled until postoperative meaning, explicit negative
assessments, assessability and event adequacy are established by qualified review.
The default title is therefore mortality-only. No other morbidity endpoint is
silently substituted.

Once the reviews and mappings are genuinely complete:

```sh
uv run --locked preop-xai build-cohort --config configs/local.yaml
uv run --locked preop-xai build-labels --config configs/local.yaml
uv run --locked preop-xai build-features --config configs/local.yaml
uv run --locked preop-xai audit-leakage --config configs/local.yaml
uv run --locked preop-xai split --config configs/local.yaml
uv run --locked preop-xai train --endpoint mortality --config configs/local.yaml
uv run --locked preop-xai calibrate --endpoint mortality --config configs/local.yaml
uv run --locked preop-xai explain --endpoint mortality --partition validation --config configs/local.yaml
uv run --locked preop-xai stability --endpoint mortality --config configs/local.yaml
uv run --locked preop-xai freeze --endpoint mortality --config configs/local.yaml
uv run --locked preop-xai evaluate --endpoint mortality --partition test --config configs/local.yaml
uv run --locked preop-xai report --config configs/local.yaml
```

If both endpoints are supported, complete development/explanation/stability
stages for both **before freezing either endpoint**, then freeze and evaluate
each separately. Development commands cannot mutate frozen experiments.
Evaluation unlocks once; reuse saved outputs instead of repeatedly testing.
Source, lockfile, configuration and analysis-data changes invalidate the freeze.
Any protocol amendment needs a new output directory and documented rationale.

## Checks

```sh
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Tests protect indexing, unknown labels, exact respiratory strings, patient
independence, lab boundaries/units, fold-local preprocessing, SHAP additivity,
review gates and frozen test access. Final tables and figures are script-generated.

## Research record

- [Complete codebase, architecture, configuration, and CLI guide](docs/codebase-guide.md)
- [Actual MOVER EPIC run checks and research-readiness blockers](docs/real-data-verification.md)
- [Protocol](docs/protocol.md)
- [Data dictionary and local audit](docs/data_dictionary.md)
- [Data implementation](docs/data-implementation.md)
- [Models and statistics](docs/model-implementation.md)
- [Explanations and stability](docs/explanation-implementation.md)
- [Task completion record](docs/completion-log.md)
- [Verification evidence](docs/verification.md)
- [Decisions and deviations](docs/deviations.md)

Raw data, identifiers, partitions, models, predictions and patient explanations
stay in authorized, ignored storage. Aggregate artifacts are not automatically
approved for publication. Individually shifted dates do not support genuine
calendar-temporal validation; retrospective internal validation and SHAP do not
establish causality, clinical readiness or treatment effects. VitalDB is outside
the core campaign.
