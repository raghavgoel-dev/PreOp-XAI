# Plan: persist the report's results, values, graphs and curves

Status: **implemented and verified on 19 October 2026**. The requirements below
remain the specification; [execution evidence](report-artifacts-execution.md)
records the delivered paths, 222 passing tests, command receipts, numerical/privacy
checks, visual inspection and source-integrity limitations. The exact reference is
`artifacts/report-reference-20261019-b20b62dc`; the final completed-fixture derivative
is `artifacts/report-export-fixture-20261019-result-exports`. The inspected `-v3`
capture is retained too; all 36 aggregate file bytes, including eleven PNGs,
match the canonical derivative.
Read [report-results-audit.md](report-results-audit.md) for the original inventory.

## 1. Desired result and boundaries

The implemented contract delivers both:

1. An exact, explicitly illustrative archive of the supplied report's numerical
   tables and embedded result images.
2. Real campaign exports of the same metric and figure types, derived from
   that campaign's saved predictions, explanations and bootstrap results.

Do not tune models to equal the report's illustrative values. Do not rewrite
existing campaigns, change clinical review flags, change seeds/search spaces,
enable respiratory, refit models/calibrators, rerun held-out evaluation, or add
features/models to make the figures look favorable. The future exporter must
preserve protocol 1.1 invalid/unestimable calibration behavior.

The original planning session made no application changes. Its specified importer,
exporter, numerical tables, figures, CLI, reporting and tests are now implemented.
No historical campaign was retrained, recalibrated, reevaluated, resealed or changed.

## 2. Implementation map

The inspected source revision is
`1285f8409d5a0936c16f30eb964f33bbfe8e51f8`. Recheck the current tree before
editing; do not assume it still matches this review.

| Existing seam | Implemented extension |
|---|---|
| `evaluate.py:ModelEvaluation`, `_operating`, `evaluate_models` | Add accuracy/alert counts for new evaluations; reuse fixed probabilities for exports |
| `evaluate.py:_bins` | Retain existing five-bin protocol output; add a separately named quantile-bin export |
| `stability.py:_summarize`, `run_stability` | Reuse existing pairwise summaries and saved grouped contributions; no refits in rendering |
| `explain.py:explain_models` | Preserve existing global/local figures and additivity metadata; no new SHAP fitting in exporter |
| `reporting.py:build_report` | Index the explicit export manifest and formatted aggregate tables/figures |
| `workflow.py:run_stage`, `_check_seal`, `_guard_mutation` | Wire read-only derivative export without weakening evaluation/development guards |
| `cli.py` | Add the proposed `export-results` command with explicit source/destination arguments |
| New `src/preop_xai/result_artifacts.py` | One focused module for curve/bin/table generation and file-only plotting |
| New `scripts/import_report_reference.py` | Separate DOCX reference importer; no clinical/model imports |
| Existing model/explanation/workflow test files | Test numerical contracts, privacy, freeze and actual CLI export |

Use existing dependencies and naming/style. Add no web UI, notebook, external
service, new model or general reporting framework.

## 3. Storage layout and provenance

### 3.1 Exact report reference: isolated root

```text
artifacts/report-reference-20261019-b20b62dc/
  source/PreOp_XAI_Minor_Project_Report.docx
  reference_manifest.json
  tables/
    table_5_17_mortality_metrics.csv
    table_5_18_mortality_operating_point.csv
    table_5_19_respiratory_metrics.csv
    table_5_20_respiratory_operating_point.csv
    table_5_23_rank_perturbation.csv
    table_5_14_published_benchmarks.csv
    evidence_status.csv
  figures/
    figure_5_7_mortality_roc_pr.png
    figure_5_8_mortality_calibration.png
    figure_5_9_mortality_confusion.png
    figure_5_10_endpoint_comparison.png
    figure_5_11_respiratory_roc_pr.png
    figure_5_12_respiratory_calibration.png
    figure_5_13_respiratory_confusion.png
    figure_5_14_rank_sensitivity.png
  construction.json
  README.md
```

Import the actual DOCX bytes and eight ZIP image members identified in the audit.
Preserve image bytes, not screenshots or re-encoded versions. Extract named
tables by caption and verify headers/content rather than depending on body-block
indices. Store numeric `value` and original `display_value` separately so
`0.011601` and trailing zeros survive as report evidence. Mark published entries
`evidence_category=B`, the five illustrative tables/eight images `C`, and
historical project assertions `A` with their historical date and qualification.

