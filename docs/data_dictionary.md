# Data dictionary and review register

Canonical keys are `patient_id` (MRN), `operation_id` (LOG_ID) and `t0`
(AN_START_DATETIME). They are private provenance, never predictors.

| Concept | Source | Representation |
|---|---|---|
| Age | BIRTH_DATE | Numeric years only after review; not parsed as birth date |
| Sex | SEX | Categorical, missing becomes explicit unknown |
| ASA | ASA_RATING_C | Reviewed categorical I-V; VI excluded |
| Hemoglobin | Lab Name / Observation Value | g/dL |
| Platelets | Lab Name / Observation Value | 10^9/L |
| Creatinine | Lab Name / Observation Value | mg/dL |
| BUN | Lab Name / Observation Value | mg/dL; not urea |
| Sodium / potassium | Lab Name / Observation Value | mmol/L |
| Glucose | Lab Name / Observation Value | mg/dL |
| Lab collection | Collection Datetime | Collection, not demonstrated release |
| Lab unit | Measurement Units | Exact reviewed conversion map |
| Mortality | DISCH_DISP, hospitalization times | Nullable 0/1 |
| Respiratory | Element_Name, Element_abbr, CONTEXT_NAME, SMRTDTA_ELEM_VALUE | Reviewed exact tuple, nullable 0/1 |

The local lab table has no release timestamp. Strict mode therefore rejects it
without an explicit release-column mapping; a collection-time proxy is a
separate, disclosed protocol choice. Candidate mappings in YAML are not
clinical approvals.

Only empty CSV fields are parsed as null. Literal `None`, text, inequalities
and unknown units remain available for audit. Inequality values are not exact
measurements. Latest conflicting eligible measurements are quarantined.

## Local source audit, 17 October 2026

`preop-xai audit --config configs/study.yaml` reproduced 65,728 information rows,
39,685 distinct patients and 64,354 operations. It found 1,374 duplicated
operation keys, including 10 with nonidentical records. These are raw counts,
not final cohort or event counts. The laboratory source contains 29,079,344 rows.

The information audit found 7,484 missing/invalid anesthesia starts, 7,498
invalid/missing ends, nine admissions after anesthesia start and 63 discharges
before anesthesia end. These are review flags, not automatically corrected facts.
Private inventories and source checksums are in `artifacts/study/audit/`.
