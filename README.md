# PreOp-XAI

PreOp-XAI is a research-only codebase for training and evaluating explainable
machine learning models that predict postoperative outcomes from values and
results verified as available strictly before the start of a patient's first
structurally eligible released operation. The target dataset is INSPIRE,
release 1.4.2, a credentialed research dataset hosted on PhysioNet
(https://physionet.org/content/inspire/1.4.2/, DOI
https://doi.org/10.13026/1eay-yc85).

## Research-only warning

This project does retrospective research. It is not a medical device, it
provides no clinical decision support, and no output may be used for patient
care. All interpretation is descriptive and noncausal; see `docs/protocol.md`.

## Current status

- Code: SOFTWARE_IMPLEMENTATION_IN_PROGRESS. Milestones 1 and 2 are implemented
  and fixture-verified: strict contracts, privacy guards, synthetic fixtures,
  host-locked resumable acquisition, verification, immutable preparation, and
  evidence-gated capability audit. Modeling, evaluation, bundles, and UI remain
  pending.
- Data: REAL_DATA_PENDING. No dataset files have been obtained, and no access
  was evidenced in this session; access is researcher-driven per
  `docs/data-access.md`. Everything currently producible is synthetic only, and
  no scientific result exists or is claimed.

## Prerequisites

- Python 3.12
- uv (observed: 0.11.21)
- CPU-only machine; the resource policy lives in `docs/implementation_plan.md`

## Setup

```
uv sync --locked
```

## Command-line interface

Console script `preop-risk`, invoked as `uv run preop-risk <command>`:

| Command | Purpose |
| doctor | Implemented: check software and scientific readiness |
| synthetic | Implemented: generate seeded synthetic fixtures |
| plan-download | Implemented: build a download plan from an authenticated inventory |
| download-data | Implemented: researcher-run authenticated resumable transfer |
| verify-data | Implemented: verify files and write a provenance manifest |
| prepare-data | Implemented: convert mapped raw files into derived Parquet |
| audit-data | Implemented: write an evidence-gated capability report |
| build-cohort | First structurally eligible released operation per patient |
| build-labels | Endpoint labels per the protocol gates |
| build-features | Strict and proxy feature matrices |
| split | Patient-disjoint split (chronology only if audited as valid) |
| train | Train the four model families, sequentially, CPU only |
| calibrate | FrozenEstimator calibration on disjoint validation |
| explain | Raw-margin TreeSHAP with training-only background |
| lock | Freeze the experiment into a hashed manifest |
| evaluate | Single evaluation against the locked test portion |
| report | Assemble reporting artifacts and checklist evidence links |
| run-all | Orchestrate the pipeline end to end |

Commands take a YAML configuration, for example `--config configs/smoke.yaml`
or `--config configs/research.yaml`; budgets (row caps, iterations, explanation
background size, threads) come from that file.

## Smoke run and UI (planned)

```
uv run preop-risk run-all --config configs/smoke.yaml
uv run streamlit run app/streamlit_app.py
```

The UI binds to localhost, opens on a synthetic demo bundle, and has exactly six
views: Run overview; Performance; Explanations; Subgroups and errors; Predict;
Methods and status.

## Artifact and data privacy model

- All computation is local. Telemetry, experiment-tracking services, and cloud
  inference are off (decision D-018).
- Credentials are entered interactively by the researcher only; they never
  appear in arguments, config files, logs, chat, or the repository.
- Real raw, derived, and run roots live outside the repository at
  environment-configured paths (`INSPIRE_DATA_DIR`, `PREOP_PRIVATE_WORK_DIR`,
  `PREOP_RUNS_DIR`); the raw root is write-once. Authenticated-only metadata
  (physical names, URLs, sizes, checksums, schemas) stays in those local roots
  and is never committed.
- Bundles load only from trusted local paths after manifest hash verification.

## Verification commands

Milestone 1 and 2 verification:

```
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run preop-risk doctor --config configs/smoke.yaml
uv run preop-risk synthetic --config configs/smoke.yaml --runs-dir <external-path>
```

`run-all` remains planned and is not available yet.

Pass criteria for the full gate set are listed under Final gates in
`docs/implementation_plan.md`.

## Documentation

- `docs/implementation_plan.md`: milestones, tests, artifacts, gates
- `docs/decisions.md`: dated technical decisions
- `docs/progress.md`: evidence, status, next commands, blockers
- `docs/data-access.md`: official sources, researcher checklist, handling rules
- `docs/dataset-preparation.md`: acquisition, verification, preparation
- `docs/protocol.md`: frozen scientific rules
- `docs/reporting-checklist.md`: TRIPOD+AI and PROBAST+AI evidence map
