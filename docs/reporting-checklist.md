# PreOp-XAI Reporting Checklist

Status: working checklist, 2026-10-01. Nothing here implies formal TRIPOD+AI or
PROBAST+AI compliance, and no formal reporting review has been performed. The
structure below mirrors the published checklist sections at summary level;
confirm exact item numbering and wording against the official TRIPOD+AI and
PROBAST+AI publications when a report is drafted.

Legend: PENDING = evidence cannot exist yet (blocked on real data or unbuilt
code). PLANNED = the evidence location is defined and the producing step is
scheduled. DONE = evidence exists and is linked.

## TRIPOD+AI item-to-evidence

| Section / item summary | Planned evidence | Status |
| Title identifies prediction-model study | README and report title block | PLANNED (milestone 8) |
| Structured abstract | `PREOP_RUNS_DIR/<run>/report/` assembled abstract | PENDING |
| Source of data (dataset, release, dates, setting) | `docs/data-access.md`, `docs/protocol.md`, inventory manifest | PARTIAL: release and protocol fixed; real access details PENDING |
| Participants (eligibility, cohort flow) | `docs/protocol.md` section 3; cohort manifest with counts | PARTIAL: rules fixed; real counts PENDING |
| Outcome (definition, ascertainment, blinding where relevant) | `docs/protocol.md` section 4; audit endpoint matrix | PARTIAL: primary selected; real mortality linkage blocked pending audit; secondary support PENDING |
| Predictors (definition, measurement, timing) | `docs/protocol.md` sections 2 and 5; feature dictionary from audit | PARTIAL: boundary rule fixed; concrete variable list PENDING |
| Sample size (how determined, flow) | audit-derived counts; split manifest | PENDING |
| Missing data (amount, handling) | milestone 3 missing-data plan and per-variable counts | PENDING |
| Study type and analytical methods (split, tuning, calibration) | `docs/protocol.md` sections 7 to 10; split and calibration manifests | PLANNED |
| Model building per family (hyperparameters, selection) | training configs and manifests under `PREOP_RUNS_DIR/<run>/models/` | PENDING |
| Model performance (discrimination, calibration, CIs) | locked evaluation report under `PREOP_RUNS_DIR/<run>/evaluation/` | PENDING |
| Model updating | not planned; stated as not performed in report | PLANNED (statement) |
| Fairness and heterogeneity (subgroups) | Subgroups and errors view outputs and stability summaries | PENDING |
| Results: participants and model development flow | run manifest and cohort flow numbers | PENDING |
| Results: performance tables and figures | locked evaluation report | PENDING |
| Limitations (bias sources, generalizability) | report limitations section citing audit and protocol | PENDING |
| Interpretation and implications | descriptive, noncausal statements only, per protocol section 12 | PLANNED |
| Funding and conflicts | report front matter | PENDING |
| Protocol and registration availability | this repository: `docs/protocol.md`, `docs/decisions.md` | DONE (docs exist); external registration PENDING (not yet decided) |
| Data and code availability statement | README and report statement consistent with DUA | PENDING |
| Use of generative AI or automated tooling in the work | statement in report per journal policy | PENDING |

## PROBAST+AI domain-to-evidence

Risk of bias and applicability, by domain, with the evidence that will answer
each signalling topic.

| Domain / signalling topic | Planned evidence | Status |
| 1. Participants and data sources: appropriate source, inclusions and exclusions, enrollment timing | `docs/protocol.md` sections 1 to 3; cohort manifest | PARTIAL: rules fixed; real flow PENDING |
| 2. Predictors: defined and measured consistently, available at the prediction time, assessed without outcome knowledge | boundary contract tests; strict/proxy split; audit feature dictionary | PARTIAL: mechanism PLANNED (milestone 3 tests); real confirmation PENDING |
| 3. Outcome: defined consistently, determined without predictor knowledge, correct timing | `docs/protocol.md` section 4; audit endpoint matrix; label build manifests | PARTIAL: primary selected; mortality linkage blocked pending audit; secondary confirmation PENDING |
| 4. Analysis: adequate sample and events, no leakage, valid split, calibration and discrimination both reported, overfitting controls | leakage tests; split manifest; FrozenEstimator calibration; locked single evaluation; stability study | PLANNED for synthetic path; real-data judgment PENDING |
| Applicability concerns overall | report section mapping cohort and predictors to intended research use | PENDING |

## Standing rules for this checklist

1. No row moves to DONE while its evidence does not exist in the repository.
2. Real-data-dependent rows stay PENDING until REAL_DATA_PENDING clears per the
   definition in `docs/dataset-preparation.md`.
3. Claiming formal TRIPOD+AI or PROBAST+AI compliance, or a completed risk-of-
   bias rating, is out of scope for this file and for the project as a whole.
4. The milestone 8 `report` command regenerates the evidence links here; manual
   edits to the Status column without evidence are a process violation.
