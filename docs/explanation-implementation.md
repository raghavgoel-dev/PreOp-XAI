# Explanation lane implementation

## Read-only stability derivatives - 19 October 2026

The separate `export-results` command reads `stability.json` and available saved
private refit NPZs, without fitting or recomputing SHAP. It exports original draw
IDs by mapping pair positions through `successful_paired_draws`, preserves null
undefined Spearman values and partial/insufficient statuses, and validates the
`k*(k-1)/2` pair register and its means.

`stability_importance.csv` distinguishes across-refit sample SD (`ddof=1`) of
per-refit validation-mean absolute grouped importance from the existing
patient-centered contribution RMS. Sample-SD error bars are descriptive, not
confidence intervals; actual importance need not sum to one. Missing unsealed
arrays retain JSON means but make SD explicitly unavailable. Required sealed
file mismatches remain errors. Fewer than two successful refits supplies no
unsupported SD or agreement estimate.

The aggregate derivative indexes existing global SHAP bars and XGBoost
beeswarm/dependence figures with source hashes, preserving source files.
It excludes local TP/FP/TN/FN images, patient contribution arrays, draws and
baselines. LR coefficient links retain their source scaling/encoding
qualifications; no odds ratios or cross-model SHAP agreement are inferred.
See `report-artifacts-execution.md` for execution and visual inspection receipts.

## Protocol 1.1 reliability amendment - 18 October 2026

Finite nonpositive recalibration remains explainable algebraically, but JSON
and local figure titles label it invalid-fit research diagnostics. Negative
slopes reverse SHAP directions; passing additivity does not validate risk.
Unavailable calibration produces raw explanations only, null calibrated
summaries and no threshold-defined local groups. It is never silently treated
as identity calibration. The saved fitted pipeline/preprocessing remains the
explanation target. Stability still uses raw logits and now escalates estimator
convergence warnings rather than continuing an unconverged refit.

## Completion entry — 17 October 2026

Implemented `explain_models`, `run_stability`, and `build_report`, with direct
synthetic LR/XGBoost scientific tests. This entry records implementation, not
execution, clinical review, endpoint approval, or final experiment completion.
Repository inspection and test execution must be recorded by the integrating
runner; neither is claimed here.

## Interfaces and assumptions

Feature matrices must contain exactly the ordered `preprocessing.FEATURES`
columns. Each row must represent one distinct indexed patient; identity and
outcome columns are rejected as predictors. Row uniqueness by patient cannot be
verified without the upstream private split manifest.

Bundles expose fitted `preprocess` and `model` pipeline steps. Recalibrators are
either absent or fitted sklearn one-predictor logistic regressions exposing
`coef_` and `intercept_`. Local error groups require an already fixed threshold.
Calibration functions remain the authoritative raw-score/probability interfaces.

Outputs are `explain.json`, `stability.json`, aggregate figures, and restricted
`private/` artifacts. Reports discover these files and `metrics.json` recursively,
supporting endpoint subdirectories. Missing report stages are explicitly marked.

## Explanation conventions

A seeded sample without replacement of at most 64 raw training rows supplies
the shared background for both models. Every model transforms those same rows
through its own fitted preprocessing. LinearExplainer and TreeExplainer use
interventional explanations with raw log-odds output. The SHAP version is recorded.

Transformed names are resolved to canonical concepts after removing sklearn
transformer prefixes. One-hot columns and explicit missingness columns are summed
within each concept before computing global mean absolute attribution.
Missingness contributions are additionally reported separately, as are individual
transformed-column mean absolute values. Unknown or ambiguous transformed names
raise an error rather than silently dropping attribution.

Raw score additivity is checked numerically. For logistic recalibration
`calibrated_logit = a + b * raw_score`, contributions are multiplied by `b` and
the baseline becomes `a + b * baseline`. Calibrated-logit additivity and agreement
with the calibration probability API are checked independently.

Global bars use raw grouped contributions. XGBoost beeswarm and dependence plots
use transformed raw contributions. Dependence concepts are fixed in advance:
age, creatinine, and hemoglobin. The lookup excludes explicit missingness columns.
If multiple non-flag columns exist, schema order selects the first; if none exists,
the plot is omitted with an explicit unavailable record. No outcome-dependent
substitute is selected.

Local TP/FP/TN/FN examples are nearest to the median calibrated risk within their
group, with first-row tie breaking. Empty groups are recorded. Their bars use
grouped calibrated-logit contributions. Patient-level risk values and selected
row positions are stored only in restricted arrays.

## Stability conventions

Default execution draws ten training-row bootstrap arrays, shared by all models.
Every refit uses `sklearn.clone` on the selected fixed-parameter pipeline.
Preprocessing is refitted; no hyperparameter search, validation fitting,
recalibration, early-stopping selection, or threshold selection occurs.

The original validation rows and original raw training background remain fixed.
Grouping always uses the canonical concept schema, including zero contributions
when a category is absent in a refit. Stability is measured on raw-model log-odds.

Outputs include all pairwise Spearman correlations, top-five Jaccard overlaps,
top-five inclusion frequencies, importance summaries, centered contribution RMS
variability, and baseline means/shifts. Ranking ties follow canonical schema
order. Constant importance vectors have explicitly undefined correlations,
serialized as JSON null without invoking a warning-producing correlation.

For each validation patient and concept, contributions are centered by subtracting
their across-refit mean. RMS variability is computed over refits and then averaged
over validation patients. Baseline shifts are centered and summarized separately;
they are not attributed to clinical features.

Single-class bootstrap draws are excluded for both models. Fitting or explanation
errors propagate and fail the stage rather than being swallowed.
Successful draw indices are reported. Fewer than two successful
paired refits produces an explicit insufficient-results status. Pair indices in
summaries refer to the ordered successful-draw list.

## Privacy and reporting

Private directories are mode 0700; compressed arrays and local figures are mode
0600. Permissions supplement, but do not replace, authorized storage, ignored
artifact directories, DUA compliance, and institutional controls. Patient-level
arrays use positions rather than identifiers and remain sensitive.

Aggregate report generation never opens private arrays or embeds local figures.
It includes available aggregate JSON, an aggregate figure index, and explicit
limitations. Upstream metric JSON must itself be aggregate-only.

Interventional SHAP is descriptive, not causal. Correlation can divide attribution;
missingness can describe care processes. Calibrated-logit contributions are not
additive probability percentage points. Clinical plausibility review remains a
human task.

No explanation artifact approves clinical semantics, hospitalization linkage,
age/ASA interpretation, availability assumptions, or respiratory ascertainment.
The core study remains MOVER EPIC only. Synthetic tests cannot approve real-data
modeling.

## Verification supplied

`tests/test_explanations.py` directly checks:

- LR and small XGBoost raw-logit additivity;
- nonidentity affine recalibration and probability agreement;
- seeded shared-background selection;
- grouping conservation and explicit missingness recognition;
- undefined-rank handling without warnings;
- deterministic bootstrap summaries and original-model isolation;
- centered attribution variability;
- empty local groups, restricted arrays, report generation;
- rejection of identifier-bearing feature matrices.

Run these tests in the root-owned locked environment before claiming verification.
