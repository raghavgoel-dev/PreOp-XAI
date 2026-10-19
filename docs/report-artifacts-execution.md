# Ultrawork Notepad - report artifact implementation
Started: 2026-10-19

## Plan (exhaustively detailed)
1. Read the complete plan and audit; inspect source, tests, history and prior evidence.
2. Implement the exact DOCX reference importer independently.
3. Implement saved-prediction numerical export and additive evaluation fields.
4. Render performance figures from the exported numerical series.
5. Implement stability aggregation from saved successful refits.
6. Integrate read-only integrity checks, CLI and explicit manifest reporting.
7. Add deterministic numerical, privacy, provenance and workflow regressions.
8. Exercise both command surfaces, historical rejection and completed synthetic fixture.
9. Inspect all reference PNGs and every generated figure class.
10. Verify source immutability, numerical reconciliation, manifests and report links.
11. Run semantic diagnostics, full pytest, Ruff lint and format checks.
12. Update implementation documentation, self-review, remove owned resources and report.

## Success criteria + QA scenarios
- Exact reference: run `uv run --locked python scripts/import_report_reference.py --source`
  with the audit's exact DOCX path and `--output artifacts/report-reference-20261019-b20b62dc`.
  PASS: source hash, 104 displayed values and eight image byte hashes match;
  benchmark qualifications, A/B/C categories and unavailable arrays are preserved.
  Wrong-hash and overwrite commands must fail.
- Historical integrity: run `uv run --locked preop-xai export-results --source
  artifacts/reliability-20261018 --output artifacts/reliability-20261018-result-exports`.
  PASS: matching export or exact seal rejection with no derivative files.
- Completed fixture: run the same command with source
  `artifacts/report-export-fixture-20261019` and fresh sibling `-result-exports`.
  PASS: every required table/figure has data or a justified unavailable entry,
  source hashes/file set are unchanged, all manifest hashes and report links resolve,
  and aggregate files contain no patient identifiers or row-level arrays.
- Numerical regressions: pytest covers curve/bin edge cases, calibration policy,
  operating arithmetic, original stability draw IDs/sample SD, incomplete/tampered
  provenance and unsafe links. PASS: deterministic tests pass without skipped cases.
- Visual inspection: read the eight archived PNGs and each generated figure class.
  PASS: readable unclipped labels, honest status, correct prevalence/thresholds,
  confusion orientation, AP labels, four-decimal Brier and sample SD labels.
- Checks: `uv run --locked pytest -q`, `uv run --locked ruff check .`,
  `uv run --locked ruff format --check .` and semantic diagnostics on touched Python.
  PASS: no new failures; any pre-existing diagnostics reported precisely.
- Stop when all implementation is delivered with evidence and owned resources cleaned.

## Now
Inspect repository contracts tests and source provenance.

## Todo
Follow the ordered plan above and the live phased checklist.

## Findings
- Tier HEAVY: new exporter modules and an integrity/provenance boundary.
- Both supplied documents read completely before implementation.
- HEAD is `1285f8409d5a0936c16f30eb964f33bbfe8e51f8`.
- Existing user changes: `docs/completion-log.md`, `docs/workflow.md`;
  untracked supplied plan/audit. Preserve them.
- No root AGENTS.md or .omo directory exists.
- Memory consulted: preop-project.md. Historical source seals can reject export;
  real clinical review remains unapproved. Do not train or evaluate.
- Skills: bun-1-4 for resident orchestration; programming/Python for implementation;
  git-master for required path history inspection; memory-discipline for durable notes.
- Delegation topology: independent reference importer to a background worker;
  numerical exporter and integrity integration retained by lead; stability/plot lanes
  delegated only after shared schema is established. No planning child: ordered
  work packages already settle dependency order.

## Learnings
- Source campaigns must remain byte-identical; derivative and historical provenance
  must remain separate. Nonpositive calibration stays invalid-diagnostic-only.
- No commits or pushes authorized.

## Resources
- Owned run root: `C:\Users\LENOVO\AppData\Local\Temp\preop-report-ulw-wdfgJo`.
- Runtime caches are under this run root. All subprocesses inherit TMPDIR/TEMP/TMP,
  NODE_COMPILE_CACHE and BUN_RUNTIME_TRANSPILER_CACHE_PATH there.
- Durable notepad is this file; retain it as implementation evidence.

## Transition - implementation
- Discovery complete. Goal registered with exact reference/export command scenarios.
- Shared `result_io.py` defines aggregate rows, table interchange, hashing and safe paths.
- Actual background workers use the available `omo-native-qa-executor` with explicit
  `chatgpt-subscription/gpt-6.1-sol` routing; the stored default category route lacks
  credentials. Lanes: reference-import, result-numerics, result-stability.
