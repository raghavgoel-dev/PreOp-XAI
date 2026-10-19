# Minor-project report: result and figure audit

Reviewed on 19 October 2026. This is a documentation-only inspection, not a new
model experiment. The implementation plan is in
[report-artifacts-plan.md](report-artifacts-plan.md).

## 1. Source and review boundary

Supplied document:

```text
C:\Users\LENOVO\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\F781BF988A0AD2E4F3FE3365F691CE7D45FA2167\transfers\2026-42\PreOp_XAI_Minor_Project_Report (1).docx
```

Document SHA-256:

```text
b20b62dc2e612846c59eba6a3fa7e37876dc70bbb5de48460c89e26d0c19a8c9
```

All 506 nonempty text/table/image body blocks were extracted and read, including
Appendix C. All eight result images were visually inspected. Table/figure numbers
below are the Word report's numbers, not newly generated project results.

The report describes public revision
`919a07506573b77a9113a54332379280c97a4d66`. The local revision inspected here is
`1285f8409d5a0936c16f30eb964f33bbfe8e51f8`, with a clean working tree before this
documentation work. Current source and selected local aggregate artifacts were
inspected; models were not refitted, raw patient records were not reviewed, and
the held-out evaluation was not rerun.

## 2. Main finding: preserve two different kinds of output

The report explicitly separates:

| Evidence | Meaning | Storage consequence |
|---|---|---|
| A | Project implementation and attributed historical verification | Preserve campaign identity, actual audit/status/metric evidence, and limitations |
| B | Published benchmark values, principally Table 5.14 | Store as attributed context, never project metrics or acceptance targets |
| C | Artificial report examples: Tables 5.17-5.20 and 5.23; Figures 5.7-5.14 | Archive the exact report values/images as references; compute future project results separately |

The report's numerical illustrations are **not outputs of the fitted LR/XGBoost
pipelines**. Matching their AUROC, event counts, calibration, or stability values
is not a goal for real or synthetic project training. The plan preserves the
specific report examples and adds the missing output types to actual campaigns.

### Comparison with available local evidence

`artifacts/reliability-20261018/status.json` records a completed **synthetic**
campaign, not a clinical study. Its `performance.csv` files contain:

| Endpoint | Test n / events | LR raw AUROC / AP | XGBoost raw AUROC / AP |
|---|---:|---:|---:|
| Mortality | 90 / 16 | 0.6739864865 / 0.2953669530 | 0.7048141892 / 0.3761641464 |
| Respiratory | 90 / 12 | 0.5267094017 / 0.1469522028 | 0.5288461538 / 0.1756242572 |

Both respiratory validation calibration slopes are negative:
`-0.5495885985` and `-0.5767432164`. Their calibrated outputs are labeled
`invalid-diagnostic-only`; they must not be replaced by the report's favorable
illustrations. Mortality LR calibrated Brier is `0.1450543116`, not the report's
illustrative `0.0094`.

The report's statement that artifacts were unavailable applies to the public
checkout it inspected. Ignored local artifacts are available here. Its historical
28-test statement must remain historical; `docs/completion-log.md` separately
records 109 tests on 18 October 2026. Neither count was rerun in this review.
Current protocol 1.1 also distinguishes invalid/unestimable calibration and
saved-model inference; the report's older capability description is not the
complete current contract.

## 3. Exact numerical reference inventory

Values in this section are transcribed from the supplied report, including its
display precision. They are category C unless explicitly stated otherwise.

### Table 5.17: illustrative mortality discrimination and calibration

| Metric | LR raw | LR calibrated | XGB raw | XGB calibrated |
|---|---:|---:|---:|---:|
| AUROC | 0.8796 | 0.8796 | 0.9023 | 0.9023 |
| Average precision | 0.1092 | 0.1092 | 0.1384 | 0.1384 |
| Brier score | 0.0095 | 0.0094 | 0.0094 | 0.0092 |
| Offset intercept | -0.4054 | 0.0296 | 0.1617 | 0.0150 |
| Joint intercept | -0.1490 | 0.4485 | -0.4823 | 0.2995 |
| Joint slope | 1.0815 | 1.1160 | 0.8056 | 1.0830 |