`reference_manifest.json` must contain schema version, source basename/SHA-256,
import timestamp, original inspected revision, each report table/figure number,
DOCX member where applicable, evidence category, output path/SHA-256 and
`underlying_arrays_available=false`. Use portable relative paths, not the
sender's WhatsApp path. `construction.json` retains every Appendix C constant
listed in the audit, including the missing RNG/draw-order/optimizer details as
unavailable, not invented defaults.

`evidence_status.csv` maps Tables 5.12-5.13, 5.16, 5.21-5.22, Appendix B and
C.1/C.5 to source evidence or an unavailable reason. Preserve Table 5.15's
benchmark qualifications with Table 5.14; these are not campaign scores.

Keep this root separate from every study root. Do not name reference files
`metrics.json`, `stability.json` or `explain.json`: current report discovery
recursively loads those names. Never put this archive underneath a clinical
campaign. Its README must state that these score streams are artificial, not
fitted project models, and cannot be used for inference or clinical conclusions.

### 3.2 Campaign exports: fresh derivative root

```text
artifacts/<campaign-id>-result-exports/
  report_artifacts.json
  campaign_summary.csv
  endpoint_comparison.csv
  endpoint_comparison.png
  report.md
  mortality/
    discrimination_calibration.csv
    operating_point.csv
    confusion_counts.csv
    roc_points.csv
    pr_points.csv
    calibration_bins_fixed.csv
    calibration_bins_quantile.csv
    roc_pr.png
    confusion_matrices.png
    calibration_quantile.png
    stability_summary.csv
    stability_pairs.csv
    stability_importance.csv
    stability_importance.png
    stability_agreement.png
  respiratory/                       only when source evidence supports it
```

The source campaign remains unchanged. Preserve existing `metrics.json`,
`performance.csv`, `intervals.csv`, `predictions.npz`, `calibration.png`, model
bundles, explanations, private arrays, freeze and evaluation markers in place.
Do not copy private arrays into the aggregate derivative. New campaign metrics
may include additive fields; legacy metrics must remain readable without edits.

The export manifest must record:

- `schema_version`, source campaign identity, evidence kind
  (`synthetic`, `clinical-research`, or `report-illustration-reference`),
  source revision from the campaign, exporter revision/source hashes, dependency
  versions, creation time and endpoint/partition.
- Source manifest, status, freeze and evaluation-completion hashes; hashes of
  each consumed metrics/prediction/stability/explanation file.
- Every exported file's relative path, hash, table/figure role, source files,
  model/variant, denominator, units/scale, availability and calibration status.
- Fixed-bin and quantile-bin rules, display precision, ROC/PR definitions,
  threshold policy, unavailable reasons, and any legacy provenance limitations.

Never claim the historical campaign used the current exporter source. It did
not. Keep historical source provenance and derivative provenance distinct.
No identifiers or row-level outcomes/predictions belong in this manifest.
The complete artifacts tree remains ignored and subject to existing storage
rules; an aggregate directory is not automatic permission to publish.

## 4. Required metric and table contracts

### 4.1 Discrimination and calibration: Tables 5.17 and 5.19

`discrimination_calibration.csv` has one row per endpoint/model/variant:

```text
endpoint,partition,model,variant,n,events,nonevents,prevalence,
auroc,average_precision,brier,training_prevalence_brier,
test_prevalence_brier_reference,offset_intercept,joint_intercept,joint_slope,
calibration_diagnostic_status,calibration_status,probability_use,evidence_kind
```

Read estimates from `metrics.json`; do not refit calibration in the exporter.
Use `raw_calibration` for raw rows and `calibration` for calibrated rows.
Preserve diagnostic convergence/status and nulls. The separately named
`test_prevalence_brier_reference = prevalence * (1 - prevalence)` is descriptive;
it is not the existing `training_prevalence_brier`, which evaluates the frozen
training-prevalence constant on test outcomes. Keep both.

Use project `average_precision`, labeled AP in figures, not trapezoidal PR area.
Retain full precision in CSV/JSON; round only presentation. Disabled/missing
endpoints produce an unavailable status entry, not an all-zero metric row.
For an unestimable calibrator, keep a calibrated availability entry in the
manifest with a reason; do not create identity-calibrated probabilities.
Finite nonpositive-slope diagnostics can be exported only with their explicit
invalid-fit labels, matching current research evaluation policy.

