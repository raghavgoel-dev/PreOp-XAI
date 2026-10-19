# Reliability and saved-inference audit - 18 October 2026

## Verdict and scope

The original demo completed execution, but its respiratory calibrated predictions
are unreliable. Neither synthetic results nor passing tests validate clinical use.
Real MOVER modeling remains blocked by review and source-mapping prerequisites.
The scope remains MOVER EPIC, regularized Logistic Regression and XGBoost,
in-hospital mortality, and respiratory only after its definition is reviewed.

Existing `artifacts/demo`, `artifacts/demo_new`, `artifacts/study`, and
`artifacts/real-readiness-20261018` are preserved. The changed calibration policy
is a prospective software/protocol amendment for new campaigns, not an attempt
to optimize already observed final-test performance. No seed, outcome, or sign
was changed to remove the warning.

## Original warning: measured evidence

Reproduce the read-only diagnostic on trusted local artifacts:

```powershell
uv run --locked python scripts/inspect_calibration.py artifacts/demo_new
```

The script reads training and validation only, reconstructs the original
synthetic generating labels by patient/operation identity, compares probabilities
with estimator margins, and independently fits the Bernoulli likelihood with
an analytic gradient. It does not train the base estimators or unlock test data.
The generating seed must match the campaign (default 2026).

| Endpoint | Model | Validation n | Events / non-events | Saved intercept | Saved slope | Raw validation AUROC |
|---|---|---:|---:|---:|---:|---:|
| Mortality | LR | 90 | 16 / 74 | -0.034142229 | 0.849162064 | 0.773648649 |
| Mortality | XGBoost | 90 | 16 / 74 | 1.627165705 | 2.141779230 | 0.828547297 |
| Respiratory | LR | 90 | 10 / 80 | -3.115259324 | -0.551539659 | 0.482500000 |
| Respiratory | XGBoost | 90 | 10 / 80 | -3.170078845 | -0.577102895 | 0.440000000 |

Both warnings therefore belong to **respiratory**, not mortality.
The fitted objects in `<endpoint>/models.joblib`, `split_counts.json`, and the
explanation calibration parameters agree. Training uses 420 patients:
mortality 74/346 and respiratory 58/362 events/non-events.

Checks against the original saved objects:

- Zero mismatches between reconstructed generating labels and either partition.
- Both estimators expose classes `[0, 1]`; event is 1. LR uses its decision
  function and XGBoost its binary-logistic margin, not a probability as a logit.
- Maximum sigmoid-margin versus `predict_proba[:, 1]` error is zero for LR and
  less than `4.2e-8` for XGBoost across these partitions.
- Independent respiratory slopes are -0.549588607 and -0.576743145. Their
  likelihood-gradient maximum absolute errors are below `6e-9`. The small
  discrepancy from the saved fits reflects the original optimizer tolerance;
  it does not explain the sign. New fits use a tighter tolerance.
- Validation score/event covariance is negative: -0.004735873 for LR and
  -0.006533329 for XGBoost. The independently optimized likelihood agrees with
  the negative association rather than exposing a score-scale defect.

The known respiratory generating risk depends only on ASA:
`expit(-2.2 + 0.5 * (ASA - 2))`, spanning approximately 0.063 to 0.231.
Even this known generating score has validation AUROC **0.443125**, versus
0.616594 in training. Thus sampling variation is visible before learning any
model. Only ten validation events inform two calibration parameters.
Respiratory fitted training AUROCs are 0.658983 (LR) and 0.788912 (XGBoost),
versus 0.4825 and 0.44 in validation. This supports weak signal plus sampling
variability, with additional training optimism/overfit, especially for XGBoost.
It does not quantify each cause's contribution or prove clinical reliability.
No observed encoding, positive-class, alignment, or margin/probability bug
explains the original negative slopes.

The actual software defects were that ordinary `probabilities()` returned an
invalid recalibration without rejection, and model boundaries allowed a
misordered label Series or fractional labels to be consumed positionally or
truncated. New regressions reproduced those defects before fixing them.
They were not observed in the original correctly aligned demo.

### Consequences of a nonpositive slope

For raw logit `z`, calibration is `a + b*z`; probability is its sigmoid.
Positive `b` preserves ranking. Negative `b` reverses it: AUROC becomes
`1 - raw AUROC`, with ties handled consistently. Average precision must be
recomputed; it has no analogous complement identity. Brier error can improve
or worsen independently of ranking. At `b = 0`, every probability is identical,
AUROC is 0.5 when both classes exist, and average precision is prevalence.