### Table 5.18: illustrative mortality operating point

| Quantity | LR scenario | XGBoost scenario |
|---|---:|---:|
| Validation-selected threshold | 0.006810 | 0.011601 |
| TP | 89 | 80 |
| FP | 3188 | 1842 |
| TN | 6712 | 8058 |
| FN | 11 | 20 |
| Sensitivity | 0.8900 | 0.8000 |
| Specificity | 0.6780 | 0.8139 |
| Precision / PPV | 0.0272 | 0.0416 |
| NPV | 0.9984 | 0.9975 |
| Accuracy | 0.6801 | 0.8138 |
| F1 | 0.0527 | 0.0791 |
| Predicted positives / 10,000 | 3277 | 1922 |

### Table 5.19: illustrative respiratory discrimination and calibration

| Metric | LR raw | LR calibrated | XGB raw | XGB calibrated |
|---|---:|---:|---:|---:|
| AUROC | 0.8513 | 0.8513 | 0.8773 | 0.8773 |
| Average precision | 0.4049 | 0.4049 | 0.4706 | 0.4706 |
| Brier score | 0.0593 | 0.0588 | 0.0562 | 0.0551 |
| Offset intercept | -0.2778 | -0.0084 | -0.1765 | -0.0048 |
| Joint intercept | -0.1933 | -0.1004 | -0.4523 | -0.0339 |
| Joint slope | 1.0548 | 0.9481 | 0.8074 | 0.9827 |

### Table 5.20: illustrative respiratory operating point

| Quantity | LR scenario | XGBoost scenario |
|---|---:|---:|
| Validation-selected threshold | 0.072946 | 0.080390 |
| TP | 619 | 628 |
| FP | 2267 | 1890 |
| TN | 6933 | 7310 |
| FN | 181 | 172 |
| Sensitivity | 0.7738 | 0.7850 |
| Specificity | 0.7536 | 0.7946 |
| Precision / PPV | 0.2145 | 0.2494 |
| NPV | 0.9746 | 0.9770 |
| Accuracy | 0.7552 | 0.7938 |
| F1 | 0.3359 | 0.3785 |
| Predicted positives / 10,000 | 2886 | 2518 |

### Table 5.23: illustrative rank perturbation, not SHAP stability

| Condition | Vectors / unique pairs | Mean Spearman | Top-five Jaccard | RMS SD |
|---|---:|---:|---:|---:|
| Mild perturbation | 10 / 45 | 0.9830 | 1.0000 | 0.0140 |
| Moderate perturbation | 10 / 45 | 0.8139 | 0.7630 | 0.0395 |

### Checks performed and limits

All four confusion matrices sum to 10,000. Mortality has 100 events and 9,900
nonevents; respiratory has 800 events and 9,200 nonevents. Independently
recomputed sensitivity, specificity, PPV, NPV, accuracy and F1 match **all 24
displayed rate cells** to four decimals. All four predicted-positive totals match
`TP + FP`. The embedded confusion figures display the same four counts.

The report's prevalence-only Brier references are arithmetically correct:
`0.01 * 0.99 = 0.0099` and `0.08 * 0.92 = 0.0736`. The all-negative accuracies
are 99% and 92%, respectively. Ten vectors/refits yield `10 * 9 / 2 = 45`
unique pairs, not 45 independent experiments.

ROC/AP legend values match the tables at three decimals. Figure 5.10 uses
three-decimal labels; both mortality calibrated Brier bars display `0.009`,
concealing the table's `0.0094` versus `0.0092`. This is reduced display
precision, not a conflicting count. Future plots should display four decimals
for Brier and retain full-precision source values.

AUROC, AP, Brier, fitted calibration parameters, selected thresholds and rank
summaries **cannot be independently numerically verified from the DOCX alone**.
It contains raster plots and rounded tables, not the underlying score arrays,
bin membership or rank vectors. There are no embedded chart workbooks; the
custom XML is an empty bibliography record. The plots are visually consistent
with the table summaries, but visual agreement does not recover their data.

