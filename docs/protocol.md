# Study protocol, version 1.1

Amendment, 18 October 2026: new campaigns distinguish execution from reliability
and use the invalid/unestimable calibration policy in `reliability-audit.md`.
Default inference rejects unreliable calibration; explicit research-only
inference returns raw scores without calibrated probabilities/classifications.
Research evaluation preserves finite nonpositive fits as labeled invalid-fit
diagnostics, and reports unestimable calibrated results as unavailable. This
policy was fixed before the new campaign; prior campaigns remain unchanged.

Source documents: *Preoperative XAI Project Plan* and *Research Synopsis*,
17 October 2026. This implementation is research software, not evidence of
completed clinical review or clinical readiness.

The cohort is the first eligible observed operation per adult MOVER EPIC patient,
selected before endpoint exclusions. ASA VI and invalid anesthesia boundaries
are excluded. Prediction is immediately before anesthesia starts. Across-patient
calendar-temporal validation is invalid because dates are individually shifted.

The candidate concepts are age, sex, categorical ASA I-V, hemoglobin, platelets,
creatinine, BUN, sodium, potassium and glucose. Missing lab values are retained
with training-only imputation and explicit indicators. No identifiers, outcomes,
ICU information, future labs, diagnoses or procedure durations enter models.

Laboratory selection uses a 30-day window, with explicit result availability
or a declared 24-hour collection-time proxy. The proxy approximates availability;
it does not prove freedom from leakage. Unreviewed unit and identity mappings
must not become clinical inputs.

In-hospital mortality requires hospitalization linkage and reviewed disposition
semantics. Transfers, missing or conflicting evidence are unknown, not survival.
Respiratory requires reviewed postoperative meaning and explicit negative
assessments; absent assessment and literal `None` are not automatically negative.
The default study is mortality-only pending review, with title narrowed
accordingly. No substitute morbidity endpoint is added.

Patient-independent seeded training/validation/test assignments target 70/15/15.
Both models use identical assessable patients per endpoint. Training CV selects
L2 Logistic Regression and shallow XGBoost by average precision. Calibration
and an 80%-sensitivity threshold use validation only. Test data are unlocked
only after settings and artifact hashes are frozen.

The core analysis reports raw and calibrated discrimination, probability error,
calibration and threshold measures, with 1,000 paired patient bootstraps.
SHAP describes raw and calibrated log-odds, never additive probability effects.
Ten paired training bootstrap refits quantify exploratory explanation stability.
Clinical plausibility and documentation dependence require human interpretation.

VitalDB, additional model families and a web application are excluded from the
core implementation. No empirical superiority or target AUROC is promised.