### 4.2 Operating point: Tables 5.18 and 5.20

`operating_point.csv` has one row per available calibrated model operating point:

```text
endpoint,partition,model,n,events,nonevents,threshold,threshold_source,
tp,fp,tn,fn,sensitivity,specificity,ppv,npv,accuracy,f1,
predicted_positives,predicted_positive_fraction,predicted_positives_per_10000,
calibration_status,classification_use,evidence_kind
```

The threshold comes from validation and is applied with `p >= threshold`.
Never choose it using exported test curves. Store:

```text
accuracy = (tp + tn) / n
predicted_positives = tp + fp
predicted_positive_fraction = (tp + fp) / n
predicted_positives_per_10000 = 10000 * (tp + fp) / n
```

The last field is a normalized rate, not an assertion that test n is 10,000.
Other rates use the formulas in the audit. Zero denominators remain null.
For new evaluations, add accuracy to `_operating` so its individual and paired
bootstrap intervals follow the existing operating-metric path; do not bootstrap
count totals or invent historical intervals. Include the new field in the
paired operating-metric list. Export existing intervals unchanged and clearly
mark accuracy intervals unavailable for legacy metrics that do not contain them.

`confusion_counts.csv` is a four-cell long table keyed by endpoint, model,
true class and predicted class, with count, threshold and status. Matrix layout
is `[[TN, FP], [FN, TP]]`. Class 1 always means the endpoint event.

### 4.3 Campaign evidence: Tables 5.12-5.13, 5.16 and 5.21-5.22

`campaign_summary.csv` contains source audit totals, indexed-patient totals,
exclusion-reason counts, per-endpoint assessable/unknown/event counts,
partition denominators, selected settings/CV AP, review/availability/mapping
status, explanation/additivity status and successful stability counts.
Read the existing aggregate JSON, selection, calibration and bundle metadata;
do not read raw CSVs, Parquet partitions or fitted joblib models for this export.

Store unavailable quantities with a reason, not zero. Audit flags may overlap;
cohort exclusions can have operation-row versus patient denominators. Keep
denominator and unit columns, and do not calculate a false patient flow by
subtracting unrelated source flags. Include measured runtime/peak memory only
when the source campaign has an actual measurement receipt. No instrumentation
expansion is required just to fill these absent report cells.

Keep LR coefficients and their scaling/encoding qualifications at their current
source path. Link rather than invent odds ratios/reference categories. Table
5.22 is interpretation guidance, not a measured ranking. Do not add automated
cross-model SHAP agreement: it is not needed to reproduce the report outputs.

## 5. Required curve and figure contracts

### 5.1 ROC and PR: Figures 5.7 and 5.11

Read only completed evaluation `predictions.npz`, matching named rows by
`names`, never by assumed dictionary order. Validate binary `y`, unique names,
array shapes, finite probabilities in `[0,1]`, endpoint n/event agreement with
metrics and alignment across models/variants. Do not load partitions or call
model prediction APIs.

Export all raw and available calibrated curve coordinates:

```text
roc_points.csv:
endpoint,model,variant,point_index,fpr,tpr,threshold,threshold_kind

pr_points.csv:
endpoint,model,variant,point_index,recall,precision,threshold,threshold_kind
```

Retain complete distinct-threshold ROC points, including endpoints. PR's terminal
point has no threshold; its blank threshold has `threshold_kind=none`.
Represent a ROC infinity sentinel with a blank numeric threshold and
`threshold_kind=positive_infinity`, not a nonstandard JSON number or a fabricated
finite value. Keep finite thresholds as full-precision numbers.

`roc_pr.png` contains two panels comparing LR and XGBoost. Show calibrated
curves when available with valid/invalid status visible; show raw-only curves
and an explicit reason when calibration is unavailable. Raw curves remain
stored even if not all are overlaid. ROC axes span `[0,1]`, include the diagonal;
PR includes **that endpoint's actual evaluation prevalence**, not fixed 1%/8%.
Legends show AUROC/AP and variant. Single-class inputs make ranking curves
unavailable with a reason; do not plot invented curves.

### 5.2 Calibration: Figures 5.8 and 5.12

Keep existing source `calibration.png` and five fixed-width `bins`/`raw_bins`
unchanged. Export `calibration_bins_fixed.csv` with five probability intervals
`[0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]`, retaining empty-bin rows.
Compute counts/events from saved probabilities because legacy JSON omits
empty-bin edges and event counts.