### Published context: Tables 5.14 and 5.15, category B

These values were checked against the report's own text, not independently
re-extracted from the publications in this documentation review.

| Report reference | Values to preserve as attributed context |
|---|---|
| Lee [2] | XGBoost AUROC 0.9376; PR summary 0.1593; best external AUROC 0.941; 454,404 adults |
| Choi [13] | Internal/external AUROC 0.960/0.932; PR summary 0.216/0.122; Brier 0.0015/0.0036; populations 276,341/63,384 |
| Hadaya [14], complete | LR/XGB AUROC 0.894/0.900; mAP 0.48/0.50; recall 0.265/0.270; 8.8% prevalence; estimated 1,003,703 admissions |
| Hadaya [14], sparse | LR/XGB AUROC 0.836/0.836; probability-plot slopes 0.862/0.975 and intercepts 0.04/0.01; PR summary not extracted |
| Bihorac [3] | Complication AUROC 0.82-0.94; mortality 0.77-0.83 across 1-24 months; 51,457 patients; PR summary not extracted |

The report's selected mortality ranges, AUROC 0.932-0.960 and PR summary
0.122-0.216, and respiratory range 0.836-0.900 agree with those entries. Preserve
the original metric names, populations, horizons and model variants. Do not
convert mAP/AUPRC to project AP, probability-plot slopes to logit slopes,
missing values to zero, or benchmark ranges to required model scores.

## 4. Figure-by-figure storage requirements

| Report figure | DOCX ZIP member | Content and future project equivalent |
|---|---|---|
| 5.7 | `word/media/image8.png` | Mortality calibrated LR/XGB ROC and PR panels, diagonal ROC reference, PR prevalence 0.01 |
| 5.8 | `word/media/image9.png` | Mortality raw/calibrated reliability curves, separate LR/XGB panels, ten equal-frequency bins and ideal line |
| 5.9 | `word/media/image10.png` | Mortality `[[TN, FP], [FN, TP]]` count matrices, fixed thresholds, logarithmic shading |
| 5.10 | `word/media/image11.png` | Calibrated AUROC/AP/Brier grouped bars for both outcomes and models |
| 5.11 | `word/media/image12.png` | Respiratory ROC/PR counterpart, PR prevalence 0.08 |
| 5.12 | `word/media/image13.png` | Respiratory raw/calibrated ten-bin reliability counterpart |
| 5.13 | `word/media/image14.png` | Respiratory confusion-matrix counterpart |
| 5.14 | `word/media/image15.png` | Mild/Moderate schematic normalized importance means with sample SD; mean Spearman/Jaccard bars |

Archive all eight original image byte streams in the future reference import;
do not redraw them from rounded metrics and call that exact reproduction.
Figure 5.14's empirical counterpart must use actual paired bootstrap SHAP
refits labeled LR/XGBoost, not reinterpret Mild/Moderate as model names.
Figures 5.1-5.6 are process/architecture diagrams, not measured outcome graphs.
They can remain documentation; no fabricated numerical cohort flow is needed.

### Appendix C construction to retain in reference metadata

- Mortality seed `20261019`; respiratory seed `20261020`; independent validation
  and evaluation samples of 10,000 each; exactly 100/800 events per sample.
- Correlated standard-normal model noises, correlation `0.92`.
- `s = d*y + z`; `l = logit(pi) + d*s - d*d/2`.
  Mortality LR/XGB `d = 1.60/1.75`; respiratory `d = 1.50/1.65`.
  LR raw logit `0.92*l + 0.15`; XGB raw logit `1.22*l + 0.55`.
- Validation-only logistic recalibration and highest threshold retaining at
  least 80% sensitivity. Evaluation diagnostics do not refit predictions.
- Ten equal-frequency calibration bins; nominal 1,000 rows each in these examples.
- Rank seed `20261021`; base weights ordered Age, ASA, Creatinine, Hemoglobin,
  BUN, Glucose, Sodium, Platelets, Potassium, Sex:
  `(0.23, 0.20, 0.15, 0.12, 0.10, 0.07, 0.05, 0.035, 0.025, 0.02)`.
  Multiply by `exp(epsilon)` with normal SD `0.12` or `0.38`; normalize each of
  ten vectors per condition to sum one. Error bars use sample SD (`ddof=1`).
  RMS SD is `sqrt(mean(feature sample variances))`.