A validation threshold applied to negative-slope calibrated scores selects the
opposite raw-score direction. Achieving 80% validation sensitivity says nothing
about clinical usefulness, specificity, PPV, or held-out sensitivity. Thresholds
are fixed before test access and are never treatment recommendations.

SHAP calibration is algebraically `phi_calibrated = b * phi_raw` with baseline
`a + b * baseline_raw`. A negative slope reverses all contribution signs; zero
erases them. Additivity can pass perfectly for an unreliable model. Grouping
and missingness remain conserved, but these calibrated contributions cannot
be interpreted as validated clinical-risk effects.

For context only, the **already evaluated** original test artifacts report:

| Endpoint/model | Raw AUROC | Calibrated AUROC | Raw Brier | Calibrated Brier |
|---|---:|---:|---:|---:|
| Mortality/LR | 0.673986 | 0.673986 | 0.148523 | 0.145055 |
| Mortality/XGBoost | 0.704814 | 0.704814 | 0.134428 | 0.142355 |
| Respiratory/LR | 0.526709 | 0.473291 | 0.116934 | 0.116339 |
| Respiratory/XGBoost | 0.528846 | 0.471154 | 0.115780 | 0.117314 |

These are synthetic descriptive results, not policy-selection targets or real
clinical results. Respiratory's training-prevalence Brier reference is 0.115578,
which neither model improves on in that original test. No superiority claim
is justified by these point estimates.

## Status and invalid-calibration policy

`status.json` and the report explicitly distinguish stage execution, synthetic
scope, data/endpoint review attestations, per-model calibration, completed
internal evaluation, and unsupported clinical use. `passed: true` is retained
for backward-compatible **software execution** only; the demo's terminal JSON
also states that predictive reliability is not established.

The policy is fixed in code before running the new campaign:

1. Ordinary calibrated prediction rejects a nonpositive or unavailable fit.
   No slope constraints, label reversal, seed search, or automatic replacement.
2. Explicit `predict --research-only` permits **raw** scores/probabilities when
   calibration is invalid. Calibrated probability, threshold and classification
   are blank. This is a diagnostic output, not validated risk.
3. Research evaluation/explanation explicitly opts into preserving a finite
   nonpositive recalibration as an **invalid-fit diagnostic**. Status and plot
   labels carry that designation. This preserves evidence of ranking/sign
   reversal without approving its use in inference.
4. Fewer than two validation events or non-events, constant scores,
   complete/quasi separation, nonfinite parameters/scores, and optimizer failure
   make calibration unavailable. The base model is preserved; calibrated
   metrics, threshold counts and calibrated SHAP are unavailable/null rather
   than invented. Raw-only research evaluation remains possible.

The two-per-class guard is an arithmetic/estimability policy, **not** an event
adequacy or clinical performance target. A finite positive slope alone does not
establish stability, calibration quality, transportability, or clinical utility.
Clinical/sample-adequacy review remains separate.

## Complete workflow assessment

| Stage | Implemented behavior and evidence | Remaining limitation |
|---|---|---|
| Raw audit | Lazy string scans, checksums, coding/key/timing inventories; actual local audit exists | Inventories do not approve semantics |
| Cohort | Exact supplied-field duplicates, conflict quarantine, adult/ASA/boundary gates, first eligible operation before labels | Conflict scope is canonical projection, not every unconsumed raw field |
| Labels | Nullable reviewed mortality, containment/linkage checks; exact respiratory tuples with explicit negatives and contradictions | Real mappings and assessability not approved |
| Features | Seven mapped labs, explicit units/bounds, 30-day selection, release or disclosed 24-hour proxy, provenance | Source names/units mismatch; no release column |
| Leakage | Identity/order/static/provenance/window invariants | Cannot verify source timestamp meaning or truth of proxy |
| Split | One deterministic patient-independent mortality-stratified 70/15/15 assignment; unknown-primary allocation independent of respiratory | Respiratory not separately stratified; sparse events require review |
| Preprocess/train | Whole-pipeline clones inside training CV; LR 3 and XGBoost 12 candidates selected by AP; training-only final refit | Minimum computational class counts are not power calculations |
| Calibration | Validation-only raw-logit recalibration and 80% sensitivity diagnostic threshold; no base refit | Sparse-event uncertainty remains |
| Explanations | Both fitted models/preprocessors; same raw training background; raw and affine calibrated-logit additivity; concept/missingness grouping | SHAP is descriptive, not causal; invalid calibration is diagnostic only |
| Stability | Ten paired fixed-parameter training bootstraps, refitted preprocessing, fixed validation/background, raw-logit scale | Exploratory; no retuning or recalibration uncertainty |
| Freeze | Hashes of source/config/lock/partitions/models/calibration/metadata/explanation/stability; development mutation rejected | Workflow guard, not filesystem access control; raw hashes recorded from audit |
| Evaluation | Same assessable patients; raw/calibrated AUROC/AP/Brier, prevalence reference, calibration diagnostics/bins, confusion measures | No universal performance acceptance target |
| Uncertainty | Shared patient bootstrap draws; percentile intervals and paired model differences; undefined draws counted | Conditions on fitted models/calibrators/thresholds; calibration-parameter CIs not implemented |
| Storage/inference | Complete fitted pipelines and calibration/threshold in joblib, strict versioned metadata/schema/hash, separate-process CSV inference | Trusted local joblib only; feature-only input cannot prove timing |
| Reporting | Separate execution/review/reliability/validation statuses; missing stages explicit | Software report cannot confer clinical approval |

