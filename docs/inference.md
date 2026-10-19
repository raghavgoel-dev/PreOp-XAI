# Saved-model research inference

## Interface

Training persists both complete fitted sklearn pipelines to
`<output_dir>/<endpoint>/models.joblib`. Calibration attaches the validation-only
recalibrator and research threshold and writes `calibration.json` plus
`bundle.json`. Native `xgboost.json` alone is **not** an inference bundle.

```powershell
uv run --locked preop-xai predict --bundle artifacts/reliability-20261018/mortality --model lr --input docs/examples/new-patients.csv --output artifacts/reliability-20261018/lr-new.csv
uv run --locked preop-xai predict --bundle artifacts/reliability-20261018/mortality --model xgboost --input docs/examples/new-patients.csv --output artifacts/reliability-20261018/xgb-new.csv
```

These are independently constructed artificial feature rows, not held-out
patients and not clinical risk estimates. The full new demo command is:

```powershell
uv run --locked preop-xai demo --output artifacts/reliability-20261018
```

Use another output directory for another campaign and adjust the paths.
Prediction outputs must be new `.csv` paths; existing evidence is not overwritten.
Old bundles lacking versioned metadata are rejected; do not silently relabel
or modify previous frozen campaign artifacts to make them appear compatible.

## Input contract

Inputs are **already prepared canonical features**, not raw MOVER records.
The CSV must contain exactly these ten unique names:

```csv
age,sex,asa,hemoglobin,platelets,creatinine,bun,sodium,potassium,glucose
```

Column order may differ; it is reordered to the saved schema. Output
`row_position` is zero-based input order, including repeated equal feature rows.
No labels, identifiers, timestamps or extra columns are accepted.
Use an external row manifest if authorized patient linkage is needed.

| Feature | Canonical interpretation |
|---|---|
| age | Finite adult age 18-90, already top-coded at 90 by upstream preparation |
| sex | Categorical string; empty is explicit unknown |
| asa | Canonical I-V as 1-5; equivalent numeric `.0` forms accepted; empty/unknown permitted |
| hemoglobin | g/dL |
| platelets | 10^9/L |
| creatinine, bun | mg/dL; BUN is not urea |
| sodium, potassium | mmol/L |
| glucose | mg/dL |

Labs can be empty/missing and are imputed **only by the already fitted training
imputer**. Nonempty numerics must parse and be finite, and labs must respect
the saved mapping's bounds. Malformed CSV rows, duplicate names, nonfinite
numeric text, missing age, invalid ASA, and incompatible schemas/artifacts fail.
Sex categories unseen in fitting use the saved encoder's `handle_unknown=ignore`
policy; that is an all-zero encoded category, not a learned new category or a
claim of equivalence to another sex. Categories are not learned at inference.

The caller is responsible for canonical units. A feature-only CSV cannot prove
that a plausible number is expressed in the correct unit. Inference does not
guess units, convert source values, cap ages, repeat lab selection, or normalize
values twice. Saved preprocessing transforms the canonical inputs once.

The caller must independently establish preanesthetic provenance. No anesthesia,
collection or release timestamps are supplied, so output explicitly says
`not-verifiable-from-feature-only-input`. This command cannot perform the raw-data
leakage audit or establish clinical meaning from numbers alone.

## Artifact and output contract

Only load trusted, authorized local bundles: joblib deserialization executes
Python object reconstruction. Hashes catch accidental incompatibility, not an
attacker who can replace both model and metadata.

Metadata versions the ordered schema, canonical units, bounds, categorical and
missingness policy, endpoint, synthetic scope, review status, model hash, and
runtime versions. Incompatible versions, hashes, fitted transformer/model
contracts or positive-class order are rejected before predicting. Copy the
whole endpoint directory when transferring a bundle, not just the tree JSON.

Prediction never calls `fit`, `fit_transform`, CV, threshold selection or
calibration fitting. It reuses the fitted preprocessor, estimator and calibrator.
Both one-row and batch inputs follow the same path.

Rows expose model, endpoint, artifact version, synthetic status, data review,
calibration and internal-validation status, unsupported clinical use, raw logit,
raw probability, calibrated probability when allowed, and a research threshold/
classification when allowed. The completion marker is bound to the model hash;
synthetic evaluation remains explicitly synthetic. Internal retrospective
evaluation is not prospective or clinical validation.

Invalid calibration is rejected by default. To obtain **raw-only** diagnostic
output explicitly:

```powershell
uv run --locked preop-xai predict --bundle artifacts/reliability-20261018/respiratory --model lr --input docs/examples/new-patients.csv --output artifacts/reliability-20261018/respiratory-raw.csv --research-only
```

Calibrated probability, research threshold and classification are blank in that
case. There is no silent fallback to a different risk model, positive slope
constraint, label reversal or inference-time recalibration. Even positive-slope
calibrated probabilities are research outputs, not validated clinical estimates;
threshold classifications are never clinical recommendations.