The appendix does not specify the RNG implementation, precise draw/shuffle
order, correlated-noise construction, optimizer configuration or original
full-precision arrays. A seed plus these constants is insufficient to promise
bitwise regeneration. Exact archival import is achievable; numerical recreation
requires the original generation code/arrays or a separately labeled new example.

## 5. Current code versus required artifacts

| Area | Existing source/output | Gap for this report |
|---|---|---|
| Performance | `evaluate.py:evaluate_models`; `metrics.json`, `performance.csv`, `intervals.csv` | CSV lacks calibration estimates, operating counts/rates, accuracy and alert totals |
| ROC/PR | Saved `predictions.npz`: `y`, `names`, `probabilities` | No ROC/PR images or machine-readable curve coordinates |
| Calibration | `evaluate.py:_bins`; `calibration.png`; `bins`/`raw_bins` in JSON | Five fixed-width bins, not ten quantiles; no bin boundaries/events/empty-bin register or dedicated CSV |
| Confusion | TP/FP/TN/FN and threshold in JSON | No matrix image/CSV; accuracy and predicted-positive fields absent |
| Model comparison | Endpoint performance CSVs | No same-campaign two-endpoint metric comparison figure/table |
| SHAP | `explain.py:explain_models`; `explain.json`, `figures/`, private NPZ/local figures | Existing capability; preserve it and index its aggregate files; do not invent clinical values for Table 5.22 |
| Stability | `stability.py:_summarize`/`run_stability`; `stability.json`, private refit arrays | No summary/pairwise/importance CSVs or stability images; schematic RMS SD differs from patient-centered SHAP variability |
| Reporting | `reporting.py:build_report` | Dumps aggregate JSON and indexes explanation/calibration images; no report-numbered table/figure map |
| Freeze | `workflow.py:_sealed_inputs`/`_check_seal` | Existing campaigns cannot be rerun or rewritten to add exports; deterministic postprocessing needs a separate derivative directory |

### Other outcome-section items

- Tables 5.12-5.13: retain audit counts, cohort/exclusion/assessability/split
  evidence and explicit unavailable clinical results. The inspected real-readiness
  audit agrees with 65,728 information rows, 39,685 patients, 64,354 operation IDs,
  29,079,344 lab rows, 1,374 duplicate keys, ten conflicts, 7,484 invalid starts
  and 7,498 invalid ends. Its nine admission and 63 discharge flags also agree.
  These are source/audit counts, not final cohort totals; flags can overlap.
- Table 5.16 and Appendix B: current primary reviews are false, respiratory is
  disabled, and no release-time mapping is supplied. Store evidence status,
  not a made-up respiratory clinical result or approval.
- Table 5.21: preserve LR coefficients, additivity checks, successful paired-refit
  counts, undefined pairs, missingness contributions and baseline shifts.
- Table 5.22: preserve the ten-concept allowlist and interpretation qualifications.
  Albumin, prothrombin time, procedure and comorbidity rankings are not outputs
  of this project's fixed feature schema.
- Section 5.21, Appendix C.5 and the conclusion: selected clinical parameters,
  final clinical event counts, runtime/peak memory and clinical performance
  remain unmeasured. Export observed evidence if available, otherwise an
  unavailable reason. No new measurement was made in this review.

## 6. Review receipt

This review verified table arithmetic, visible figure/table agreement, source
artifact coverage, current local synthetic evidence and report provenance.
An automated source-to-document comparison matched all 104 value cells in
Tables 5.17-5.20 and 5.23 exactly, preserving their displayed precision.
All eight result-figure mappings and local documentation links were checked;
`git diff --check` passed. Only the four documented Markdown files changed.
Underlying illustrative arrays, publication source values and clinical outcomes
were not independently reproduced. No application code, configuration, tests,
existing artifacts or the supplied DOCX were changed.