- Numerical lane owns evaluate.py plus numerical tables/tests. Stability owns only
  result_stability modules/tests. Lead owns integrity, orchestration, plots, reporting,
  CLI, workflow tests, documentation and final QA.
- Artifact storage is ignored by `artifacts/.gitignore` (`*`, `!.gitignore`).
- No ulw-plan workflow ran; verification gate requires self-review, not a reviewer.

## Now
Archive illustrative report tables figures and provenance (worker); lead builds integrity.

## Todo
Integrate completed numerical/stability lanes, run commands, inspect figures, verify and clean.

## Findings - baseline and implementation
- Original scientific regression command (five original test files, explicit paths):
  `uv run --locked pytest -q tests/test_models_contracts.py
  tests/test_workflow_contracts.py tests/test_explanations.py tests/test_inference.py
  tests/test_data_contracts.py`: PASS, 109 passed, three existing warnings, exit 0.
- Background reference worker first returned QA-only evidence of absent code; sent
  one corrective implementation instruction. Numerical/stability workers created modules.
- Source DOCX independently matches the audited SHA-256; initial reference QA evidence
  is at `artifacts/report-reference-20261019-b20b62dc-qa/`.
- Fresh standalone semantic check resolves new modules, unlike the long-lived LSP
  cache, which currently falsely reports missing new imports. One actual error and
  346 warning diagnostics require inspection; no diagnostics are being suppressed.
- Lead implemented safe aggregate paths, recorded-path historical seal checks,
  source context, explicit manifest validation/reporting, file-only performance figures,
  CLI wiring and completed saved-array integration fixture/tests.
- Fixture is explicitly constructed software evidence, NOT a newly trained campaign.
  It uses an intentionally non-deserializable model sentinel to catch model loading.
  No held-out evaluation, recalibration or bootstrap refit is run.

## Resources - retained evidence
- `artifacts/report-artifacts-qa-20261019/` retains QA receipts, not temporary resources.
- Original regression monitor bash_1 exited 0; no owned process remains from that run.

## QA - first integrated run
- `uv run --locked pytest -q tests/test_result_workflow.py`: PASS, 10 passed,
  three inherited library warnings, exit 0. Captured
  `artifacts/report-artifacts-qa-20261019/integration-first.log`.
- Fixture source before/after snapshot and actual Typer export, tamper/incomplete
  rejection, unsafe links, disabled respiratory and overwrite/storage checks passed.
- Semantic error caught: implicit test-helper import. Fixed with explicit
  `tests.result_fixture` and a package marker; fresh diagnostics must confirm.
- Visual scenario: `read` on
  `<RUN_TMP>/pytest-of-LENOVO/pytest-1/test_cli_exports_named_predict0/artifacts/exports/mortality/roc_pr.png`.
  FAIL: legends overlap ROC/PR panel titles. Changed legends to in-axis placement,
  removed manual outside-layout suptitle positioning; final render must be inspected.
- Privacy case now includes `PRIVATE_SENTINEL_PATIENT_<i>` in an extra source NPZ member;
  all exported CSV/JSON/Markdown must omit the sentinel and any row-level arrays.
- Added fixed CSV headers for empty/unavailable tables, case-insensitive private path
  rejection, and campaign-local legacy report discovery (never nested campaigns).

## Now
Integrate CLI commands and manifest driven reporting.

## Todo
Inspect final lane evidence; exercise both commands; inspect all figures; full checks;
document actual outcomes and clean isolated roots.

## QA - historical command and preservation
- Invocation: `uv run --locked preop-xai export-results --source
  artifacts/reliability-20261018 --output artifacts/reliability-20261018-result-exports`.
- PASS (expected rejection), exit 1. Exact failing recorded input:
  `src\preop_xai\cli.py`; expected
  `ead11230d9a0ed83040fe90b469b717f4948c78c1de0937a5a38364e20b5a382`;
  observed `bdbf2690caa92563bb8a884c2760f4b24fdba90cb518232b71089799150c2c8d`.
- All 116 source file paths and SHA-256 values are identical before/after.
  Derivative destination does not exist. No seal, model or status was modified.
- Raw command receipt: `artifacts/report-artifacts-qa-20261019/historical-export.log`
  (PowerShell Tee-Object UTF-16 encoding). Final structured QA receipt will also
  preserve this result in portable JSON.
- This is an external historical-provenance blocker, not incomplete exporter behavior.
  Successful command proof will use the deterministic completed saved-array fixture.