Held-out metrics never tune models or recalibrators. Failed descriptive
calibration fits return null estimates with reasons, not plausible-looking
unconverged coefficients. Raw and calibrated five-bin plots include counts.
Paired differences cover discrimination/error and calibrated operating measures.
Missing classes/zero denominators are undefined rather than scored as zero.
Training, recalibration and stability convergence warnings fail or record
unavailable calibration explicitly; warnings are not suppressed.

## Actual MOVER readiness

The independent read-only audit rechecked the live schemas and information,
complication and procedure-event aggregates. Laboratory global counts are from
the existing full audit, reconciled against all five inventory totals; a bounded
live 10,000-row sample was inspected. This is not a new whole-file checksum run.

The sources contain 65,728 information rows, 39,685 patients, 64,354 operations,
29,079,344 labs, 203,945 complication rows, and 640,223 procedure-event rows.
These are raw counts, not assessable indexed patients or power estimates.

Source identifiers are `MRN` and `LOG_ID`; the cutoff is `AN_START_DATETIME`.
Information also consumes `BIRTH_DATE`, `SEX`, `ASA_RATING_C`,
`AN_STOP_DATETIME`, `HOSP_ADMSN_TIME`, `HOSP_DISCH_TIME`, `DISCH_DISP_C`,
and `DISCH_DISP`. The source schema has no separate hospitalization identifier.
Reviewed encounter linkage cannot be replaced by timestamp containment alone.

The actual lab schema is `LOG_ID, MRN, ENC_TYPE_NM, Lab Code, Lab Name,
Observation Value, Measurement Units, Reference Range, Abnormal Flag,
Collection Datetime`. No result-release timestamp exists. Complications contain
`LOG_ID, MRN, Element_Name, CONTEXT_NAME, Element_abbr, SMRTDTA_ELEM_VALUE`,
with no assessment timestamp. Postoperative meaning requires source review,
not a timing assertion from columns that are absent.

Exact configured aliases HGB/PLT/CREATININE/BUN/SODIUM/POTASSIUM/GLUCOSE each
have zero inventory matches. Candidates are Hemoglobin/Platelets/Creatinine/
Urea nitrogen/Sodium/Potassium/Glucose, **not automatically approved mappings**.
Hemoglobin is predominantly `G/DL`; platelets use `THOUS/MCL` and
`THOUS/ CU MM`. Current mappings miss these spellings. Some name groups have
incompatible-looking volume/urinary units. Specimen compatibility, source-specific
conversion and BUN-versus-urea identity need qualified review.

Raw `BIRTH_DATE` is numeric 17-90: 34 rows below 18 and 668 at 90.
ASA is represented as 1.0-6.0, with 6,970 missing rows and 41 class-VI rows.
The primary MOVER publication documents age capping at 90 and random date shifts
linked to each patient, preserving within-patient intervals but not shared
calendar chronology: Samad et al., JAMIA Open (2023), DOI
`10.1093/jamiaopen/ooad084`, "Deidentification and HIPAA compliance".
This supports a patient-independent random split, **not calendar-temporal
validation**. It does not independently approve this release's `BIRTH_DATE`
field as age at the indexed operation, ASA translation, or static provenance.