Add `calibration_bins_quantile.csv` and `calibration_quantile.png` as an
explicitly separate descriptive representation, not a replacement protocol.
Request ten probability-quantile bins separately per model/variant. Collapse
duplicate quantile edges; assign tied probabilities together. Include the
minimum in the first interval and use right-closed subsequent intervals.
Constant probabilities form one bin. Record requested and effective bin counts,
actual edges, closure, collapsed-edge count and strategy in manifest metadata.
Actual clinical bins need not have 1,000 observations or exactly equal counts.

Both bin CSVs contain:

```text
endpoint,model,variant,bin_id,lower,upper,n,events,nonevents,
mean_predicted,observed_fraction,empty,calibration_status
```

For empty bins, n/events/nonevents are zero, but means are null. Totals must
reconcile to all evaluated observations/events for each series. The quantile
figure has separate LR/XGB panels, raw/calibrated lines and the ideal diagonal.
Record axis limits; a focused risk-range view must be labeled as such, not
suggest that no individual risks lie beyond bin means. Do not add smoothing,
confidence bands or calibration-parameter intervals not in the source analysis.

### 5.3 Confusion matrices: Figures 5.9 and 5.13

Draw LR/XGB matrices from the same frozen counts used by the operating table.
Show true/predicted class labels, integer counts, threshold, endpoint, n and
calibration status. Use logarithmic shading only for positive cells; mask zero
cells for the color scale while annotating them as zero. Do not alter counts
to make log shading possible. Missing calibrated operating points receive an
unavailable panel/reason rather than an artificial all-negative classifier.

### 5.4 Endpoint metric comparison: Figure 5.10

`endpoint_comparison.csv` draws only from this export's performance table,
keyed by endpoint/model/variant. The figure has separate AUROC, AP and Brier
panels. Calibrated comparisons carry invalid-fit status when necessary.
If respiratory is disabled, show mortality only plus its unavailable reason;
never fill respiratory with report illustrations or another campaign's metrics.

Label AP as prevalence-dependent and Brier as lower-is-better; include each
endpoint's prevalence and reference Brier in the table/caption. Use four decimal
labels for Brier so 0.0094 versus 0.0092 is visible. Do not rescale one endpoint
to resemble the report or imply cross-endpoint statistical significance.

### 5.5 SHAP and stability: Figure 5.14 and Tables 5.21-5.23

For exact report preservation, archive the Mild/Moderate reference image and
Table 5.23 unchanged. For project exports, use actual LR/XGB paired-refit
evidence and label it as such; there are no corresponding empirical targets.

Reuse `stability.json` for:

- `stability_summary.csv`: model, requested/successful paired refits, status,
  pair count, defined/undefined Spearman counts, mean Spearman/Jaccard,
  baseline-shift RMS, endpoint, validation/background n and explanation scale.
- `stability_pairs.csv`: original successful draw IDs, unique pair IDs,
  Spearman/null and top-five Jaccard. Map summary pair positions through
  `successful_paired_draws`; do not mistake successful positions for draw IDs.
- `stability_importance.csv`: model/concept, mean absolute grouped importance,
  sample SD of per-refit global importance, top-five inclusion frequency and
  existing patient-centered contribution variability.

Per-refit global importance is
`mean_over_validation_patients(abs(grouped_contributions))`. Compute its
across-refit sample SD (`ddof=1`) from
`private/<model>_stability.npz`; write only aggregate values outside private
storage. Do not export its patient rows, draw arrays or baselines. The schematic
report's RMS SD is not the existing patient-centered SHAP RMS measure; keep
names/definitions separate. Do not force actual importances to sum one.

`stability_importance.png` compares actual LR/XGB concept means with sample-SD
error bars; `stability_agreement.png` shows mean Spearman/Jaccard and successful
refit/pair counts. These are descriptive SDs, not confidence intervals.
If fewer than two successful refits exist, preserve insufficient status and
omit unsupported SD/agreement values. Undefined rank correlations stay null.

Index existing global SHAP bars, XGB beeswarm/dependence figures and explanation
metadata without recomputing SHAP. Local TP/FP/TN/FN images and row-level arrays
remain private and must not be embedded in the aggregate derivative report.
Aggregate explanation figure links can point back to their source campaign;
record the linked file hash in the manifest.

## 6. Execution and compatibility rules

