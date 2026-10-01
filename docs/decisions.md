# PreOp-XAI Decisions

Status: living record, append new entries, never rewrite accepted ones.
All entries are dated 2026-10-01, the day the project was scoped.
Format: decision, context, consequences.

## D-001 Python 3.12

Decision: the project targets Python 3.12 only.
Context: 3.12.9 is available on the development machine; a single pinned minor
version keeps the lockfile and CI surface small.
Consequences: syntax and standard library assumptions may require 3.12; other
versions are unsupported rather than half-supported.

## D-002 uv for environment management

Decision: uv (0.11.21 observed) manages dependencies and the virtual environment;
`uv sync --locked` is the only supported setup path.
Context: fast, lockfile-first, reproducible installs without extra tooling.
Consequences: every dependency change must regenerate `uv.lock`; ad-hoc installs
inside the environment are out of contract.

## D-003 Polars and NumPy, no pandas

Decision: DataFrame work uses Polars; array work uses NumPy. pandas is not a
project dependency.
Context: one dataframe idiom keeps contracts, I/O, and tests uniform and keeps the
dependency tree smaller.
Consequences: third-party snippets that use pandas must be translated, not
vendored; adapters that require pandas (for example some model wrappers) are used
through their NumPy interfaces.

## D-004 Pydantic v2 strict YAML configuration

Decision: all configuration loads through Pydantic v2 models in strict mode from
YAML; unknown keys, coerced types, and missing required fields fail fast.
Context: configuration errors should surface at load time, not mid-pipeline.
Consequences: every new option requires a schema change and a test.

## D-005 Official INSPIRE release 1.4.2 only

Decision: the sole data source is the official PhysioNet INSPIRE release 1.4.2
(https://physionet.org/content/inspire/1.4.2/, DOI
https://doi.org/10.13026/1eay-yc85). No mirrors, reposts, or third-party copies.
Context: provenance and license compliance require the canonical release.
Consequences: acquisition tooling locks redirects to the official host and fails
on anything else.

## D-006 Authenticated inventory before physical files

Decision: physical filenames, sizes, checksums, schemas, and dictionaries are
treated as unknown until obtained through the researcher's own authenticated
session; the first acquisition step is always an inventory, never a guessed file
list.
Context: public pages document logical roles only; physical metadata is
authenticated-only.
Consequences: documentation and tests contain no invented file names, sizes, or
counts; planning commands consume an inventory artifact.

## D-007 Availability strictly before operation start

Decision: the prediction time is the operation start. A value enters the strict
feature set only when its result availability is verified to be strictly before
the operation start; values available at the cutoff are excluded. An event time
before the cutoff is not sufficient when result availability is at or after the
cutoff or unverified, and unverified availability is excluded from the strict
analysis. A clearly named proxy sensitivity analysis may include timestamp
proxies, without claiming leakage-free status.
Context: the supplied research-paper draft defines immediate-before-operation
prediction; availability timing, not event timing, decides leakage.
Consequences: contracts enforce verified availability at row build time; the
proxy set is analyzed and labeled separately.

## D-008 Mortality is the primary endpoint

Decision: postoperative in-hospital mortality is the primary endpoint. Real
mortality mapping/linkage is required for any real-data claim and stays blocked
until the local capability audit verifies direct admission status/linkage and
the timing assumptions. Synthetic mortality may be supported in smoke mode only.
Context: endpoint support cannot be verified before authenticated access, so
the real mapping is treated as unverified until the audit resolves it.
Consequences: reports lead with mortality only after the audit unblocks it;
smoke-mode outputs are labeled synthetic-only.

## D-009 Conditional secondary endpoints

Decision: secondary endpoints (acute kidney injury, early ICU admission,
prolonged invasive support) are included only when the capability audit confirms
the required variables exist; otherwise they are omitted with a recorded reason.
Context: endpoint support cannot be verified before authenticated access.
Consequences: reporting never fabricates support; the audit matrix is the source
of truth.

## D-010 Composite endpoints and chronology disabled by default

Decision: no composite endpoint is defined, and chronology-based splitting is
disabled unless the audit demonstrates a valid cross-patient chronology.
Context: composites blur interpretation; an invalid chronology produces false
temporal confidence.
Consequences: endpoints stay atomic and separately reported; the default split
path is grouped random.

## D-011 Patient-disjoint random validation fallback

Decision: when no valid cross-patient chronology exists, splitting is random at
the patient level with all rows of one patient in exactly one partition.
Context: grouped-random is the fallback described by the supplied research-paper
draft.
Consequences: split tests assert patient disjointness; chronology mode requires
an audit flag to activate.

## D-012 Four model families

Decision: exactly four families are compared: penalized logistic regression,
random forest, gradient-boosted trees (XGBoost, CPU-bounded), and Explainable
Boosting Machine.
Context: a span from transparent baselines to strong tabular learners without
GPU dependence.
Consequences: adding a family is a new decision entry plus a protocol amendment,
not a code detail.

## D-013 FrozenEstimator calibration

Decision: post-hoc calibration wraps the fitted estimator with sklearn
FrozenEstimator and fits calibrators on the disjoint validation portion only.
Context: calibration must not refit the base model and must not touch test data.
Consequences: calibration tests assert the base estimator object is frozen and
the validation indices match the split manifest.

## D-014 Threshold omission without a feasible policy

Decision: classification thresholds are reported only if a feasible operating
policy is defined before the experiment lock; otherwise threshold artifacts are
omitted and ranking and calibration metrics carry the report.
Context: a research-only project has no cost structure to justify a cutoff.
Consequences: absence of threshold artifacts is the expected default, not a gap.

## D-015 Raw-margin TreeSHAP, separated from calibrated probability

Decision: tree-based explanations use TreeSHAP on the raw margin with a
training-only background, stored and displayed separately from calibrated
probability outputs.
Context: mixing scales invites misreading additive margin contributions as
probabilities.
Consequences: explanation artifacts declare their scale; UI and report sections
never merge the two scales.

## D-016 Trusted local bundles only

Decision: model and report bundles load only from local paths after manifest
hash verification; nothing is fetched from the network at load or inference
time.
Context: reproducibility and privacy both forbid remote artifact resolution.
Consequences: the bundle loader verifies before use and fails closed.

## D-017 Localhost, synthetic-first UI

Decision: the Streamlit app binds to localhost and starts on a synthetic demo
bundle; real bundles appear only after verification and explicit selection.
Context: the UI is a research inspection tool, and patient-level content must
never be the default surface.
Consequences: AppTest coverage exercises the synthetic path first; every page
shows the current data status.

## D-018 Telemetry and cloud tracking off

Decision: no telemetry, no experiment-tracking services, and no cloud inference
at any point; all computation is local.
Context: patient-level data may not be sent to third parties, and the project
has no need for external tracking.
Consequences: dependencies with mandatory telemetry are excluded; Predict runs
on trusted local bundles only.

## D-019 Environment-configured external data and run roots

Decision: no patient-level or run output lives in the repository. Raw downloads,
inventory, and plan state go to `INSPIRE_DATA_DIR`; derived patient-level tables
go to `PREOP_PRIVATE_WORK_DIR`; run outputs (bundles, explanations, evaluation,
reports, synthetic fixtures) go to `PREOP_RUNS_DIR`. Synthetic test outputs use
pytest temporary directories or an explicitly configured external run root.
Context: repository-internal data paths invite accidental commits of restricted
content.
Consequences: commands resolve roots from the environment or configuration, and
docs and tests never hardcode repository data paths.