## Completed increment - stability
- Package 4 integrated: `result_stability.py`, `result_stability_validation.py`,
  `result_stability_plots.py`, `tests/test_result_stability.py`.
- Focused saved-file regression command passed 26 cases; Ruff lint/format passed.
  Original nonconsecutive draw IDs, pair completeness, ddof=1 sample SD, null ranks,
  partial/insufficient statuses, optional versus sealed arrays and CSV-only plots covered.
- Evidence/visual scenarios/cleanup:
  `artifacts/stability-package4-qa-st_01a1541a/st_01a1541a-manual-qa.md`.
  Worker temporary root removed with `CLEANUP_OK` receipt.
- First comparison PNG inspection found top-of-axis 1.0000 labels crowding panel
  titles; added uniform comparison-axis headroom (0..1.08), preserving ROC/PR
  and calibration 0..1 limits. Invalid recalibration is now explicitly labeled.
- Fixed-bin review identified `np.linspace`'s 0.6000000000000001 boundary hazard;
  numerical worker instructed to use exact specified decimal edges and regression
  cases while leaving legacy evaluation bins unchanged.
- Deterministic fixture creation command passed:
  `uv run --locked python tests/result_fixture.py --output
  artifacts/report-export-fixture-20261019`; exit 0. Receipt `fixture-create.log`.
- Added independent serialized-file QA invocation:
  `uv run --locked python tests/result_verification.py --source
  artifacts/report-export-fixture-20261019 --output
  artifacts/report-export-fixture-20261019-result-exports --receipt
  artifacts/report-artifacts-qa-20261019/export-verification.json`.
  PASS requires independently matching ranking/curve integrals, operating counts,
  bin conservation/sample SD, manifest hashes, resolved report links and no identifiers.

## Transition - lane integration
- CLI/integrity/manifest/report integration is implemented; first real CLI integration
  suite passed. Numerical and reference workers remain active and own final evidence.
- Fresh semantic analysis of lead-owned source/fixture/verification files: zero errors,
  230 unsuppressed warnings (dynamic JSON/NumPy typing and repository defaults).
  Full final diagnostics will preserve all warnings and distinguish actual errors.
- First scoped lint caught an overlong metadata literal and an unused verification
  import. Both fixed without suppressions. Final full Ruff checks remain pending.
- Stability test-only casts removed in favor of explicit TypedDict-key narrowing.
  Full final tests will cover this type-only adjustment.
- Additional integration cases cover malformed manifest parsing, status-only evidence,
  case-insensitive private paths and actual raw-only unavailable operating figures.
- Owned cache isolation extended with RUFF_CACHE_DIR/PYTEST_ADDOPTS under RUN_TMP;
  remaining subprocesses set PYTHONDONTWRITEBYTECODE=1. Existing shared caches
  are preserved; only identifiable newly generated bytecode will be cleaned.

## Now
Archive illustrative report tables figures and provenance (reference worker active).

## Todo
Integrate terminal reference/numerical results; run successful fixture export and
independent receipt; inspect final figures; run full checks; finalize docs and clean.

## Recovery and completed numerical/reference increments
- Reference worker stopped at provider quota after writing code/tests, before producing
  the permanent archive. Lead took over directly; no provider/configuration change needed.
- Numerical lane evidence: 71 focused tests passed, scoped Ruff and fresh source semantic
  checks passed; owned cache root removed. See `result-numerics-manual-qa.md`.
- Actual fixture export exited 0. Review caught a manifest-only denominator regression:
  stability files were labeled with test n=8 rather than fixed validation n=4.
  Fixed and added an explicit regression assertion; the final workflow run passed
  15 tests. First generated derivative is superseded and will be removed, not overwritten.
- Corrected plots were visually opened: ROC/PR title overlap resolved; prevalence,
  invalid-fit notices, zero confusion cells, SD-versus-CI and comparison labels readable.
- A behavior-preserving source-context helper move keeps result_artifacts.py focused;
  final command proof will use a fresh derivative destination after source is stable.
- Reference importer split into command, extraction, construction and immutable inventory
  modules. Inventory is a pure-data table; executable modules stay below the size ceiling.
  No clinical/model imports or score recreation were introduced.
- Focused reference tests: 17 passed. Exact supplied-DOCX command then exited 0,
  storing all 104 displayed values, eight original PNGs and 19 archive files at
  `artifacts/report-reference-20261019-b20b62dc`.
- Broad semantic checks found new test-only typing defects in heterogeneous fixture
  mutations/aggregate assertions. Fixed with typed shape/number assertions and split
  focused fixture modules, without weakening any test or suppressing diagnostics.
