# Implementation contract

The project plan and synopsis dated 17 October 2026 agree. The core study uses
MOVER EPIC only, one indexed eligible adult operation per patient, mortality
and a conditional reviewed respiratory endpoint. VitalDB is an optional later
extension, not part of this implementation campaign.

## Shared module interfaces

All compact tables are pandas DataFrames at the model boundary. Raw sources
are scanned lazily with Polars. Canonical identity fields are `patient_id` and
`operation_id`; cutoff is `t0` (datetime). Outcome columns are nullable integers
`mortality` and `respiratory`. Split column `partition` contains `train`,
`validation`, or `test`. Feature names are `age`, `sex`, `asa`, `hemoglobin`,
`platelets`, `creatinine`, `bun`, `sodium`, `potassium`, `glucose`. Feature matrices
contain ONLY these columns; preprocessing adds seven explicit lab missingness
indicators, including when an entire training lab is absent.

Data lane exposes:
- `audit.audit_raw(raw_dir: Path, output: Path) -> Path` writes audit.json and
  mapping inventories; no clinical verification is inferred.
- `cohort.build_cohort(information: pd.DataFrame) -> pd.DataFrame` handles canonical
  columns, exact duplicate reconciliation, conflicts and first eligible indexing.
- `labels.build_labels(cohort, information, complications, outcome_config) -> pd.DataFrame`
  uses explicit reviewed mappings and nullable states.
- `features.build_features(cohort, labs, feature_config) -> tuple[pd.DataFrame, pd.DataFrame]`
  returns wide canonical features and long selection/rejection provenance.
- `features.audit_leakage(cohort, features, provenance, feature_config) -> None`.
- `splits.assign_splits(labels: pd.DataFrame, seed: int = 2026) -> pd.DataFrame`.
Raw-to-canonical adapters and config shapes are owned/documented by the data lane.

Model lane exposes:
- `preprocessing.FEATURES`, `LABS`: ordered tuples of canonical feature names.
- `train.fit_models(X: pd.DataFrame, y: pd.Series, seed=2026, folds=5,
  quick=False) -> dict[str, ModelBundle]`; keys `lr`, `xgboost`.
- `ModelBundle` has `pipeline`, `name`, `parameters`, `cv_score`,
  `training_prevalence`, `calibrator`, `threshold`.
- `calibration.raw_scores(bundle, X) -> np.ndarray`.
- `calibration.calibrate_models(bundles, X_validation, y_validation) -> None`;
  mutates only calibrator and threshold, never base pipelines.
- `calibration.probabilities(bundle, X, calibrated=True) -> np.ndarray`.
- `evaluate.evaluate_models(bundles, X, y, output: Path, bootstraps=1000,
  seed=2026) -> dict` writes metrics, paired bootstrap intervals and plots.

Explanation lane imports the model contracts above and exposes:
- `explain.explain_models(bundles, X_train, X_explain, y_explain,
  output: Path, seed=2026) -> dict`.
- `stability.run_stability(bundles, X_train, y_train, X_validation,
  output: Path, refits=10, seed=2026) -> dict`.
- `reporting.build_report(output: Path) -> Path`.
Use sklearn clone for fixed-parameter bootstrap refits. Explain pipeline steps
`preprocess` and `model`. Feature names from preprocess.get_feature_names_out().
Both explainers receive the SAME raw training background patients transformed
through each fitted preprocessor. Check raw and calibrated logit additivity.

Root owns packaging, config IO, raw adapters integration, CLI stages, freeze,
synthetic demonstration, final verification and commits. Workers do not commit
or modify shared files. Every worker maintains its own docs completion entry.

## Review and availability gates

Default configuration is unreviewed. Clinical semantics, hospitalization linkage,
numeric age interpretation, ASA, anesthesia boundary and static-variable provenance
must be reviewed explicitly before raw-derived modeling. Respiratory can remain
disabled with an amended mortality-only question. Collection-time proxy requires
an explicit 24-hour-lag choice, not a silent assumption. Synthetic demo settings
are explicitly synthetic and cannot approve real data.

## Initial completion record

Read the complete plan and synopsis, inspected repository and raw table headers,
and recorded matched scientific contracts. Existing history has one commit,
`first commit`, with no established naming convention; subsequent atomic commits
will use normal descriptive imperative subjects. Existing staged `.gitignore`
is preserved.
