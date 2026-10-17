# Task completion log

## Discovery

### Read complete plan synopsis repository and history

Read every section of the supplied Markdown plan and every paragraph/table of
the Word synopsis. Inspected current history, raw dataset table names and
headers, available Python/uv, staged changes and local project memory.
Both source documents prescribe the same bounded study. No pre-existing
implementation or tests existed.

### Record protocol alignment and shared module contracts

Recorded cohort, endpoint, timing, split, modeling, calibration, evaluation and
explanation contracts in `protocol.md` and `implementation-contract.md`.
The optional VitalDB extension is excluded from core work. Review gates are
explicit and default to unapproved.

## Environment

Created Python package metadata and exact Python pin `3.11.9`. `uv lock` and
`uv sync --locked` exited 0; `uv run --locked python --version` returned
`Python 3.11.9`. The lockfile records the resolved environment. Clinical outputs
are excluded from Git without altering the pre-existing staged `.gitignore`.

### Configure study mappings gates and private outputs

Added unreviewed study/outcome/feature maps, local configuration template and
explicit mortality-only default title. Separate review flags cover identifiers,
age, ASA, cutoff, static provenance and mortality linkage/dispositions;
respiratory adds phase, negative semantics and event-adequacy gates.

## Data and modeling implementation

Implemented cohort conflict quarantine and first eligible adult operation
selection, nullable labels, exact respiratory tuples, unit-normalized temporal
lab selection/provenance, leakage checks and patient-independent stratified
assignments. Modeling, calibration and evaluation details are recorded in
`model-implementation.md`; explanation work is recorded separately.

The first test run exposed a read-only pandas index array in unknown-label
split assignment and a float32-vs-float64 expectation mismatch in a SHAP
probability check. Assignment now copies before shuffling; the independent
expected logit is explicitly float64 without weakening its tolerance.

The first synthetic CLI run exposed nonserializable cohort exclusion metadata
inherited by feature tables. Feature metadata is now separated from the cohort
exclusion table. Actual rerun outcomes are recorded in `verification.md`.

### Audit age ASA identifiers outcomes and timestamps

The real-data audit ran successfully and reproduced the source counts. It wrote
private schemas, key counts, duplicate/conflict counts, coding/respiratory/lab
inventories, timestamp flags and SHA-256 hashes. `data_dictionary.md` records
aggregate findings, not clinical approval.

### Reconcile duplicates and index eligible adult operations

Exact duplicates collapse, conflicts quarantine the entire operation, and the
first eligible operation precedes outcome filtering. Missing ASA/discharge do
not cause later operations to replace the index. Ambiguous first timestamps
exclude the patient rather than imposing identifier-based chronology.

### Validate mortality hospitalization linkage and unknown states

Implemented reviewed disposition mapping and operation/hospital containment
checks. Missing, conflicting, unlinked, transfer and unmapped evidence stays
nullable. Qualified review remains required for real mappings.

### Audit respiratory semantics and enforce endpoint decision

Implemented exact element/abbreviation/context/value mapping, explicit negatives,
contradiction handling and literal `None` preservation. The default endpoint is
disabled, with a narrowed mortality title and independent review gates.

### Freeze units availability rules and lab lookback

Versioned maps require reviewed concepts, units, specimen compatibility and
plausibility bounds. Strict release availability and the explicit 24-hour
collection proxy are separate paths. Real mappings are not falsely marked frozen.

### Extract features and enforce temporal leakage invariants

Implemented lazy mapped/windowed lab loading, normalized latest eligible
selection, individual provenance and raw rejection counts. Tests exercise
inclusive 30-day/24-hour boundaries, future values, conflicts, unknown units
and attempts to alter a feature without selection evidence.

### Assess events and freeze patient independent splits

Implemented single seeded mortality-stratified 70/15/15 assignment, one-time
unknown-primary allocation, deterministic input-order independence and explicit
insufficient-event failure. Private split tables and endpoint counts are saved
before model fitting; no calendar-temporal claim is made.

## Freeze-boundary regression

A persisted synthetic campaign completed mortality evaluation but correctly
rejected respiratory test access after `demo.py` changed while the campaign
was running. Comparing recorded/current SHA-256 values identified that exact
source file; the freeze guard was not bypassed. The final proof must run after
all source changes and commits, with source left untouched throughout.

## Models, calibration and experiment boundary

### Train paired models using isolated training crossvalidation