There are 1,374 duplicate operation keys, including ten conflicting raw keys
and four keys linked to multiple patients. Seven conflicts remain after the
adapter's actual projection/parsing. Therefore the raw audit's ten conflicts
must not be described as the pipeline's eventual seven canonical exclusions.
The canonical supplied-field contract remains unchanged; any decision to
quarantine discrepancies in unconsumed raw fields is a separate review amendment.

Timing findings include 7,484 missing/invalid starts, 7,498 invalid ends,
14 missing/invalid discharges, nine admissions after start, and 63 discharges
before anesthesia end. Counts overlap. No final cohort count is inferred.

Raw `Expired` occurs in 1,012 rows across 420 patients/992 operations; that is
not 1,012 indexed deaths. Home Routine occurs in 45,358 rows; 19,358 other/missing
dispositions remain subject to explicit review. Transfers/hospice/unmapped or
contradictory evidence remain unknown.

Raw complication literals include 196,720 `None` and 596 `Respiratory` rows
(191 patients/582 operations for the latter); 517 patient-operation pairs
contain both literals. Neither is an approved negative/positive mapping.
Respiratory remains disabled, and `respiratory_label_map.csv` is header-only.

All six primary review flags are false, reviewer/evidence fields are empty,
feature/mortality mappings are unreviewed, and strict lab availability lacks
its required release column. Thus no real campaign is authorized by the current
configuration. Final assessability, events, eligible-lab coverage, split/training/
calibration adequacy, or real model reliability cannot yet be measured through
the approved pipeline. Complete the reviews and mappings, then use a **new**
output directory; do not repurpose existing frozen campaigns.

## Verification record

The original baseline passed 28 tests with three visible external SHAP/Matplotlib
deprecation warnings. Six added boundary regression cases failed before the
fix; those same six passed afterward. Integrated model/explanation/workflow
checks then passed 30 tests, including unavailable calibration and sign-reversed
SHAP. Final campaign, fresh-process equivalence and complete-check evidence follow.

### Final unchanged-source campaign and checks

`uv run --locked preop-xai demo --output artifacts/reliability-20261018`
completed with exit 0. Both endpoints completed full training-CV searches,
calibration, explanations, ten paired stability refits per model, freeze,
one held-out evaluation with 1,000 paired draws, and report generation.
All four models passed raw and calibrated-logit SHAP additivity checks.
Both respiratory warnings remain visible. The report records complete execution,
synthetic-fixture-only reviews, completed synthetic evaluation, failed respiratory
calibration, and unsupported clinical use. Source/configuration was not changed
during the campaign; its hashes are retained in both freezes. No project commit
was created.

The tighter validation fit yields:

| Endpoint/model | Intercept | Slope | Status |
|---|---:|---:|---|
| Mortality/LR | -0.034199544 | 0.849123767 | fitted, research only |
| Mortality/XGBoost | 1.627247381 | 2.141845866 | fitted, research only |
| Respiratory/LR | -3.111672495 | -0.549588599 | nonpositive, invalid diagnostic |
| Respiratory/XGBoost | -3.169417817 | -0.576743216 | nonpositive, invalid diagnostic |

New synthetic test uncertainty remains broad. Mortality raw AUROC 95% paired-draw
percentile intervals are 0.540-0.799 (LR) and 0.561-0.831 (XGBoost), with
XGBoost-minus-LR difference -0.063 to 0.122. Respiratory intervals are 0.366-0.696
and 0.360-0.698; the paired difference is -0.136 to 0.127. All these intervals
used 1,000 effective draws with zero undefined draws in this campaign; that is
not a guarantee for sparse real cohorts. The original weak respiratory result
has not been made reliable by a software-policy change. No overall model
superiority or clinical usefulness follows from these synthetic results.

Actual separate CLI processes predicted all three independently constructed
feature rows with mortality LR and XGBoost (exit 0), rejected default respiratory
LR calibrated inference (exit 1), and produced explicitly raw-only respiratory
LR/XGBoost CSVs with blank calibrated/threshold/classification fields (exit 0).
Each row preserves positions 0, 1, 2 and exposes model, endpoint, version,
synthetic/review/calibration/internal-evaluation/clinical-use/timing statuses.
The saved examples are `lr-new.csv`, `xgb-new.csv`, `respiratory-raw.csv`, and
`respiratory-xgb-raw.csv` in the new campaign root. No rejected-output CSV exists.

