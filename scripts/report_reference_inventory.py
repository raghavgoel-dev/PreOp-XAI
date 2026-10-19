"""Immutable audited report inventory and reference archive schema (pure data)."""

from collections.abc import Mapping, Sequence
from typing import TypedDict

Json = str | int | float | bool | None | Sequence["Json"] | Mapping[str, "Json"]

SOURCE_SHA256 = "b20b62dc2e612846c59eba6a3fa7e37876dc70bbb5de48460c89e26d0c19a8c9"
INSPECTED_REVISION = "1285f8409d5a0936c16f30eb964f33bbfe8e51f8"
REPORT_REVISION = "919a07506573b77a9113a54332379280c97a4d66"
HISTORICAL_DATE = "2026-10-17"
INSPECTION_DATE = "2026-10-19"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CAPTIONS = {
    "5.6": "Table 5.6 Prespecified model search space",
    "5.12": "Table 5.12 Available evidence and the claim it supports",
    "5.13": "Table 5.13 Project evidence and clinical result availability",
    "5.14": "Table 5.14 Published benchmarks from related studies category B",
    "5.15": "Table 5.15 Benchmark interpretation and quantities without transferable targets",
    "5.16": "Table 5.16 Recorded respiratory endpoint status",
    "5.17": "Table 5.17 Illustrative mortality discrimination and calibration category C",
    "5.18": "Table 5.18 Illustrative mortality operating point category C",
    "5.19": "Table 5.19 Illustrative respiratory discrimination and calibration category C",
    "5.20": "Table 5.20 Illustrative respiratory operating point category C",
    "5.21": "Table 5.21 Explanation and stability evidence category A",
    "5.22": "Table 5.22 Predictor interpretation without invented SHAP values",
    "5.23": "Table 5.23 Illustrative rank perturbation summary category C",
    "B.1": "Table B.1 Required review and campaign metadata",
    "C.1": "Table C.1 Result provenance and permitted claims",
}
HEADERS = {
    "5.6": ["Setting", "LR", "XGBoost"],
    "5.12": ["Evidence category", "Available information", "Permitted conclusion"],
    "5.13": ["Quantity", "Available finding and provenance"],
    "5.14": [
        "Study and population",
        "Outcome and model",
        "AUROC",
        "AP or AUPRC",
        "Other reported evidence",
    ],
    "5.15": ["Quantity", "Evidence and interpretation"],
    "5.16": ["Required evidence", "Status at inspected revision"],
    "5.17": ["Metric", "LR raw", "LR calibrated", "XGB raw", "XGB calibrated"],
    "5.18": ["Quantity", "LR scenario", "XGBoost scenario"],
    "5.19": ["Metric", "LR raw", "LR calibrated", "XGB raw", "XGB calibrated"],
    "5.20": ["Quantity", "LR scenario", "XGBoost scenario"],
    "5.21": ["Quantity", "Verified status and interpretation"],
    "5.22": ["Concept", "Evidence or diagnostic interpretation"],
    "5.23": ["Condition", "Vectors / pairs", "Mean Spearman", "Top-five Jaccard", "RMS SD"],
    "B.1": ["Review item", "Decision evidence and responsible reviewer"],
    "C.1": ["Category", "Evidence in this report", "Permitted claim"],
}
ROW_LABELS = {
    "5.6": [
        "Search candidates",
        "Structure",
        "Tree count",
        "Learning rate",
        "Other constraints",
        "Selection metric",
    ],
    "5.12": [
        "Direct repository inspection",
        "Repository-recorded source audit",
        "Repository-recorded synthetic campaign",
        "Repository-recorded synthetic checks",
        "Repository-recorded tests",
        "Clinical evaluation",
    ],
    "5.13": [
        "Raw source size",
        "Duplicate and timing flags",
        "Indexed cohort and exclusions",
        "Clinical events and prevalence",
        "Clinical partitions and model scores",
        "Software demonstration",
        "Verification status",
        "Availability and mapping",
    ],
    "5.14": [
        "Lee et al. [2]; four institutions; 454,404 adults",
        "Choi et al. [13]; development/internal 276,341; external 63,384",
        "Hadaya et al. [14]; estimated 1,003,703 EGS admissions",
        "Hadaya et al. [14]; same population",
        "Bihorac et al. [3]; 51,457 inpatient surgical patients",
    ],
    "5.15": [
        "Mortality discrimination",
        "Respiratory discrimination",
        "Sensitivity, specificity, PPV, NPV, F1",
        "Accuracy",
        "Brier score",
        "Calibration",
        "Prevalence",
        "Explanation stability",
    ],
    "5.16": [
        "Postoperative meaning",
        "Explicit positives and negatives",
        "Assessability, contradictions and events",
        "Modeling decision",
        "Permitted report interpretation",
    ],
    "5.17": [
        "AUROC",
        "Average precision",
        "Brier score",
        "Offset intercept",
        "Joint intercept",
        "Joint slope",
    ],
    "5.18": [
        "Validation-selected threshold",
        "TP / FP / TN / FN",
        "Sensitivity",
        "Specificity",
        "Precision / PPV",
        "NPV",
        "Accuracy",
        "F1",
        "Predicted positives / 10,000",
    ],
    "5.19": [
        "AUROC",
        "Average precision",
        "Brier score",
        "Offset intercept",
        "Joint intercept",
        "Joint slope",
    ],
    "5.20": [
        "Validation-selected threshold",
        "TP / FP / TN / FN",
        "Sensitivity",
        "Specificity",
        "Precision / PPV",
        "NPV",
        "Accuracy",
        "F1",
        "Predicted positives / 10,000",
    ],
    "5.21": [
        "LR coefficients and odds",
        "Global and local SHAP",
        "Refits and pairs",
        "Clinical rank Spearman / top-five Jaccard",
        "Clinical SHAP variability",
        "Cross-model agreement",
        "Implication",
    ],
    "5.22": [
        "Age",
        "ASA",
        "Creatinine and BUN",
        "Hemoglobin and platelets",
        "Sodium, potassium and glucose",
        "Missingness indicators",
        "Albumin and prothrombin time",
        "Procedure and comorbidities",
    ],
    "5.23": ["Mild perturbation", "Moderate perturbation"],
    "B.1": [
        "Age semantics and ASA coding",
        "Anesthesia boundary and static provenance",
        "Mortality hospitalization linkage",
        "Laboratory names, specimens and units",
        "Result availability protocol",
        "Respiratory semantics and assessability",
        "Independent events and sample adequacy",
        "Ethics and DUA requirements",
        "Final source and configuration hashes",
        "Final input checksums and environment",
    ],
    "C.1": ["A Project evidence", "B Published benchmarks", "C Illustrative values"],
}
DISPLAY_ROWS = {
    "5.17": (
        "0.8796|0.8796|0.9023|0.9023\n0.1092|0.1092|0.1384|0.1384\n"
        "0.0095|0.0094|0.0094|0.0092\n-0.4054|0.0296|0.1617|0.0150\n"
        "-0.1490|0.4485|-0.4823|0.2995\n1.0815|1.1160|0.8056|1.0830"
    ),
    "5.18": (
        "0.006810|0.011601\n89 / 3188 / 6712 / 11|80 / 1842 / 8058 / 20\n"
        "0.8900|0.8000\n0.6780|0.8139\n0.0272|0.0416\n0.9984|0.9975\n"
        "0.6801|0.8138\n0.0527|0.0791\n3277|1922"
    ),
    "5.19": (
        "0.8513|0.8513|0.8773|0.8773\n0.4049|0.4049|0.4706|0.4706\n"
        "0.0593|0.0588|0.0562|0.0551\n-0.2778|-0.0084|-0.1765|-0.0048\n"
        "-0.1933|-0.1004|-0.4523|-0.0339\n1.0548|0.9481|0.8074|0.9827"
    ),
    "5.20": (
        "0.072946|0.080390\n619 / 2267 / 6933 / 181|628 / 1890 / 7310 / 172\n"
        "0.7738|0.7850\n0.7536|0.7946\n0.2145|0.2494\n0.9746|0.9770\n"
        "0.7552|0.7938\n0.3359|0.3785\n2886|2518"
    ),
    "5.23": "10 / 45|0.9830|1.0000|0.0140\n10 / 45|0.8139|0.7630|0.0395",
}
TABLE_FILES = {
    "5.17": "tables/table_5_17_mortality_metrics.csv",
    "5.18": "tables/table_5_18_mortality_operating_point.csv",
    "5.19": "tables/table_5_19_respiratory_metrics.csv",
    "5.20": "tables/table_5_20_respiratory_operating_point.csv",
    "5.23": "tables/table_5_23_rank_perturbation.csv",
}
# Report number, exact caption suffix, output filename suffix, ZIP member, original PNG hash.
FIGURES = [
    (
        "5.7",
        "mortality ROC and precision recall",
        "mortality_roc_pr",
        8,
        "94c69a3667bbf8b26515cfff0535577ff0329aa6803c24455b2c997b9b4cc415",
    ),
    (
        "5.8",
        "mortality calibration",
        "mortality_calibration",
        9,
        "d29a8bd5cd4f28e17c10306aa3d65d8fefef9d331bad4fee56ac28dbfc04f38d",
    ),
    (
        "5.9",
        "mortality confusion matrices",
        "mortality_confusion",
        10,
        "010f7728d256ef6ee59c53584063c7736667c8e44324a2d8ce29ee3d17dcd8cc",
    ),
    (
        "5.10",
        "two outcome metric comparison",
        "endpoint_comparison",
        11,
        "1af8dff499535a338ef6afd9b6cdcbd5837ebbd432cdd51a940e9725fd58ec99",
    ),
    (
        "5.11",
        "respiratory ROC and precision recall",
        "respiratory_roc_pr",
        12,
        "f4d1dc0c1b4d2fc1439c6aea15c71710301361f9d00c7e2bce2354315e946b16",
    ),
    (
        "5.12",
        "respiratory calibration",
        "respiratory_calibration",
        13,
        "c8afd82e6c053514781513376d652c363156a37634545d5c5e437194b7761339",
    ),
    (
        "5.13",
        "respiratory confusion matrices",
        "respiratory_confusion",
        14,
        "de58620d1ec516cc919e9257c575c71b456643e28e38908d4e2c97a285b49ac1",
    ),
    (
        "5.14",
        "rank sensitivity exercise",
        "rank_sensitivity",
        15,
        "39aaab754063430b42dffe06596b1f72458e636a8c6df818afdcb6a912e8cfa1",
    ),
]
APPENDIX_HEADINGS = [
    "C.1 Result provenance summary",
    "C.2 Prediction scenario construction",
    "C.3 Consistency calculations",
    "C.4 Rank sensitivity construction",
    "C.5 Clinical configuration and measurements",
    "C.6 Final reporting boundary",
]
QUALIFICATION = (
    f"Attributed to public revision {REPORT_REVISION}, inspected {INSPECTION_DATE}. "
    f"Historical audit, synthetic campaign and tests are dated {HISTORICAL_DATE}, not rerun here. "
    "Public-checkout artifact unavailability is historical, "
    "not a claim about current local campaigns. No clinical score or approval is established."
)


