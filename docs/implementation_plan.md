# PreOp-XAI Implementation Plan

Status: SOFTWARE_IMPLEMENTATION_IN_PROGRESS
Data status: REAL_DATA_PENDING
Last updated: 2026-10-01

This plan is the binding execution order for the PreOp-XAI codebase. It assumes the
frozen scientific rules in `docs/protocol.md`, the tooling and policy choices in
`docs/decisions.md`, and the access procedures in `docs/data-access.md` and
`docs/dataset-preparation.md`. Milestones 1 and 2 are implemented and
fixture-verified; authenticated real-data execution and later milestones remain
pending.

## Normative corrections over the initial outline

These choices override any earlier outline or inline sketch:

1. The Streamlit application has exactly six views, named exactly:
   Run overview; Performance; Explanations; Subgroups and errors; Predict;
   Methods and status.
2. Data acquisition is a full implementation, not a planner-only stub. The commands
   `plan-download`, `download-data`, `verify-data`, and `prepare-data` each perform
   real work: planning from an authenticated inventory, resumable transfer,
   verification, and conversion to derived Parquet.
3. `download-data` is executed by the researcher in a separate local terminal,
   outside captured or shared tooling. Credentials are entered interactively only
   (secure prompt, or the official Wget `--ask-password` flow where Wget is
   available). The implementation enforces bounded retries, timeouts, and
   concurrency, safe output paths, and redirects locked to the official host.
   Archive extraction is not assumed unless an authenticated inventory proves it
   is required and a separately tested safe-extraction contract is added.

## Resource policy

- Python 3.12 only.
- CPU only. No GPU is required or used.
- Training is sequential: one model family at a time, never parallel fits.
- Estimator thread counts default to a maximum of 2 (configurable in YAML).
- Budgets come from YAML configuration: `configs/smoke.yaml` (tiny row counts,
  iteration caps, small explanation background) and `configs/research.yaml`
  (full data within the limits recorded in `docs/progress.md`). Every
  long-running command takes `--config`.

## Path policy

No patient-level or run output is written inside the repository. Three
environment-configured external roots hold everything:

- `INSPIRE_DATA_DIR`: authenticated inventory, download plan and state, and
  verified raw files (write-once).
- `PREOP_PRIVATE_WORK_DIR`: derived patient-level tables (prepared Parquet,
  audit outputs, cohort, labels, features, split assignments).
- `PREOP_RUNS_DIR`: run outputs (synthetic fixtures for demos, model bundles,
  calibration, explanations, lock manifests, evaluation, reports).

Commands resolve these roots from the environment or the `--config` file.
Synthetic test outputs go to pytest temporary directories or an explicitly
configured external run root, never into the repository.

## Test discipline

Every milestone lists its RED tests (written first, failing for the right reason)
and the GREEN condition that ends the milestone. Tests run under pytest inside the
uv-managed environment; the test dependency is added in milestone 1. Intended
commit boundaries are neutral messages to apply once Git is initialized; they are
boundaries, not existing history.

## Milestone 1: Contracts, environment, privacy, synthetic fixtures

Goal: a uv-managed Python 3.12 project skeleton with typed contracts, strict YAML
configuration, privacy guardrails, and seeded synthetic fixtures that structurally
mimic the INSPIRE logical roles without containing any real data.

- Modules (planned paths):
  - `pyproject.toml`, `uv.lock`
  - `src/preop_xai/__init__.py`, `src/preop_xai/cli.py`
  - `src/preop_xai/config.py` (Pydantic v2 strict YAML loader)
  - `src/preop_xai/contracts.py` (typed contracts for tables, runs, bundles)
  - `src/preop_xai/privacy.py` (rejects credential-like values in logs and paths)
  - `src/preop_xai/synthetic/fixtures.py` (seeded generator)
  - `tests/test_config.py`, `tests/test_contracts.py`, `tests/test_privacy.py`,
    `tests/test_synthetic.py`
- RED tests:
  - `test_config_rejects_unknown_keys`: loader must fail on an unknown YAML key;
    fails because the loader does not exist.
  - `test_contract_rejects_availability_at_or_after_operation_start`: contract
    rejects any value whose result availability is at, after, or unverified
    relative to the operation start.
  - `test_privacy_guard_rejects_secret_like_strings`: guard raises on secret
    patterns in paths and log fields.
  - `test_synthetic_fixture_is_seed_deterministic`: two runs with one seed produce
    identical frames; fails until the generator exists.
