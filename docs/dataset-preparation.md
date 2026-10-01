# PreOp-XAI Dataset Preparation

Status: REAL_DATA_PENDING. The commands here are implemented and fixture-tested,
but remain researcher-gated and have not been run against real data. Last
updated: 2026-10-01.

## Commands

Full release (default scope):

```
uv run preop-risk plan-download --config configs/research.yaml --scope full-release
uv run preop-risk download-data --config configs/research.yaml --scope full-release
uv run preop-risk verify-data --config configs/research.yaml
uv run preop-risk prepare-data --config configs/research.yaml
```

Required tables only (fallback scope):

```
uv run preop-risk plan-download --config configs/research.yaml --scope required-tables
uv run preop-risk download-data --config configs/research.yaml --scope required-tables
uv run preop-risk verify-data --config configs/research.yaml
uv run preop-risk prepare-data --config configs/research.yaml
```

The default scope is `full-release`, pending the measured storage check from
the authenticated inventory. If the measured requirement with margin exceeds
free disk, the project falls back to `required-tables` and records the reason.
Paths do not appear in these commands because roots come from the environment
or the `--config` file: the raw root is `INSPIRE_DATA_DIR`, derived
patient-level tables live under `PREOP_PRIVATE_WORK_DIR`, and run outputs live
under `PREOP_RUNS_DIR`. Nothing patient-level is written inside the repository.

`download-data` is run by the researcher in a separate local terminal (see
`docs/data-access.md`). It prompts interactively for credentials, or, on systems
with GNU Wget, documents the official Wget `--ask-password` flow as an
equivalent alternative. Retries, timeouts, and concurrency are bounded and
configurable; defaults: 3 retries with backoff, per-request timeouts, and 2
concurrent transfers. Output paths are validated to stay inside
`INSPIRE_DATA_DIR`; redirects are accepted only to the official host.

## Logical dependency map

Logical roles are public; physical files are resolved from the inventory.

- Operations: the cohort anchor. The first structurally eligible released
  operation per patient and the operation-start availability boundary are
  derived here.
- Laboratory results: pre-operation baseline labs; joined to the cohort by
  patient and time, boundary-gated.
- Ward and device observations: pre-operation vitals and measurements;
  boundary-gated.
- Diagnosis codes: comorbidity and history features; boundary-gated by coding
  availability rules established at audit.
- Medications: pre-operation medication exposure; boundary-gated.
- Intraoperative vitals: after the boundary, so excluded from strict features;
  used only for leakage checks and, where protocol rules allow, label context.
- Dictionaries and metadata: code meanings, units, and exclusion lists. Public
  documentation names supporting files such as `schema.csv`, `parameters.csv`,
  and applicable excluded-code files; the exact set is confirmed by the
  inventory. `prepare-data` requires these to validate and decode the tables
  above.

## Storage estimate

No dataset size value is recorded anywhere in this repository, because none is
known before the authenticated inventory. The rule instead:

1. The researcher obtains the inventory; `plan-download` inventories the
   authenticated listings first and prints the measured download total (sum of
   listed file sizes). No byte estimate happens before this inventory exists.
2. Derived size is an estimated range, not a measurement: it combines the actual
   file metadata from the inventory with a representative local conversion pilot
   (running `prepare-data` on a small verified subset and extrapolating), with a
   declared margin recorded next to the estimate. No formula treats derived
   Parquet size as knowable from file metadata alone.
3. Required free space is the measured download total plus the upper bound of
   the estimated derived range, each carrying the declared margin. The decision
   between `full-release` and `required-tables` scopes is made from those
   numbers against current free space (137.72 GiB free at the initial audit;
   re-measure at run time).

## Resumability and the Windows path without Wget

- The static plan file is kept under `INSPIRE_DATA_DIR`; resumable transfer state
  is the measured size of each `<name>.part` file.
- Transfers resume with HTTP range requests from that measured offset; partial
  content is atomically renamed on completion.
- GNU Wget is unavailable on this Windows machine, so `download-data` implements
  the transfer itself over HTTPS with the same semantics (interactive password,
  resume, bounded retries and timeouts). The official Wget instructions with
  `--ask-password` remain a documented alternative wherever Wget exists.
- Interrupted runs are safe to re-run: the validated plan defines targets and
  each `.part` file defines its own resume offset.

## Verification semantics

`verify-data` checks each file against the authenticated inventory:

- Size must match the inventory value exactly.
- Every authenticated inventory entry must supply a SHA-256 hash. The verifier
  computes the local SHA-256 and requires it to match before writing the
  verification manifest under `INSPIRE_DATA_DIR`.
- Any size or hash mismatch quarantines the file and exits non-zero; there is no
  silent acceptance.

## Immutable raw versus derived Parquet

- The raw root `INSPIRE_DATA_DIR` is write-once and treated as immutable after
  verification. No pipeline stage modifies it; a test in milestone 2 asserts raw
  hashes are unchanged by `prepare-data`.
- `prepare-data` writes derived Parquet under `PREOP_PRIVATE_WORK_DIR` (typed,
  decoded, but not cohort-filtered). Downstream stages (audit, cohort, labels,
  features, split) read and write under `PREOP_PRIVATE_WORK_DIR`.
- Derived outputs are rebuildable from verified raw files, mappings, code, and
  configuration. Code/config provenance manifests are added by the later run
  orchestration milestone rather than claimed by this preparation command.

## Handoff

Order of commands after verification:

```
uv run preop-risk prepare-data --config configs/research.yaml
uv run preop-risk audit-data --config configs/research.yaml
uv run preop-risk build-cohort --config configs/research.yaml
uv run preop-risk build-labels --config configs/research.yaml
uv run preop-risk build-features --config configs/research.yaml
uv run preop-risk split --config configs/research.yaml
```

`audit-data` must run before the cohort step on real data; its support matrix
decides whether mortality mapping/linkage is unblocked and which conditional
endpoints exist (see `docs/protocol.md`).

## Definition of done for this phase

REAL_DATA_PENDING clears only when all of the following hold:

1. The access checklist in `docs/data-access.md` is complete for the researcher.
2. The inventory exists and `plan-download` printed measured storage numbers.
3. `download-data` completed with every file in state verified.
4. `verify-data` exited zero and wrote its manifest.
5. `prepare-data` completed and `audit-data` is green on the derived root
   (`PREOP_PRIVATE_WORK_DIR`).
6. `docs/progress.md` is updated with the measured facts (table list, sizes,
   endpoint support) obtained from the inventory, citing it as the source.

Until then, every table, cohort, label, feature, model, metric, and figure in
this project is synthetic.
