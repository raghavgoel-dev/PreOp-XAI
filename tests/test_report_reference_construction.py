"""Machine-readable construction metadata preserves the report constants."""

import json
from pathlib import Path

from tests.report_reference_fixture import DocxFixture, reference
from tests.report_reference_fixture import docx as docx


def test_construction_constants_and_unavailable_details(docx: DocxFixture, tmp_path: Path) -> None:
    source, _, _, _ = docx
    output = tmp_path / "reference"
    reference.import_reference(source, output)
    data = json.loads((output / "construction.json").read_text())
    scenarios = data["prediction_scenarios"]
    assert scenarios["mortality"] == {
        "seed": 20261019,
        "validation_n": 10000,
        "evaluation_n": 10000,
        "events_per_sample": 100,
        "prevalence": 0.01,
        "d_lr": 1.6,
        "d_xgb": 1.75,
    }
    assert scenarios["respiratory"]["seed"] == 20261020
    assert scenarios["respiratory"]["events_per_sample"] == 800
    assert scenarios["noise_correlation"] == 0.92
    assert scenarios["raw_logit_lr"] == {"multiplier": 0.92, "offset": 0.15}
    assert scenarios["raw_logit_xgb"] == {"multiplier": 1.22, "offset": 0.55}
    assert scenarios["threshold"]["minimum_sensitivity"] == 0.8
    assert scenarios["calibration_bins"] == {
        "strategy": "equal-frequency",
        "count": 10,
        "nominal_n": 1000,
    }
    rank = data["rank_sensitivity"]
    assert rank["seed"] == 20261021
    assert rank["base_weights"] == [0.23, 0.20, 0.15, 0.12, 0.10, 0.07, 0.05, 0.035, 0.025, 0.02]
    assert rank["normal_epsilon_sd"] == {"Mild": 0.12, "Moderate": 0.38}
    assert rank["vectors_per_condition"] == 10 and rank["unique_pairs_per_condition"] == 45
    assert rank["top_k"] == 5 and rank["sd_ddof"] == 1
    assert rank["shap_values"] is False and rank["bootstrap_patient_refits"] is False
    assert set(data["source_appendix_c"]) == {"C.1", "C.2", "C.3", "C.4", "C.5", "C.6"}
    assert set(data["unavailable_details"]) >= {
        "rng_implementation",
        "precise_draw_order",
        "shuffle_order",
        "correlated_noise_construction",
        "optimizer_configuration",
        "original_full_precision_arrays",
    }
    assert all(
        value["value"] is None and value["reason"] for value in data["unavailable_details"].values()
    )
    clinical = data["clinical_configuration_context"]
    assert [
        clinical[key]
        for key in (
            "seed",
            "lr_candidates",
            "xgb_candidates",
            "training_folds",
            "evaluation_bootstrap_resamples",
            "stability_refits",
        )
    ] == [2026, 3, 12, 5, 1000, 10]
    assert clinical["source_python"] == "3.11.9"
    assert all(
        clinical[key] is None
        for key in (
            "selected_clinical_c",
            "selected_clinical_tree_configuration",
            "training_cv_ap",
            "clinical_event_counts",
            "runtime",
            "peak_memory",
            "clinical_execution_environment",
        )
    )