- Real-surface command: `uv sync --locked`; `uv run preop-risk doctor`;
  `uv run preop-risk synthetic --config configs/smoke.yaml`
- Artifacts: lockfile; synthetic fixture Parquet under the configured
  `PREOP_RUNS_DIR` synthetic namespace (regenerable, never committed).
- Dependency gates: none (entry milestone).
- Checkpoint: `doctor` reports a clean environment on a fresh machine profile.
- Intended commit boundary: `Add environment skeleton, contracts, privacy guards, and synthetic fixtures`

## Milestone 2: Access preparation, local schema and capability audit

Goal: full acquisition commands plus a local audit that records which logical roles
and endpoints the obtained tables can support.

- Modules:
  - `src/preop_xai/acquire/inventory.py` (parse researcher-supplied authenticated
    inventory into a typed download plan)
  - `src/preop_xai/acquire/plan.py` (`plan-download`)
  - `src/preop_xai/acquire/download.py` (`download-data`: interactive credentials,
    bounded retries/timeouts/concurrency, ranged resume with `.part` files and
    atomic rename, safe path handling, host-locked redirects)
  - `src/preop_xai/acquire/verify.py` (`verify-data`)
  - `src/preop_xai/acquire/prepare.py` (`prepare-data`: immutable raw to derived
    Parquet)
  - `src/preop_xai/audit.py` (`audit-data`)
  - `tests/test_acquire_plan.py`, `tests/test_acquire_download.py`,
    `tests/test_acquire_verify.py`, `tests/test_acquire_prepare.py`,
    `tests/test_audit.py`
- RED tests:
  - `test_plan_download_requires_inventory_fields`: plan building fails without
    required inventory fields.
  - `test_download_rejects_redirect_to_foreign_host`: redirect outside the
    allowlisted host is refused; tested against a local HTTP test double.
  - `test_download_resumes_from_recorded_offset`: transfer continues from plan
    state, not from byte zero.
  - `test_verify_fails_on_size_or_hash_mismatch`: verifier quarantines mismatches.
  - `test_prepare_never_mutates_raw`: raw file hashes identical before and after
    preparation.
  - `test_audit_records_endpoint_support_matrix`: audit output lists supported and
    unsupported logical roles and endpoints with reasons.
  - `test_audit_keeps_mortality_blocked_until_linkage_verified`: audit marks real
    mortality as blocked unless direct admission status/linkage and timing
    assumptions are verified.
- Real-surface command: `uv run preop-risk plan-download --config configs/research.yaml --scope full-release`;
  researcher-run `uv run preop-risk download-data --config configs/research.yaml --scope full-release`;
  `uv run preop-risk verify-data --config configs/research.yaml`;
  `uv run preop-risk prepare-data --config configs/research.yaml`;
  `uv run preop-risk audit-data --config configs/research.yaml`
- Artifacts: inventory, download plan, and state files under `INSPIRE_DATA_DIR`;
  derived Parquet and the audit report under `PREOP_PRIVATE_WORK_DIR`.
- Dependency gates: milestone 1 complete. Human gate: the researcher completes the
  access checklist in `docs/data-access.md` before any real inventory or download.
  The audit path must also run green on synthetic fixtures so this milestone is not
  blocked on access approval.
- Checkpoint: audit states, with reasons, which logical roles are usable,
  whether mortality mapping/linkage is verified (real mortality stays blocked
  until it is), and which conditional endpoints (AKI, early ICU admission,
  prolonged invasive support) are usable.
- Intended commit boundary: `Add acquisition commands and local schema and capability audit`

## Milestone 3: Cohorts, labels, features, splits

Goal: the first structurally eligible released operation per patient, endpoint
labels with leakage guards, strict and proxy feature sets, and a validated
split.

- Modules: `src/preop_xai/cohort.py`, `src/preop_xai/labels.py`,
  `src/preop_xai/features.py`, `src/preop_xai/splits.py`;
  `tests/test_cohort.py`, `tests/test_labels.py`, `tests/test_features.py`,
  `tests/test_splits.py`