Implemented full three-candidate LR and twelve-candidate XGBoost searches on
the same training patients, storing all candidate scores, selected parameters,
training prevalence and LR coefficient encodings. The persisted synthetic CLI
completed these full searches for both endpoints.

### Fit validation calibrators and fixed sensitivity thresholds

Implemented validation-only scalar logistic recalibration without base refit
and the highest threshold retaining at least 80% sensitivity. Synthetic
respiratory calibration had nonpositive slopes and emitted explicit warnings;
the study does not silently substitute a calibrator or optimize on test data.

### Freeze models thresholds and explanation analysis settings

Implemented SHA-256 seals over code, lockfile, configs, partitions, model bundle,
explanations and stability results. Frozen development and premature test access
are rejected by regression tests; observed mid-run source drift was also rejected
through the actual CLI. Final unchanged-source campaign evidence follows.

## Final campaign and reports

### Unlock frozen test evaluation with paired uncertainty

The final unchanged-source campaign on `a0a75fc` evaluated both synthetic
endpoints successfully, once each, after genuine hash seals. Each produced
finite paired raw/calibrated tables and 1,000 paired patient-bootstrap samples,
including operating-point uncertainty and undefined-resample accounting.
Actual attempts to retrain frozen models and repeat test evaluation exited 1
with the intended messages.

### Generate research reports flow diagram and limitations

Generated `performance.csv`, `intervals.csv`, calibration plots, grouped/global/
local explanation figures, stability JSON and aggregate `report.md`. Added
`workflow.md` with the data-flow diagram, private-artifact boundaries and
limitations. Synthetic artifacts are explicitly labeled; no clinical findings
or approval are claimed.

### Record optional VitalDB exclusion from core study

Recorded the plan's optional-extension decision in protocol, workflow and README.
No VitalDB mixing, target-cohort tuning, extra endpoint or web app was added.

## Final verification

### Exercise synthetic pipeline through actual CLI commands

`uv run --locked preop-xai demo --output artifacts/demo` exited 0, completed
all persisted stages for both endpoints and wrote `demo_complete.json` with
`passed: true`. Forty paired stability refits and all four additivity checks
passed. `verification.md` maps exact invocations to artifacts.

### Audit local EPIC and prove unreviewed modeling rejection

The final actual-source audit exited 0. The real training command using the
shipped unreviewed configuration exited 1 before data/model access. Clinical
semantics remain a human review requirement, not a silently deferred software
feature or a fabricated experiment.

### Run scientific tests lint formatting and diagnostics

On final source: 28 tests passed without skips; Ruff lint/format checks passed;
installed basedpyright reported zero errors, warnings or notes. Three external
SHAP/Matplotlib deprecation warnings remain visible. No test was weakened,
suppressed or deleted to obtain a pass.

### Review evidence and commit each verified increment

Reviewed the scientific boundaries, source diffs, actual command behavior and
generated plots. Implementation is split into five verified descriptive commits:
`67282fd`, `d5009ab`, `f4552a6`, `5cbb964`, and `a0a75fc`.
No attribution trailers were added. The user's pre-existing staged root
`.gitignore` was neither changed nor included in these commits.

## Delivery and cleanup receipts

### Document every completed task and preserved artifacts

Every task is recorded in this completion log or `workflow.md`; exact command
scenarios, scientific invariants, evidence paths, regression findings and
self-review are in `verification.md`. The final audit and explicitly synthetic
results are intentionally retained under ignored `artifacts/study/` and
`artifacts/demo/`. The locked environment remains available for reproduction.

### Remove owned run roots caches and resources

All owned command sessions exited before teardown. Removed each path below
and checked afterward that it did not exist:

- `C:/Users/LENOVO/AppData/Local/Temp/preop-ulw-WgyiyZ`
- `.pytest_cache`
- `.ruff_cache`
- `src/preop_xai/__pycache__`
- `tests/__pycache__`

The run root contained the owned runtime/transpiler/Matplotlib caches. The
failed-worker `.omo` QA tree and superseded synthetic campaign were also removed
with absence receipts. Shared caches, the project environment, authorized data,
final evidence and the durable notepad were preserved. No browser/server/
container/listening-port resource was started.

### Report verified scope limitations and atomic commits

The implementation, actual-source audit, complete synthetic campaign, 28 tests
and static checks are verified. Real clinical experiments require the plan's
documented age/ASA/timing/provenance/outcome reviews; none was fabricated.
The final handoff reports this distinction, evidence locations and all atomic
commit hashes. No push or unrelated staged-file commit was performed.