- Latest full-tree diagnostics: only the four previously documented pandas typing errors
  in untouched `tests/test_data_contracts.py:136,187,188,201`; all new files have zero
  errors. All 3,129 default-mode warning diagnostics remain unsuppressed.

## Now
Run the integrated full check gate and verify both generated artifact surfaces.

## Todo
Full pytest/lint/format; independent exported-file checks; eight reference images and
final figure inspection; update delivered documentation; remove owned QA resources.

## Acceptance evidence
- Full `uv run --locked pytest -q`: PASS, **222 passed**, three existing warnings,
  exit 0 in 61.36 seconds. Receipt: `artifacts/report-artifacts-qa-20261019/full-tests.log`.
- Full `uv run --locked ruff check .` and `ruff format --check .`: PASS, exit 0;
  74 files at that gate. One subsequently added independent QA helper is checked below.
- `tests/result_verification.py` against final `-result-exports-v3`: PASS, eight
  series, 112 fixed/quantile bin rows, 36 artifact hashes and 46 report links.
  Independently reconciles ranking/curve integrals, operating counts, sample SD
  and absence of private arrays/fixture patient identifiers. Receipt:
  `artifacts/report-artifacts-qa-20261019/export-verification.json`.
- Independent source-to-reference check: PASS, 104 displayed values, eight byte-identical
  original images, 18 indexed archive hashes; actual overwrite/wrong-hash CLI calls
  exited 2 without changing existing outputs. Temporary rejection root was removed.
  Receipt: `artifacts/report-artifacts-qa-20261019/reference-verification.json`.
- All eight archived result PNGs were opened via `read` on the exact `figures/`
  paths in the reference archive. Original reduced Brier display precision remains
  preserved, not redrawn or mislabeled as a numerical discrepancy.
- All eleven final PNGs were opened via `read` under final `-result-exports-v3`:
  both endpoints' ROC/PR, quantile calibration, confusion, importance and agreement,
  plus endpoint comparison. PASS: thresholds/classes/count orientation, correct
  prevalence, explicit invalid calibration, four-decimal Brier, quantile labels,
  readable unclipped captions and sample-SD-versus-CI notices.
- Final broad semantic receipt: `semantic-final.json`, four pre-existing errors
  only at `tests/test_data_contracts.py:136,187,188,201`; 3,182 warnings unsuppressed.
  The long-lived LSP has stale new-module import errors; fresh standalone analysis
  resolves imports. No new semantic errors remain.
- Both source trees remain byte/file-set identical after final export and QA:
  fixture 22 files, file-map digest
  `d5009c8d6f30f951008c45101c761503265e011a86398219a861e0e2ce44939e`;
  historical 116 files, digest
  `d5d95f72c000293d2e280f031b24c67442fdef744afdbb44f65a66f7b4e9cff1`.
  Digests are SHA-256 of sorted relative-path-to-SHA-256 maps, before and after.

## External source change
- Initial exact archive captured at 2026-10-19T17:32:05.784Z: DOCX 1,473,964 bytes,
  audited SHA-256 `b20b62dc2e612846c59eba6a3fa7e37876dc70bbb5de48460c89e26d0c19a8c9`.
- The transfer path subsequently has 1,685,758 bytes, modification time
  2026-10-19T17:32:48.397Z, SHA-256
  `55343a2ed80b2019394fee3457a33ed92798bbbe4eaf1a98282423dadf52a21f`.
  Its cause is not inferred. Importer source handling is read-only.
- Actual importer call against this changed path rejected with exit 2; receipt
  `external-source-rejection.log`. No source or fingerprint was overwritten.
  Independent archive verification used the preserved audited DOCX, not the new bytes.

## Self-review
- Tier remained HEAVY: new derivative/provenance boundary; no planning-review gate
  was triggered. Lead reviewed the existing-file diff, new helpers, numerical
  assertions and every criterion's real-surface evidence.
- Each executable new production module is below 250 pure lines. The 357-line
  reference inventory is the explicit pure-data/type-schema exception, not
  executable modeling code. Focused helpers own source context, numerics, plotting,
  integrity and reporting; no new general framework or dependency was introduced.
- Source seals, clinical gates and calibration protocol are preserved. No historical
  model/calibrator/test evaluation was rerun. Test-only fixture fitting in the existing
  suite is separate from read-only export and never touches historical campaigns.
- No explicit Any/cast/type-ignore, warning suppression or skipped tests were added.
- Current exporter provenance is separate from historical source revision; source hashes
  identify the uncommitted implementation actually executed. No project commit or push.

## Now
Clean owned resources and record verification evidence.