- RED tests:
  - `test_cohort_selects_first_structurally_eligible_operation_only` (valid keys
    and times, representable age, impossible-sequence and verified donor/ASA-6
    exclusions applied before any endpoint surveillance or feature filtering)
  - `test_cohort_never_prefers_later_operation_for_observability`
  - `test_real_mortality_blocked_until_audit_verifies_linkage`
  - `test_labels_reject_inputs_not_verified_before_operation_start` (at-cutoff,
    post-cutoff, and unverified availability cannot enter a feature row)
  - `test_strict_feature_set_excludes_proxy_variables`
  - `test_split_is_patient_disjoint`
  - `test_split_falls_back_to_grouped_random_when_chronology_invalid`
- Real-surface command: `uv run preop-risk build-cohort --config configs/smoke.yaml`;
  `uv run preop-risk build-labels --config configs/smoke.yaml`;
  `uv run preop-risk build-features --config configs/smoke.yaml`;
  `uv run preop-risk split --config configs/smoke.yaml`
- Artifacts: cohort, labels, feature matrices, and split assignment under
  `PREOP_PRIVATE_WORK_DIR` with JSON manifests.
- Dependency gates: milestone 2 audit green (synthetic fixtures acceptable while
  REAL_DATA_PENDING).
- Checkpoint: label definitions match `docs/protocol.md`; unsupported endpoints are
  omitted with recorded rationale, never silently imputed.
- Intended commit boundary: `Add cohort, labels, features, and patient-disjoint splitting`

## Milestone 4: Training, calibration, thresholds

Goal: four model families trained sequentially on CPU, post-hoc calibration on a
disjoint validation portion, and an explicit threshold policy.

- Modules: `src/preop_xai/models/logreg.py`, `src/preop_xai/models/random_forest.py`,
  `src/preop_xai/models/xgboost_cpu.py`, `src/preop_xai/models/ebm.py`;
  `src/preop_xai/train.py`, `src/preop_xai/calibrate.py`,
  `src/preop_xai/thresholds.py`; `tests/test_train.py`, `tests/test_calibrate.py`,
  `tests/test_thresholds.py`
- RED tests:
  - `test_training_runs_sequentially_with_thread_cap` (default max 2 estimator
    threads, configurable)
  - `test_calibration_wraps_frozen_estimator` (sklearn FrozenEstimator; the base
    estimator is never refit during calibration)
  - `test_calibration_uses_disjoint_validation_only`
  - `test_threshold_omitted_when_no_feasible_policy` (a threshold is emitted only
    if a feasible operating policy was defined before lock; otherwise threshold
    artifacts are absent by design)
- Real-surface command: `uv run preop-risk train --config configs/smoke.yaml`;
  `uv run preop-risk calibrate --config configs/smoke.yaml`
- Artifacts: fitted model bundles under `PREOP_RUNS_DIR/<run>/models/` with
  manifests; calibration parameters and validation metrics JSON.
- Dependency gates: milestone 3 artifacts green.
- Checkpoint: calibration quality recorded on disjoint validation; threshold
  decision (adopt or omit) recorded with reason.
- Intended commit boundary: `Add sequential CPU training, FrozenEstimator calibration, and threshold policy`

## Milestone 5: Explanations and stability

Goal: TreeSHAP explanations computed on the raw margin scale, kept separate from
calibrated probability outputs, plus stability summaries.

- Modules: `src/preop_xai/explain/shap_tree.py`, `src/preop_xai/stability.py`;
  `tests/test_explain.py`, `tests/test_stability.py`
- RED tests:
  - `test_explanations_are_on_raw_margin_scale` (no calibrated probability leaks
    into explanation outputs)
  - `test_shap_background_is_training_split_only` (configurable cap via the
    active config)
  - `test_stability_summary_records_seed_dispersion` (seed and resample repeats
    within the smoke or research budget)
- Real-surface command: `uv run preop-risk explain --config configs/smoke.yaml`
- Artifacts: explanation tables and figures plus stability summaries under
  `PREOP_RUNS_DIR/<run>/explanations/`.
- Dependency gates: milestone 4 bundles green.
- Checkpoint: explanation scale documented in every artifact; stability spread
  recorded per endpoint and family.
- Intended commit boundary: `Add raw-margin TreeSHAP explanations and stability summaries`

## Milestone 6: Experiment lock and evaluation

Goal: freeze cohort/labels/features/split/models/calibration, then evaluate exactly
once on the locked test portion.

- Modules: `src/preop_xai/lock.py`, `src/preop_xai/evaluate.py`,
  `src/preop_xai/metrics.py`; `tests/test_lock.py`, `tests/test_evaluate.py`