### Command surfaces

Implemented commands, both requiring a fresh destination:

```powershell
uv run --locked python scripts/import_report_reference.py --source "C:\path\PreOp_XAI_Minor_Project_Report (1).docx" --output artifacts/report-reference-20261019-b20b62dc

uv run --locked preop-xai export-results --source artifacts/reliability-20261018 --output artifacts/reliability-20261018-result-exports
```

The illustrative path above is a command template; use the actual supplied
source path recorded in the audit. Both operations require a fresh destination
and refuse overwriting. The campaign exporter requires a destination outside
the source tree, under ignored authorized artifacts storage. Reference import
does not call clinical stages or claim campaign completion.

For each completed endpoint, verify the recorded model hash against
`evaluation_complete.json` and the recorded input hashes in `freeze.json`
against their files before consuming evaluation artifacts. Verify historical
sealed source files by the recorded paths/hashes, not today's `_sealed_inputs`
schema: legacy seals may lack later-added metadata. Do not modify or regenerate
seals. A mismatch stops that endpoint's export with the exact mismatch reason.
If historical source files no longer match, preserve the campaign and report
the blocker; do not skip integrity checks to make an old run exportable.

The example current-source export must therefore be verified, not assumed to
pass. New campaigns after implementation will need their own fresh source
snapshot and legitimate run; never rerun an old test unlock.

An endpoint with only review/audit evidence gets status-only output. A started
but incomplete evaluation is not exportable as completed performance. Missing
unsealed optional SHAP/stability arrays permit other figures, with explicit
unavailable entries; a mismatch of a required sealed file is an integrity
failure, not an optional omission. Validate all required inputs before creating
result files, and write the complete export manifest last.

The exporter reads model bytes only for hashes, never joblib deserialization.
It may read restricted `predictions.npz` and refit NPZ for aggregate generation,
but the report builder must read only aggregate outputs/manifest. Reject
escaping, absolute or private figure references in the aggregate index.
Do not let recursive report discovery cross into reference/other campaigns.

`build_report` should accept an explicit validated export manifest when creating
the derivative report, retaining existing behavior for campaigns without an
export. Use portable relative links, formatted table presentations, visible
evidence labels and a report-number-to-export mapping. Do not relocate patient
files, change ordinary `report` into a fitting/evaluation stage, or imply that
successful report generation proves clinical review.

For new campaigns, expose export as a separate command after the existing
evaluate stage writes its completion marker. Both endpoints' train/calibrate/
explain/stability development must still finish before either freeze. Export
and report generation do not unlock test evaluation, update status to clinical
approval, or mutate frozen development inputs.

## 7. Delivered work packages

All packages below are implemented. Their acceptance evidence is in
`report-artifacts-execution.md`; the numbered requirements are retained for traceability.

1. **Implement exact report reference import.** Add
   `scripts/import_report_reference.py`; extract all five illustrative tables,
   eight exact PNGs, benchmark context, evidence-status entries and Appendix C
   metadata into the isolated reference layout. Verify the supplied DOCX hash
   and caption/member mapping. Acceptance: every displayed value in the audit
   and all eight image-byte hashes match the source; underlying arrays remain
   explicitly unavailable. No synthetic score recreation is required.
2. **Implement metric and curve export.** Add `result_artifacts.py`; extend
   new evaluation schemas with accuracy and alert totals; export the tables,
   ROC/PR points, fixed/quantile bins and missingness/status context above.
   Acceptance: saved probabilities and counts reproduce exported point
   estimates within existing numerical tolerances; no fitting or partition
   loading occurs. Add numerical tests alongside `test_models_contracts.py`.
3. **Implement performance figures.** Render ROC/PR, quantile calibration,
   confusion matrices and same-campaign endpoint comparison from exported
   numerical data. Acceptance: every panel maps to a table/coordinate file,
   uses correct prevalence/threshold/labels and handles invalid/unavailable
   calibration and zero cells honestly.
4. **Implement aggregate stability exports.** Use JSON and private refit NPZ
   without new draws, fitting or SHAP calls. Acceptance: pair counts and means
   reconcile with existing summaries; sample-SD bars come from saved refit
   importances; patient-level data stay private. Extend
   `test_explanations.py`.
5. **Wire CLI, integrity checks and manifest reporting.** Add `export-results`,
   provenance checks and a manifest-driven derivative `report.md`. Acceptance:
   a fresh export leaves the source file set/hashes unchanged, private paths
   are excluded, endpoint gating remains intact and every requested figure
   has a path or an explicit unavailable reason. Extend workflow/CLI tests.
