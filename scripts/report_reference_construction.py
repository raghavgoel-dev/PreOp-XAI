"""Exact Appendix C construction metadata; no score generation or model imports."""

from xml.etree import ElementTree as ET

from scripts.report_reference_extract import section
from scripts.report_reference_inventory import APPENDIX_HEADINGS, QUALIFICATION, Json


def construction(
    blocks: list[ET.Element], tables: dict[str, list[list[str]]]
) -> tuple[dict[str, Json], dict[str, list[str]]]:
    appendix = {
        heading.split()[0]: section(
            blocks,
            heading,
            APPENDIX_HEADINGS[index + 1] if index + 1 < len(APPENDIX_HEADINGS) else None,
        )
        for index, heading in enumerate(APPENDIX_HEADINGS)
    }
    missing = {
        key: {"value": None, "reason": "Not specified or supplied in the source DOCX."}
        for key in (
            "rng_implementation",
            "precise_draw_order",
            "shuffle_order",
            "correlated_noise_construction",
            "optimizer_configuration",
            "original_generation_code",
            "original_full_precision_arrays",
            "score_arrays",
            "bin_membership",
            "rank_vectors",
        )
    }
    metadata: dict[str, Json] = {
        "schema_version": 1,
        "evidence_category": "C",
        "underlying_arrays_available": False,
        "source_appendix_c": appendix,
        "source_provenance_table_c_1": tables["C.1"],
        "prediction_scenarios": {
            "mortality": {
                "seed": 20261019,
                "validation_n": 10000,
                "evaluation_n": 10000,
                "events_per_sample": 100,
                "prevalence": 0.01,
                "d_lr": 1.60,
                "d_xgb": 1.75,
            },
            "respiratory": {
                "seed": 20261020,
                "validation_n": 10000,
                "evaluation_n": 10000,
                "events_per_sample": 800,
                "prevalence": 0.08,
                "d_lr": 1.50,
                "d_xgb": 1.65,
            },
            "independent_validation_and_evaluation": True,
            "paired_model_outcomes": True,
            "normal_noise_mean": 0,
            "normal_noise_sd": 1,
            "noise_correlation": 0.92,
            "score_formula": "s = d*y + z",
            "logit_formula": "l = logit(pi) + d*s - d*d/2",
            "raw_logit_lr": {"multiplier": 0.92, "offset": 0.15},
            "raw_logit_xgb": {"multiplier": 1.22, "offset": 0.55},
            "recalibration": {
                "partition": "validation",
                "formula": "sigmoid(a+b*raw_logit)",
                "objective": "mean binary log loss",
            },
            "threshold": {
                "partition": "validation",
                "minimum_sensitivity": 0.8,
                "rule": "highest calibrated threshold retaining at least 80% sensitivity",
                "evaluation_rule": "apply unchanged",
                "raw_rule": "inverse-transformed corresponding threshold",
            },
            "evaluation_diagnostics_refit_predictions": False,
            "calibration_bins": {"strategy": "equal-frequency", "count": 10, "nominal_n": 1000},
            "offset_diagnostic_fixed_slope": 1,
            "joint_diagnostic": "logistic loss against logit(p) on evaluation sample",
            "prevalence_only_brier": {"mortality": 0.0099, "respiratory": 0.0736},
            "all_negative_accuracy": {"mortality": 0.99, "respiratory": 0.92},
            "clinical_confidence_intervals_available": False,
        },
        "rank_sensitivity": {
            "seed": 20261021,
            "vectors_per_condition": 10,
            "unique_pairs_per_condition": 45,
            "feature_order": [
                "Age",
                "ASA",
                "Creatinine",
                "Hemoglobin",
                "BUN",
                "Glucose",
                "Sodium",
                "Platelets",
                "Potassium",
                "Sex",
            ],
            "base_weights": [0.23, 0.20, 0.15, 0.12, 0.10, 0.07, 0.05, 0.035, 0.025, 0.02],
            "normal_epsilon_sd": {"Mild": 0.12, "Moderate": 0.38},
            "perturbation": "weight * exp(epsilon)",
            "normalization": "each vector sums to one",
            "top_k": 5,
            "sd_ddof": 1,
            "rms_sd": "sqrt(mean(feature sample variances))",
            "error_bars": "sample standard deviations, not confidence intervals",
            "shap_values": False,
            "bootstrap_patient_refits": False,
        },
        "clinical_configuration_context": {
            "evidence_category": "A",
            "source_table_5_6": tables["5.6"],
            "seed": 2026,
            "lr_candidates": 3,
            "xgb_candidates": 12,
            "training_folds": 5,
            "evaluation_bootstrap_resamples": 1000,
            "stability_refits": 10,
            "source_python": "3.11.9",
            "selected_clinical_c": None,
            "selected_clinical_tree_configuration": None,
            "training_cv_ap": None,
            "clinical_event_counts": None,
            "runtime": None,
            "peak_memory": None,
            "clinical_execution_environment": None,
            "unavailable_reason": (
                "No approved clinical campaign artifacts or measurement manifest supplied."
            ),
            "qualification": QUALIFICATION,
        },
        "unavailable_details": missing,
        "reproduction_status": (
            "Exact byte archival only; constants do not establish bitwise regeneration."
        ),
    }
    return metadata, appendix