## Todo
Remove superseded QA derivatives, worker scratch scripts and isolated runtime caches;
record read-back cleanup receipts; final diff/document check and completion handoff.

## Final canonical output
- The specification's canonical `artifacts/report-export-fixture-20261019-result-exports`
  path is now absent after owned invalid scratch output cleanup. Run the final stable
  command once into this fresh canonical path; retain the verified `-v3` capture too.
  This creates new files in an empty destination, not an overwrite of existing results.
- Recreate only the same owned RUN_TMP for this last command and its independent
  verifier, then remove it again. Earlier cleanup.json remains a historical receipt;
  cleanup-final.json will record the final read-back.
- Correction: the initial full-hex HEAD transcription in this notepad was wrong.
  Bootstrap established short `1285f84`; closing `git rev-parse HEAD` returned
  `1285f84a09d89b9313015565f62328dbbfbc2a54`. No project commit was created.

## Canonical command proof
- Exact goal invocation: `uv run --locked preop-xai export-results --source
  artifacts/report-export-fixture-20261019 --output
  artifacts/report-export-fixture-20261019-result-exports`: PASS, exit 0, fresh directory.
- All 36 aggregate file bytes match the inspected `-v3` capture, including all
  eleven PNGs. Only manifest creation time differs; no plots or results changed.
- Independent canonical receipt: `export-canonical-verification.json`; checks the
  same eight series, 112 bin rows, 36 file hashes, 46 report links, 20 consumed
  source hashes and every delivered exporter source hash.
- Final reference source remains the audited archived bytes; the separately changed
  transfer file is not accepted. The historical CLI source seal rejection remains
  recorded, not bypassed.

## Final cleanup receipts
- `cleanup-final.json`: PASS. Owned RUN_TMP and runtime caches are absent; all
  newly generated owned bytecode was removed without wiping shared caches.
  No owned process, browser, server, port, container or task remains live.
- Removed four worker scratch Python scripts; retained their command/data receipts.
  Removed worker pytest scratch fixtures after retaining ten PNG captures under
  `artifacts/stability-package4-qa-st_01a1541a/visuals/`.
  Lead also opened the insufficient-refit and missing-array/SD-unavailable panels.
- Superseded `-v2` output is absent. The canonical final derivative and the
  byte-identical inspected `-v3` aggregate capture are retained deliverables/evidence.
- Worker temporary-root removal receipts remain in the package QA matrices.
  Reference wrong-source temporary directory removal is recorded in its JSON receipt.
- `immutability.json` records both source file-map digests. The canonical command
  was followed by the same 22-file fixture snapshot; it remains identical.
- Older worker QA selector paths describe the pre-split snapshot. Current focused
  files additionally include `test_result_numeric_edges.py` and
  `test_report_reference_construction.py`; full pytest covered all 222 current tests.
- The final provenance assertions in the standalone verifier passed actual execution,
  Ruff lint/format and fresh semantic analysis (zero errors, 49 unsuppressed warnings).

## Completion audit
| Required deliverable | Current-state evidence |
| --- | --- |
| Exact five-table/eight-figure reference, benchmarks and provenance | Canonical reference archive; reference-verification.json: 104 values, eight original streams, 18 indexed hashes, A/B/C qualifications and unavailable original arrays |
| Read-only numerical/operating/curve/bin/confusion/endpoint outputs | Canonical campaign derivative; export-canonical-verification.json: eight series, 112 bin rows, 36 file hashes, 46 resolved links |
| Stability summaries/figures and original draw/sample-SD definitions | Saved-refit CSVs/PNGs, 26 focused cases, independent SD reconciliation and retained unavailable panels |
| CLI, explicit manifest reporting, tests and documentation | Actual successful importer/export commands, rejection receipts, updated six implementation documents plus this ledger, 222 passing tests |
| Calibration, clinical gates, privacy and freeze integrity | Valid/invalid/raw-only/incomplete/tampered/disabled cases; no patient identifiers or arrays in aggregates; unchanged source maps; historical rejection not bypassed |
| Diagnostics, lint, formatting and visual QA | Full tests/Ruff receipts; no new semantic errors; four pre-existing data-test errors recorded; all eight reference and eleven generated PNGs inspected |
| No project commits/pushes; cleanup | Uncommitted worktree; closing HEAD recorded above; cleanup-final.json read-back receipts, no owned resources left running |

All implementation criteria are fulfilled. Historical source seal mismatch and the
separately changed transfer DOCX are precisely identified provenance limitations,
not deferred implementation. No historical campaign was modified or reevaluated.

## Now
Report implemented changes artifacts and external blockers.

## Todo
Deliver the final handoff with canonical artifact paths, check results and limitations.