6. **Verify and document the delivered contract.** Run the checks below,
   inspect actual PNGs, update `docs/workflow.md`, `docs/codebase-guide.md`,
   `docs/model-implementation.md`, `docs/explanation-implementation.md` and
   `docs/completion-log.md` to describe only implemented behavior. Mark this
   plan implemented only after acceptance evidence exists. Do not create a
   commit unless the user requests one in that session.

Dependencies: 1 is independent; 2 precedes 3; 2 precedes 4's shared export
schema; 3 and 4 precede 5; all precede 6. Do not start a clinical campaign as a
side effect of these implementation packages.

## 8. Verification contract for implementation

Test machine-consumed values and behavior, not prose, exact Markdown wording or
PNG byte identity for newly rendered plots. Original archived PNG bytes are an
intentional equality contract.

| Scenario | Required evidence |
|---|---|
| Exact reference import | Five table snapshots match source display values; all eight images hash-identical; B/C/A labels preserved; overwrite and wrong-source hash rejected |
| Four report confusion examples | All counts, 24 rates, positive totals and normalized alert rates agree with the audit; no training needed |
| Known saved predictions | ROC coordinates/area, AP, Brier, operating tables and calibration bin totals agree; named-array order permutation does not change model association |
| Curve edge cases | Ties, probability 0/1, terminal PR point, ROC infinity sentinel, single class and zero metric denominator have explicit valid representations |
| Quantile/fixed bins | Events/counts conserved, empty fixed bins retained, duplicate edges collapsed, constant scores handled; no random tie splitting |
| Calibration policy | Fitted, nonpositive-slope and unestimable examples preserve raw/calibrated availability and invalid-fit labels; no identity fallback |
| Stability | Exactly `k*(k-1)/2` unique pairs, correct original draw IDs, correct sample SD, null undefined ranks, partial/insufficient status retained |
| Privacy | Private files/arrays/identifiers absent from aggregate report/export; path traversal and private manifest links rejected |
| Workflow | Actual CLI export never fits, predicts with models, loads partitions or reruns evaluate; source tree bytes/file set unchanged; tampered seal and incomplete evaluation rejected |
| Endpoint comparison | Mortality-only works; disabled respiratory is not borrowed from reference or another campaign |
| Provenance | Source and derivative versions/hashes distinguished; source mutation or missing required evidence blocks completed-result claims |

Use small deterministic synthetic fixtures sized like existing tests. Subscribe
to process completion when exercising the CLI; no sleeps or polling in tests.
Use the same saved arrays across metric, table and image assertions, not
disconnected mocks that could pass while the integration is wrong.

Run once after implementation, fixing any newly introduced failures:

```powershell
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Also run available semantic diagnostics on touched Python files before the
test/build step; report any pre-existing diagnostics separately. Exercise both
proposed command surfaces against a fresh reference destination and a genuinely
matching completed campaign fixture. If current historical source hashes block
export, test the rejection and use a deterministic completed fixture; do not
weaken the seal or launch new clinical work.

Visually open all eight archived figures and every new figure class. Check
unclipped legends/captions, readable thresholds, confusion orientation/counts,
ROC/PR axes, endpoint prevalence, four-decimal Brier labels, quantile metadata,
SD versus CI labels and invalid/unavailable notices. Visual shape need not
match an artificial example when genuine campaign results differ.

Finally, recompute export hashes, resolve all report links, verify each
report-reference table/figure has an evidence label, and compare source campaign
file hashes and file set before/after. Completion means every requested output
is stored or explicitly unavailable for a justified source-data reason, with
no fabricated clinical values and no deferred unimplemented exporter behavior.

## 9. Original handoff prompt

> Implement `docs/report-artifacts-plan.md`, using
> `docs/report-results-audit.md` as the supplied report's reference inventory.
> First recheck current code and local source evidence. Build the exact isolated
> report-reference archive and the read-only campaign result exporter, including
> numerical curve data, tables, PNGs, provenance and deterministic tests.
> Preserve existing campaigns and protocol 1.1 calibration/freeze/privacy rules.
> Do not train toward the illustrative scores, enable clinical gates, rerun
> held-out evaluation or commit without authorization. Verify the actual CLI and
> generated files and document the measured result.
