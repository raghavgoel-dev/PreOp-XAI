# PreOp-XAI Progress

Status: SOFTWARE_IMPLEMENTATION_IN_PROGRESS
Data status: REAL_DATA_PENDING
Last updated: 2026-10-01

## Current evidence

Facts established at project start; nothing here is estimated.

- The repository is initialized on `main`.
- The supplied research-paper draft was read and defines the scientific scope
  recorded in `docs/protocol.md`; official public release documentation was
  consulted separately.
- The supplied feasibility constraints are used as the binding implementation
  audit.
- Python 3.12.9 is available.
- uv 0.11.21 is available.
- A Git identity is configured on the machine; its values are intentionally not
  recorded here.
- Hardware: 12 logical CPUs.
- Memory: 13.86 GiB total, 1.61 GiB free at the initial audit. Memory headroom
  was low; runs under `configs/research.yaml` should start from a lighter
  session and keep estimator threads at the default cap of 2.
- Disk: 137.72 GiB free at the initial audit. Whether this fits the dataset is
  unknown until the authenticated inventory measures it; see
  `docs/dataset-preparation.md`.
- GNU Wget is unavailable on this machine; `download-data` must therefore
  provide its own resumable HTTPS transfer with interactive credentials.
- Milestone 2 software is implemented and fixture-verified: typed authenticated
  inventory parsing, official-host planning, ranged `.part` resume, host-locked
  redirects, size/hash quarantine, immutable raw-to-Parquet preparation,
  evidence-gated capability audit, and the five acquisition CLI commands.
- `INSPIRE_DATA_DIR`, `PREOP_PRIVATE_WORK_DIR`, and `PREOP_RUNS_DIR` are applied
  from the environment and validated as external to the repository.

## Milestone checklist

Milestones refer to `docs/implementation_plan.md`.

- [x] Protocol and toolchain exploration; foundational documentation written.
- [x] M1 Contracts, environment, privacy, synthetic fixtures
- [x] M2 Access preparation, local schema and capability audit (software and
  fixture gates; authenticated real-data execution remains pending)
- [ ] M3 Cohorts, labels, features, splits
- [ ] M4 Training, calibration, thresholds
- [ ] M5 Explanations, stability
- [ ] M6 Experiment lock, evaluation
- [ ] M7 Bundle, Streamlit
- [ ] M8 Reproducibility, reporting

## Exact next commands

Milestones 1 and 2 were verified with these exact commands:

1. `uv sync --locked` (pass; 136 packages resolved from `uv.lock`)
2. `uv run pytest` (pass; 42 tests)
3. `uv run ruff check .` (pass)
4. `uv run ruff format --check .` (pass; 35 files formatted)
5. `uv run basedpyright` (pass; zero errors or warnings)
6. `uv lock --check` (pass)
7. `uv run preop-risk doctor --config configs/smoke.yaml` (pass; software ready,
   credentials not required for synthetic mode, real data blocked)
8. `uv run preop-risk synthetic --config configs/smoke.yaml --runs-dir
   <external-path>` (pass; 64 synthetic rows and three Parquet tables plus a
   manifest written outside the repository)
9. `uv run preop-risk --help` (pass; all five milestone 2 commands registered)
10. Focused milestone 2 CLI, acquisition, audit, and configuration suite (pass;
    23 tests)
11. Repository scans (pass; no no-excuse markers, patient-level files, model
    artifacts, or credentials; only the intentional privacy-test fixture and
    hidden password prompt matched the credential-pattern scan)

The immediate next implementation action is milestone 3: cohort, label,
feature, and patient-disjoint split contracts.

## Blockers

1. No INSPIRE access was evidenced in this session; the researcher checklist in
   `docs/data-access.md` has no evidenced completion.
2. The authenticated inventory is unknown, so physical file names, sizes,
   checksums, and endpoint support cannot be stated anywhere in the repository.
3. GNU Wget is unavailable; the implemented `download-data` command therefore
   uses bounded HTTPX2 transfer with interactive credentials and ranged resume.
4. Free RAM was 1.61 GiB at audit time; large-table research runs may require
   reduced session load before they start.
5. Real mortality mapping/linkage is blocked until the capability audit verifies
   direct admission status/linkage and timing assumptions (see
   `docs/decisions.md`, D-008); only synthetic mortality may run in smoke mode
   until then.

## Scientific completion

None. No data has been obtained, no model has been trained, no metric has been
computed, and no result exists. Any statement of performance, endpoint support,
or feasibility beyond this page would be fabricated.
