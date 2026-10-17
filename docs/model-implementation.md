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

Validation fits a one-dimensional unpenalized logistic recalibrator on raw
log-odds. A highest threshold attaining at least 80% sensitivity includes tied
scores. No base-model refit occurs after calibration. Nonpositive calibration
slopes are flagged rather than hidden.

Evaluation reports raw and calibrated AUROC, average precision and Brier score,
training-prevalence Brier reference, confusion counts, sensitivity, specificity,
PPV, NPV and F1. Calibration-in-the-large uses a logit offset; a separate
joint fit estimates intercept and slope. Five probability bins include counts.
One thousand seeded patient draws preserve pairing, calculate both raw and
calibrated intervals and paired differences, and count undefined resamples.
Private predictions remain ignored.

Completed implementation is not clinical validation. Test and CLI execution
evidence is maintained in `verification.md`.