class ReferenceManifest(TypedDict):
    schema_version: int
    evidence_kind: str
    source: dict[str, str | int]
    import_timestamp: str
    original_inspected_revision: str
    report_source_revision: str
    source_inspection_date: str
    historical_verification_date: str
    historical_qualification: str
    importer_sha256: str
    importer_source_sha256: dict[str, str]
    underlying_arrays_available: bool
    tables: list[dict[str, Json]]
    figures: list[dict[str, str | bool]]
    sections: list[dict[str, Json]]
    evidence_categories: dict[str, str]
    files: list[dict[str, Json]]


ILLUSTRATION_FIELDS = [
    "report_table",
    "evidence_category",
    "endpoint",
    "model",
    "variant",
    "condition",
    "quantity",
    "value",
    "display_value",
    "vectors",
    "unique_pairs",
    "source_quantity",
    "source_column",
    "source_display_value",
    "underlying_arrays_available",
]
CONTEXT_FIELDS = [
    "report_table",
    "evidence_category",
    "record_type",
    "row_label",
    "field",
    "value",
    "display_value",
    "status",
    "unavailable_reason",
    "historical_date",
    "source_inspection_date",
    "source_revision",
    "qualification",
]


REFERENCE_README = (
    "# Exact report illustration reference\n\n"
    "These score streams are artificial, not fitted project models. They cannot be used "
    "for inference or clinical conclusions. No models are trained, evaluated or loaded.\n\n"
    "Evidence A is attributed project/source evidence; B is published benchmark context; "
    "C is artificial report illustration. Historical audit, synthetic campaign and 28-test "
    f"assertions are dated {HISTORICAL_DATE}, not new verification. Public source revision "
    f"{REPORT_REVISION} was inspected on {INSPECTION_DATE}. The audit's local inspected "
    f"revision is {INSPECTED_REVISION}. Public-checkout unavailability is historical, "
    "not a claim about current ignored local campaigns.\n\n"
    "The five illustrative CSVs preserve all 104 display values. Numeric value is separate "
    "from display_value; source_display_value retains composite Word cells. The two "
    "Vectors / pairs cells use numeric vectors and unique_pairs columns; scalar value is "
    "empty. Source labels remain in source_quantity/source_column. Trailing zeros survive. "
    "Table 5.15 and surrounding benchmark qualifications are stored with Table 5.14. "
    "mAP/AUPRC are not relabeled project AP; probability-plot slopes are not logit slopes. "
    "Missing benchmark values remain text, never zero.\n\n"
    "evidence_status.csv retains Tables 5.12-5.13, 5.16, 5.21-5.22, Appendix B and C.1/C.5: "
    "original cells, source context, historical dates, qualifications and unavailable reasons. "
    "These are source claims, not an assessment of present clinical approval.\n\n"
    "construction.json retains Appendix C constants, all Appendix C prose, its provenance "
    "table and the referenced clinical search-space table. RNG implementation, precise "
    "draw/shuffle order, correlated-noise construction, illustration optimizer settings and "
    "original arrays/code are unavailable, not defaults. Seeds do not promise bitwise score "
    "regeneration. Rank weights are not SHAP; SD bars are not confidence intervals.\n\n"
    "The DOCX and eight original PNG byte streams are copied without re-encoding. "
    "reference_manifest.json records portable relative paths, hashes of every other file, "
    "table/figure captions and ZIP members. It is written last and does not hash itself. "
    "Arrays are unavailable. Keep this archive outside clinical study roots.\n"
).encode()