- RED tests:
  - `test_evaluate_refuses_to_run_before_lock`
  - `test_evaluate_aborts_on_lock_hash_mismatch` (any post-lock change to an input
    manifest invalidates the lock)
- Real-surface command: `uv run preop-risk lock --config configs/smoke.yaml`;
  `uv run preop-risk evaluate --config configs/smoke.yaml`
- Artifacts: lock manifest (config, code state, data manifests, hashes) and the
  single locked evaluation report under `PREOP_RUNS_DIR/<run>/evaluation/`.
- Dependency gates: milestones 4 and 5 green.
- Checkpoint: after lock, any pipeline change requires a new lock and a recorded
  reason; there is no silent re-evaluation.
- Intended commit boundary: `Add experiment lock and locked evaluation`

## Milestone 7: Bundle and Streamlit

Goal: trusted local bundles and a localhost synthetic-first UI with the six
normative views.

- Modules: `src/preop_xai/bundle.py` (manifest-hash-verified local bundle loader);
  `app/streamlit_app.py` and `app/views/` with exactly the views Run overview;
  Performance; Explanations; Subgroups and errors; Predict; Methods and status;
  `tests/test_bundle.py`, `tests/test_ui_apptest.py`
- RED tests:
  - `test_bundle_loader_refuses_unverified_manifest`
  - `test_ui_renders_all_six_views_on_synthetic_bundle` (Streamlit AppTest, one
    assertion pass per view)
  - `test_predict_view_uses_local_bundle_only` (no network calls during inference)
- Real-surface command: `uv run streamlit run app/streamlit_app.py`
- Artifacts: verified bundle directory under `PREOP_RUNS_DIR/<run>/bundles/`;
  UI cache via `cache_resource` only, in memory.
- Dependency gates: milestone 5 green for synthetic demo bundles; real bundles
  additionally require milestone 6.
- Checkpoint: UI binds to localhost, defaults to the synthetic demo bundle, and
  labels every page with the current data status.
- Intended commit boundary: `Add verified local bundles and six-view Streamlit app`

## Milestone 8: Reproducibility and reporting

Goal: one-command orchestration, provenance, and reporting assembly.

- Modules: `src/preop_xai/run_all.py`, `src/preop_xai/report.py`,
  `src/preop_xai/provenance.py`; `tests/test_run_all.py`, `tests/test_report.py`
- RED tests:
  - `test_run_all_reproduces_identical_artifacts_for_fixed_seed_and_config`
  - `test_report_links_each_checklist_item_to_existing_evidence_or_marks_pending`
- Real-surface command: `uv run preop-risk run-all --config configs/smoke.yaml`;
  `uv run preop-risk report --config configs/smoke.yaml`
- Artifacts: run manifest, provenance graph, assembled report under
  `PREOP_RUNS_DIR/<run>/report/`, updated `docs/reporting-checklist.md` evidence
  pointers.
- Dependency gates: all earlier milestones green.
- Checkpoint: a fresh checkout reproduces the synthetic smoke run bit-identically
  for stored tabular artifacts; the real-data run remains REAL_DATA_PENDING until
  access is granted and every earlier gate has passed on real inputs.
- Intended commit boundary: `Add orchestrated run, provenance, and reporting assembly`

## Final gates

All of the following must hold before any scientific claim is drafted:

1. `uv sync --locked` succeeds from a clean checkout.
2. `uv run preop-risk doctor` reports green.
3. `uv run pytest` passes with the full smoke configuration suite.
4. `uv run preop-risk run-all --config configs/smoke.yaml` completes end to end
   on synthetic fixtures and reproduces stored artifacts.
5. The Streamlit AppTest suite passes for all six views.
6. For real-data claims only: the access checklist in `docs/data-access.md` is
   complete, `verify-data` and `audit-data` are green on the real inventory, and
   the locked evaluation has run exactly once.
7. `docs/progress.md`, `docs/reporting-checklist.md`, and the README are updated to
   match reality before any claim is written.

## QA teardown

After any QA session: remove regenerated caches and temporary outputs outside
the configured external roots; confirm no patient-level file, credential, or
authenticated URL is present in the repository tree; confirm the repository tree
contains only intended files; and return the machine to the resource posture
recorded in `docs/progress.md` before leaving the session.