Fresh-process regression tests for **each** model compare predictions from the
original in-memory objects before serialization with loaded CLI predictions
at `rtol=1e-12, atol=1e-12`; single-row versus batch comparisons use `atol=1e-14`.
Tests forbid `fit` and available `fit_transform` methods on pipelines,
preprocessing components, both estimators and the calibrator. Missing values,
unseen categories, nonidentity upstream unit conversions and row order are covered.

Final checks:

- `uv run --locked pytest -q`: **109 passed**, three unchanged visible external
  SHAP/Matplotlib deprecation warnings, no skips or failures.
- `uv run --locked ruff check .`: exit 0.
- `uv run --locked ruff format --check .`: equivalent no-edit formatter check
  exited 0 with 41 files already formatted.
- `uv tool run basedpyright --pythonpath .venv/Scripts/python.exe --level error
  src/preop_xai scripts/inspect_calibration.py tests/test_inference.py
  tests/test_models_contracts.py tests/test_explanations.py
  tests/test_workflow_contracts.py`: **0 errors, 0 warnings, 0 notes**.
- A broader exploratory type check also included the untouched
  `tests/test_data_contracts.py` and found four existing pandas union-typing
  diagnostics at lines 136, 187, 188 and 201. Those are reported, not suppressed
  or edited to make the check appear clean. All those runtime tests pass.
- YAML LSP is not installed; actual settings parsing was exercised by the
  default-configuration tests and both real training CLI rejections.

Actual unchanged-review `train --endpoint mortality` and
`train --endpoint respiratory`, each using `--config configs/study.yaml`, exited
1 at the primary clinical-review gate before training/data mutation. No real
campaign or real predictive result is claimed. The independent source audit
and precise missing approvals/mappings above remain the real-data prerequisites.

Visual inspection opened the generated mortality raw-logit importance figure,
respiratory invalid-fit local SHAP figure, and respiratory raw/calibrated
calibration plot. Each contains readable plotted data and scale/status labels
without clipping; the invalid fit is visible in the local title and plot legend.

## Implementation references

These references describe the changed working tree, not the historical source
hashes preserved in earlier campaigns.

| Reference | Evidence or enforced boundary |
|---|---|
| `src/preop_xai/calibration.py:15` | LR decision function / XGBoost margin and event class 1 |
| `src/preop_xai/calibration.py:29` | Actual calibration parameter validity |
| `src/preop_xai/calibration.py:39` | Default invalid-calibration rejection and explicit diagnostic opt-in |
| `src/preop_xai/calibration.py:63` | Validation counts, estimability/convergence checks, recalibration/threshold |
| `src/preop_xai/inference.py:100` | Canonical schema, age, lab units and bounds |
| `src/preop_xai/inference.py:162` | Versioned bundle metadata export |
| `src/preop_xai/inference.py:198` | Metadata/runtime/hash compatibility before deserialization |
| `src/preop_xai/inference.py:228` | CSV shape, duplicate names, numeric/categorical/missingness checks |
| `src/preop_xai/inference.py:286` | Fitted preprocessing, estimator family and positive-class compatibility |
| `src/preop_xai/inference.py:338` | No-fit prediction path and explicit raw-only research policy |
| `src/preop_xai/status.py:27` | Independent execution/review/calibration/internal-evaluation/clinical-use states |
| `src/preop_xai/evaluate.py:83` | Honest null descriptive calibration estimates on failure |
| `src/preop_xai/evaluate.py:183` | Same-patient metrics, raw/diagnostic variants, paired uncertainty |
| `src/preop_xai/explain.py:152` | Saved-model/preprocessor SHAP and raw-logit additivity |
| `src/preop_xai/explain.py:236` | Affine calibrated SHAP, invalid flags and missing calibrated results |
| `src/preop_xai/workflow.py:54` | Endpoint assessability mask preserves feature/label row order |
| `src/preop_xai/workflow.py:113` | Exact sealed artifact set, including inference/calibration metadata |
| `src/preop_xai/workflow.py:144` | Persisted stage flow and partition restrictions |
| `scripts/inspect_calibration.py` | Reproducible independent original-campaign measurements |
| `tests/test_inference.py` | Pre-save versus fresh-process predictions, no fit/fit_transform, one-row/batches and malformed/incompatible inputs |

The raw adapters, label logic and patient split implementation were inspected
and preserved; their source contracts and local review evidence are described
in `data-implementation.md` and `real-data-verification.md`.
