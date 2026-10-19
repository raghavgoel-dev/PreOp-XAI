# Actual MOVER EPIC execution check - 18 October 2026

## Verdict

**The actual-source audit runs successfully. The current configuration is not
ready for an end-to-end research analysis. No real-data model performance values
were produced.**

This check used the real CSV files in `data/EPIC_EMR/EMR`, not the synthetic demo.
It found both missing review evidence and concrete source-mapping incompatibilities.
A successful synthetic campaign or a successful rejection at a review gate does
not establish successful real-data training or evaluation.

## What was executed

A fresh local configuration preserves every existing review flag and points to
a separate output root:

```text
Configuration: configs/real-readiness-20261018.local.yaml
Raw sources:   data/EPIC_EMR/EMR
Output root:   artifacts/real-readiness-20261018
```

The local configuration and generated artifacts are ignored by Git. Existing
study/demo artifacts and all raw files were left in place.

### Fresh actual-source audit

```sh
uv run --locked preop-xai audit --config configs/real-readiness-20261018.local.yaml
```

Observed result: **exit 0**. The new audit contains `audit.json` and 17 inventory
CSVs. The four source files total **3,650,722,197 bytes**. Audit duration was not
separately instrumented; no runtime estimate is presented as a measurement.

### Actual research-command attempts

The reproducible evidence script invokes actual CLI subprocesses using the
locked project interpreter:

```sh
uv run --locked python artifacts/real-readiness-20261018/verify_real_cli.py
```

