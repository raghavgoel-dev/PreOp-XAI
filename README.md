# PreOp-XAI

Research pipeline comparing Logistic Regression and XGBoost for preoperative
mortality and respiratory risk using MOVER EPIC data.

Includes patient-independent splits, validation-only calibration, grouped SHAP,
bootstrap stability, saved-model prediction, and hash-sealed evaluation.
Read-only result exports add performance tables, ROC/PR curves, calibration plots,
confusion matrices, endpoint comparisons, stability figures, and provenance.
The DOCX importer separately archives the report's original illustrative tables
and figures; these are not measured model results.

## Setup and run

Prerequisites: Git and `uv`. Python **3.11.9** is pinned; dependencies are locked
in `uv.lock`. No GPU or clinical dataset is needed for the demo.

1. **Get the project** (skip if already cloned).

   ```sh
   git clone https://github.com/raghavgoel-dev/PreOp-XAI.git
   cd PreOp-XAI
   ```

2. **Install the environment** from the project directory.

   ```sh
   uv sync --locked
   ```

3. **Run the synthetic pipeline** for both endpoints.

   ```sh
   uv run --locked preop-xai demo --output artifacts/demo
   ```

   This trains models, calibrates, explains, checks stability, and evaluates
   600 artificial patients. Open `artifacts/demo/report.md` for the results.
   The full run includes bootstrap refits, not just a quick prediction.

4. **Export the saved results** without retraining or reevaluating.

   ```sh
   uv run --locked preop-xai export-results --source artifacts/demo --output artifacts/demo-results
   ```

   Open `artifacts/demo-results/report.md`; `report_artifacts.json` indexes
   the aggregate tables and figures. Export verifies the campaign seal.

Use fresh output directories for repeat runs and update the paths together.
Data, models, and generated artifacts are excluded from Git.

## Predict with a saved model

After the demo, use the included artificial feature CSV:

```sh
uv run --locked preop-xai predict --bundle artifacts/demo/mortality --model lr --input docs/examples/new-patients.csv --output artifacts/demo/lr-new.csv
```

Use `--model xgboost` for XGBoost and a fresh output CSV for each run.
Invalid calibration is rejected; `--research-only` explicitly requests raw-only
diagnostics. See [input schema and bundle requirements](docs/inference.md).

## Real data and report references

For authorized MOVER data, copy `configs/local.example.yaml` to
`configs/local.yaml`, set paths, then run
`uv run --locked preop-xai audit --config configs/local.yaml`.
Clinical modeling stays blocked until mappings and clinical/timing reviews are
complete; real-data respiratory analysis is disabled by default.
Follow the [detailed setup and stage guide](docs/codebase-guide.md).

The [export and DOCX-import workflow](docs/workflow.md) covers reference archival
and the last session's local outputs. Those outputs are not included in a clone.
The completed export fixture is constructed software evidence, not clinical
results. Historical seal mismatches must not be bypassed.

**Research only:** synthetic runs and report illustrations are not clinical
validation. See [readiness and calibration limitations](docs/reliability-audit.md)
and the [report provenance audit](docs/report-results-audit.md).

## Checks

```sh
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```
