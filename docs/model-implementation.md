# Model and statistical implementation

Implemented fold-local medians with retained empty numeric columns, seven
permanent lab missing indicators, categorical sex and ASA, and LR-only scaling.
The feature boundary rejects extra variables rather than silently admitting
labels or identifiers.

LR selects C from 0.1, 1, 10. XGBoost selects among twelve explicit combinations
of shallow depth, tree count and restrained learning rate with regularization.
The criterion is training-CV mean average precision; earlier simpler candidates
win ties. Folds are reduced deterministically only when minority counts require
it; fewer than two events or non-events blocks training. There is no validation
early stopping, class weighting or oversampling.

Protocol 1.1 adds strict versioned saved-model inference and separate execution,
review, calibration, internal-evaluation and clinical-use statuses. See
`inference.md` and `reliability-audit.md` for contracts and measured evidence.

Validation fits a one-dimensional unpenalized logistic recalibrator on raw
log-odds. A highest threshold attaining at least 80% sensitivity includes tied
scores. No base-model refit occurs after calibration. Nonpositive calibration
slopes are flagged rather than hidden. Ordinary calibrated prediction rejects
them; explicit raw-only research inference withholds calibrated probabilities,
thresholds and classifications. Evaluation and SHAP can retain finite invalid
fits only as labeled research diagnostics. Insufficient classes/events,
constant/separated scores or failed optimization leave calibration unavailable,
with raw-only research evaluation rather than invented calibrated measures.
The computational minimum is not a sample-size or clinical-readiness criterion.

Evaluation reports raw and calibrated AUROC, average precision and Brier score,
training-prevalence Brier reference, confusion counts, sensitivity, specificity,
PPV, NPV, F1 and accuracy. New evaluations also store alert counts/fractions and
alerts per 10,000 observations. Accuracy participates in individual and paired
operating-metric bootstrap intervals; count totals do not. Calibration-in-the-large uses a logit offset; a separate
joint fit estimates intercept and slope. Five probability bins include counts.
One thousand seeded patient draws preserve pairing, calculate available raw and
calibrated intervals and paired differences (including operating measures),
and count undefined resamples. Calibration parameter estimates are null when
unestimable or unconverged; their confidence intervals are not implemented.
Private predictions remain ignored.

## Read-only result derivatives

`preop-xai export-results --source CAMPAIGN --output NEW_ARTIFACTS_DIRECTORY`
uses saved, named prediction rows and aggregate metrics only after integrity
preflight. It checks all model/variant arrays against n/events, ranking point
estimates and frozen confusion counts. It never refits descriptive calibration
diagnostics: raw rows use `raw_calibration`, calibrated rows use `calibration`,
including convergence/status/nulls.

Operating exports use `p >= validation_threshold`. Accuracy is `(TP+TN)/n`;
predicted positives are `TP+FP`, fraction `(TP+FP)/n`, and normalized rate
`10000*(TP+FP)/n`. Zero denominators remain null. The descriptive
`test_prevalence_brier_reference=prevalence*(1-prevalence)` is distinct from
the frozen training-prevalence Brier on test outcomes.

ROC retains all distinct thresholds, including a blank infinity sentinel labeled
`positive_infinity`. PR uses average precision (AP), with a blank terminal
threshold labeled `none`; single-class ranking is explicitly unavailable.
Five fixed-width bins retain empty rows. Separate descriptive quantile bins
request ten bins, collapse duplicate edges, keep ties together and include
the minimum in the first right-closed interval; constant probabilities form one
bin. Full precision is retained in CSVs; figures label Brier to four decimals.
Source metrics, intervals, predictions, fixed calibration plot and seals are unchanged.

Completed implementation is not clinical validation. Test and CLI execution
evidence is maintained in `verification.md`.