| Actual invocation | Exit | Meaning |
|---|---:|---|
| `build-cohort` | 1 | Clinical review gate rejected execution |
| `build-labels` | 1 | Clinical review gate rejected execution |
| `build-features` | 1 | Clinical review gate rejected execution |
| `audit-leakage` | 1 | Clinical review gate rejected execution |
| `split` | 1 | Clinical review gate rejected execution |
| `train --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `calibrate --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `explain --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `stability --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `freeze --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `evaluate --endpoint mortality` | 1 | Clinical review gate rejected execution |
| `train --endpoint respiratory` | 1 | Primary clinical review gate rejected execution |
| `evaluate --endpoint respiratory` | 1 | Primary clinical review gate rejected execution |
| `report` | 0 | Generated a report explicitly marking research results unavailable |

Every command above used
`--config configs/real-readiness-20261018.local.yaml`.
`cli_checks.json` retains the exact commands, exit codes, stdout, and stderr.
There were zero unexpected exit codes in the evidence script. That means the
observed guards behaved as expected; it does **not** mean the research stages
completed successfully.

The first rejection message was:

```text
Clinical review required: verify age, ASA, anesthesia boundary, static predictor
provenance and mortality hospitalization/disposition mappings; record reviewer
and evidence in the local study configuration. Run audit first.
```

The downstream calculations were not reached. Their behavior on real indexed
patients remains unverified.

## Actual source values

These are newly audited **raw source counts**, before cohort indexing, label
ascertainment, laboratory eligibility, or patient partitioning.

| Source file | Rows | Distinct MRNs | Distinct operation IDs |
|---|---:|---:|---:|
| `patient_information.csv` | 65,728 | 39,685 | 64,354 |
| `patient_labs.csv` | 29,079,344 | 33,249 | 56,125 |
| `patient_post_op_complications.csv` | 203,945 | 36,985 | 64,214 |
| `patient_procedure events.csv` | 640,223 | 28,316 | 43,600 |

Information-table audit findings:

| Finding | Raw count |
|---|---:|
| Duplicated operation keys | 1,374 |
| Operation keys with conflicting records | 10 |
| Missing or invalid anesthesia starts | 7,484 |
| Missing/invalid ends, or ends not later than start | 7,498 |
| Midnight starts | 2 |
| Admissions after anesthesia start | 9 |
| Discharges before anesthesia end | 63 |

These findings can overlap. They cannot be subtracted from raw rows to calculate
a final cohort size.

### Raw disposition evidence

The current candidate mortality mapping recognizes:

| Raw description | Rows |
|---|---:|
| `Expired` | 1,012 |
| `Home Routine` | 45,358 |
| All other descriptions or missing descriptions combined | 19,358 |

**The 1,012 rows are not 1,012 indexed patient deaths.** Repeated operations,
conflicts, hospitalization linkage, adult eligibility, index selection, and
unknown evidence have not been applied.

Observed descriptions also include `Hospice Facility`, `Hospice Home`,
`Acute Care Facility (not this hospital)`, and many other destinations. The
configured unknown descriptions `Transfer` and `Hospice` are not those exact
strings. Unrecognized descriptions remain unknown in the implementation, but
the dictionary still needs a deliberate review rather than assumptions.

The source column named `BIRTH_DATE` contains numeric values 17 through 90 in
the audit inventory, consistent with an age-like representation. This observation
does not independently establish its documented meaning or any top-coding rule.
ASA codes appear as `1.0` through `6.0`, with 6,970 missing rows; the corresponding
description inventory is available for review.

## Concrete blockers

### 1. Clinical approvals and reviewer evidence are absent

All six main review fields in the supplied study settings are false.
`reviewer` and `evidence` are empty. There is no completed local approved
configuration, and `docs/respiratory_label_map.csv` contains only its header.

The gate is therefore an actual unmet study prerequisite, not a missing package
or a command-syntax problem. Flags were not changed to claim an unperformed review.

### 2. None of the seven configured lab aliases exists in the source

Matching is exact and case-sensitive. The fresh source-name inventory gives:

| Concept | Configured alias | Exact alias matches | Observed candidate source name | Raw rows for candidate name |
|---|---|---:|---|---:|
| Hemoglobin | `HGB` | 0 | `Hemoglobin` | 791,335 |
| Platelets | `PLT` | 0 | `Platelets` | 659,714 |
| Creatinine | `CREATININE` | 0 | `Creatinine` | 739,343 |
| BUN | `BUN` | 0 | `Urea nitrogen` | 736,978 |
| Sodium | `SODIUM` | 0 | `Sodium` | 835,978 |
| Potassium | `POTASSIUM` | 0 | `Potassium` | 786,678 |
| Glucose | `GLUCOSE` | 0 | `Glucose` | 826,188 |

These candidate names are review inputs, not automatically approved replacements.
With the current aliases, the raw lab-name filter would select zero candidates.
Merely enabling review flags would not make this a valid ten-concept lab analysis.
If strict timing were separately resolved, the name mismatch could instead leave
every laboratory feature missing and permit a misleading mostly-static model.

Unit mappings also differ from the actual source:

- `Hemoglobin` has 753,469 rows labeled `G/DL`, but the current candidate map
  contains `g/dL` and `g/L`. Only 35 hemoglobin rows use exact `g/dL`.
- `Platelets` has 651,737 rows labeled `THOUS/MCL` and 7,977 labeled
  `THOUS/ CU MM`; neither spelling is in the candidate unit map.
- Creatinine, glucose, BUN, sodium, and potassium have additional uppercase unit
  spellings, alongside some currently recognized spellings.
- Some source-name groups contain units such as `G/TOT VOL`, `mg/d`,
  `MMOL/TOT VOL`, or `Unknown`. Their presence makes blanket case-normalization
  or name-only mapping insufficient to establish specimen compatibility.

The name/unit/encounter inventories support a source-specific review. They do
not prove every measurement with a candidate name is the intended specimen or
was available before anesthesia.

### 3. Strict result availability cannot be established from these lab headers

The actual lab schema has `Collection Datetime` but no result-release timestamp.
The supplied feature map chooses `availability: strict` without a `result_time`
column mapping.

After review gating is resolved, the adapter would still reject this strict
configuration with:

```text
Strict mode requires an explicit release-time column map
```

A real study needs either a verified release-time source or an explicitly
documented collection-proxy protocol with `proxy_lag_hours: 24`. The proxy is an
availability assumption, not proof of release before the cutoff.

### 4. Respiratory ascertainment remains unapproved

Both study and outcome settings disable respiratory, and its mapping rules are
empty. Actual complication inventories contain exact combinations of element,
abbreviation, context, and value, including literal `None` and `Respiratory`.
Those raw strings do not by themselves establish reviewed postoperative positives,
explicit negatives, conflicts, or indexed-patient event adequacy.

The actual respiratory CLI attempts stopped at the primary review gate first.
They did not test or approve respiratory semantics.

## Real outputs that exist

```text
artifacts/real-readiness-20261018/
  audit/audit.json
  audit/*.inventory-*.csv           17 files
  verify_real_cli.py                reproducible actual CLI checks
  cli_checks.json                  exact subprocess evidence
  report.md                        explicitly marks research results unavailable
```

The current campaign has no `cohort.parquet`, saved patient partitions,
`models.joblib`, `metrics.json`, `performance.csv`, `predictions.npz`,
`explain.json`, or `stability.json`.

Consequently, no actual-data AUROC, average precision, Brier score, calibration
estimate, operating-point performance, or SHAP result can be reported from this
run. Synthetic numbers were not copied into this evidence.

The evidence script passed Ruff lint/format checks and returned no LSP errors.
The YAML language server is not installed; actual configuration loading was
exercised by the successful audit and CLI invocations. The earlier 28-test
synthetic regression suite is software evidence, not real research validation.

## What is needed to produce real research results

1. Review and version the source-specific lab names, specimen compatibility,
   units, conversion factors, and bounds using the new inventories.
2. Resolve result availability: supply verified release times or record the
   explicitly chosen 24-hour collection-proxy assumption.
3. Complete the age, ASA, anesthesia-boundary, static-provenance, hospitalization,
   and mortality-disposition reviews with reviewer identity and evidence.
4. Retain mortality-only analysis unless respiratory rules and ascertainment
   adequacy are independently established.
5. Use a new analysis output root, run data construction and leakage checks,
   inspect actual cohort/assessability/event/missingness counts, and confirm
   partition adequacy before fitting.
6. Run training, validation calibration, explanations, and stability; then freeze
   and perform the single held-out evaluation without changing sealed inputs.

The existing [codebase guide](codebase-guide.md) contains the commands and stage
dependencies. The fresh audit provides real review material. End-to-end research
execution remains blocked by the specific prerequisites above; it has not been
certified by this readiness check.
