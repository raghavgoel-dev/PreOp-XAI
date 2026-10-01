# PreOp-XAI Scientific Protocol (Frozen Rules)

Status: frozen at drafting, 2026-10-01. Amendments require a new dated entry in
`docs/decisions.md` and a noted reason; silent drift is a protocol violation.
These rules bind every pipeline stage and every report.

## 1. Scope and question

Retrospective, single-dataset, research-only study on INSPIRE release 1.4.2.
Question: how well can models predict postoperative outcomes from values and
results verified as available strictly before the start of a patient's first
structurally eligible released operation, and how stable are their
explanations?

## 2. Prediction boundary and availability

The prediction time is the operation start. A value may enter the strict feature
set only when its result availability is verified as strictly before the
operation start; values available at the cutoff are excluded. An event time
before the cutoff is not sufficient: if the result became available at or after
the operation start, or its availability is unverified, it is excluded from the
strict analysis. Anything after the boundary, including all intraoperative
content, is used only for leakage checks and, where these rules allow, label
construction.

## 3. Cohort

- Unit: one row per patient, the first structurally eligible released operation.
- Structural eligibility uses valid keys and times only: representable age, no
  impossible sequences, and the donor and ASA physical status 6 exclusions once
  the audit verifies the fields behind them. Structural eligibility is decided
  before any endpoint-specific surveillance or feature-availability filtering.
- A later operation is never chosen because it has better predictor or outcome
  observability. Endpoint-specific eligible subsets are derived afterward and
  reported as subsets.
- No patient contributes more than one row.

## 4. Endpoints, gates, and unknown handling

- Primary: postoperative in-hospital mortality. Real mortality mapping/linkage
  is required and stays blocked until the local capability audit verifies direct
  admission status/linkage and the timing assumptions. Synthetic mortality may
  be supported in smoke mode only.
- Conditional secondaries: acute kidney injury (AKI); early ICU admission;
  prolonged invasive support. Each is included only if the capability audit
  (`audit-data`) confirms the required variables and definitions are supported.
- Gate outcomes are recorded in the audit matrix with reasons. An unsupported
  endpoint is omitted, never proxied silently.
- Unknown handling: unknown support means "not included"; missing values inside
  a supported endpoint follow the missing-data plan written at milestone 3 and
  disclosed in reporting. No result section may report an endpoint the audit did
  not confirm.

## 5. Feature analyses: strict and proxy

- Strict set: variables with verified availability strictly before the operation
  start. This is the primary analysis; unverified availability means exclusion
  from the strict set.
- Proxy set: a clearly named proxy sensitivity analysis may include timestamp
  proxies whose availability is unverified. It is analyzed separately, always
  labeled as proxy, and never claims leakage-free status.
- The two sets are never merged into one model.

## 6. Ordering and first operation

Ordering for "first" uses only keys and times the audit validates. If reliable
within-patient ordering cannot be established, real cohort construction is
blocked; row order, identifiers, or a best-effort surrogate are never used.
Eligibility never depends on downstream predictor or outcome observability.

## 7. Split

- Preferred: a chronology-based cross-patient split, used only if the audit
  demonstrates valid cross-patient chronology.
- Default and fallback: patient-disjoint random split; all rows of one patient
  fall in exactly one partition.
- Validation portion for calibration is disjoint from both training and test.

## 8. Models

Exactly four families, trained sequentially on CPU with the resource policy of
`docs/implementation_plan.md`: penalized logistic regression; random forest;
gradient-boosted trees (XGBoost, CPU-bounded); Explainable Boosting Machine.

## 9. Calibration and thresholds

- Post-hoc calibration via sklearn FrozenEstimator on the disjoint validation
  portion only; the base estimator is never refit during calibration.
- Test data is never used for calibration, tuning, or threshold choice.
- Thresholds are reported only under a feasible operating policy defined before
  lock (decision D-014); the default is omission, with ranking and calibration
  metrics carrying the evaluation.

## 10. Experiment lock and evaluation

- Before any test evaluation, `lock` freezes cohort, labels, features, split,
  model artifacts, calibration, and configuration into a hashed manifest.
- Evaluation runs exactly once against the locked test portion. A failed or
  changed check invalidates the lock; re-evaluation requires a new lock with a
  recorded reason.

## 11. Explanations and stability

- Tree-based models: TreeSHAP on the raw margin scale, background drawn from the
  training split only (capped by the configured budget), stored and displayed
  with the scale declared.
- Calibrated probabilities are reported separately and never mixed into
  explanation plots or tables.
- Stability: repeated runs across seeds and resamples within the configured
  budget; dispersion of metrics and explanation rankings is reported per
  endpoint and family.

## 12. Interpretation limits

- All findings are descriptive and noncausal. Associations are not effects.
- The project issues no clinical recommendations, thresholds for care, or
  deployment guidance, and no output may be used in patient care.
- Any manuscript or report states the research-only scope, the synthetic state
  of any non-real artifact, and every omitted or gated endpoint with its reason.
