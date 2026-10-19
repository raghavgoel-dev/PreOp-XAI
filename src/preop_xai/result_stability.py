"""Read-only aggregate exports of saved paired-refit explanation stability."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .preprocessing import FEATURES
from .result_io import ArtifactTables, Json, Row, load_json, sha256
from .result_stability_plots import plot_stability as plot_stability
from .result_stability_validation import integer, number, paired_rows, saved_sd, sealed_hash

STABILITY_FIELDS = {
    "stability_summary.csv": (
        "endpoint model requested_refits successful_paired_refits status pair_count "
        "spearman_defined_pairs spearman_undefined_pairs spearman_mean top5_jaccard_mean "
        "baseline_shift_rms validation_n background_n scale sample_sd_status"
    ).split(),
    "stability_pairs.csv": (
        "endpoint model pair_id first_draw_id second_draw_id spearman top5_jaccard"
    ).split(),
    "stability_importance.csv": (
        "endpoint model concept mean_absolute_importance sample_sd sample_sd_status "
        "sample_sd_ddof top5_inclusion_frequency centered_contribution_rms_mean_over_patients"
    ).split(),
}


def stability_tables(directory: Path, endpoint: str) -> ArtifactTables:
    """Return aggregate tables without modifying a source or fitting any model.

    Write rows with ``write_table(path, rows, STABILITY_FIELDS[name])`` to retain
    headers for unavailable tables. Missing unsealed arrays retain JSON means;
    missing or changed sealed arrays fail rather than becoming optional evidence.
    """
    directory = Path(directory)
    tables: dict[str, list[Row]] = {name: [] for name in STABILITY_FIELDS}
    unavailable: list[Row] = []
    sources: dict[str, Json] = {}
    metadata: dict[str, Json] = {
        "sample_sd_ddof": 1,
        "importance_definition": "mean_over_validation_patients(abs(grouped_contributions))",
        "sample_sd_definition": "across-refit sample SD; not a confidence interval",
        "patient_variability_definition": (
            "patient-centered contribution RMS averaged over patients"
        ),
        "scale": None,
        "sources": sources,
    }
    path = directory / "stability.json"
    if not path.is_file():
        unavailable.append(
            {"endpoint": endpoint, "artifact": "stability", "reason": "stability.json missing"}
        )
        return {"tables": tables, "metadata": metadata, "unavailable": unavailable}
    data = load_json(path)
    requested = integer(data["requested_refits"], "requested refits", 2)
    n = integer(data["validation_n"], "validation n", 1)
    background_n = integer(data["background_n"], "background n", 1)
    ids = data["successful_paired_draws"]
    if not isinstance(ids, list):
        raise ValueError("Invalid successful paired draw IDs.")
    for draw in ids:
        integer(draw, "successful paired draw ID")
    if len(set(ids)) != len(ids) or any(draw >= requested for draw in ids):
        raise ValueError(
            "Invalid successful paired draw IDs: duplicate or outside requested range."
        )
    if data["paired_draws"] is not True:
        raise ValueError("Stability evidence must use paired draws.")
    if not isinstance(data["scale"], str) or not data["scale"]:
        raise ValueError("Missing stability explanation scale.")
    metadata["scale"] = data["scale"]
    sources["stability.json"] = sha256(path)
    k = len(ids)
    if not isinstance(data["models"], dict) or not data["models"]:
        raise ValueError("Missing stability models.")
    for model, source in data["models"].items():
        if not model or any(char in model for char in "/\\:") or model in {".", ".."}:
            raise ValueError("Invalid stability model name.")
        if integer(source["successful_refits"], "successful refits") != k:
            raise ValueError(f"Successful refit count disagrees for {model}.")
        status = source["status"]
        expected_status = (
            "insufficient_successful_paired_refits"
            if k < 2
            else ("complete" if k == requested else "partial")
        )
        if status != expected_status:
            raise ValueError(f"Stability status disagrees with successful refit count for {model}.")
        pairs, rank_mean, jaccard_mean, defined = paired_rows(source, ids, endpoint, model)
        tables["stability_pairs.csv"].extend(pairs)
        baseline_rms = None
        if k >= 2:
            baseline_rms = number(source["baseline_shift_rms"], "baseline shift RMS")
            for key in (
                "mean_absolute_importance",
                "top5_inclusion_frequency",
                "centered_contribution_rms_mean_over_patients",
            ):
                if set(source[key]) != set(FEATURES):
                    raise ValueError(f"Invalid stability concept schema for {key}.")
                for feature, value in source[key].items():
                    number(
                        value,
                        f"{key}/{feature}",
                        upper=1 if key == "top5_inclusion_frequency" else np.inf,
                    )
        arrays_path = directory / "private" / f"{model}_stability.npz"
        sealed = sealed_hash(directory, arrays_path)
        sd = None
        if not arrays_path.is_file():
            if sealed is not None:
                raise ValueError(f"Required sealed stability array is missing: {arrays_path.name}.")
            reason = (
                "fewer than two successful paired refits"
                if k < 2
                else "unsealed private refit arrays missing"
            )
        else:
            if sealed is not None and sha256(arrays_path) != sealed:
                raise ValueError(f"Sealed stability array hash mismatch: {arrays_path.name}.")
            sd = saved_sd(arrays_path, source, ids, n)
            sources[f"restricted-{model}-stability"] = sha256(arrays_path)
            reason = "fewer than two successful paired refits" if k < 2 else None
        if reason:
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "model": model,
                    "artifact": "stability_importance_sample_sd",
                    "reason": reason,
                }
            )
        if k < 2 or defined < len(pairs):
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "model": model,
                    "artifact": "stability_spearman",
                    "reason": "fewer than two successful paired refits"
                    if k < 2
                    else "constant importance vectors yield undefined rank correlations",
                }
            )
        if k < 2:
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "model": model,
                    "artifact": "stability_top5_jaccard",
                    "reason": "fewer than two successful paired refits",
                }
            )
        tables["stability_summary.csv"].append(
            {
                "endpoint": endpoint,
                "model": model,
                "requested_refits": requested,
                "successful_paired_refits": k,
                "status": status,
                "pair_count": len(pairs),
                "spearman_defined_pairs": defined,
                "spearman_undefined_pairs": len(pairs) - defined,
                "spearman_mean": rank_mean,
                "top5_jaccard_mean": jaccard_mean,
                "baseline_shift_rms": baseline_rms,
                "validation_n": n,
                "background_n": background_n,
                "scale": data["scale"],
                "sample_sd_status": reason or "available",
            }
        )
        if k >= 2:
            for i, feature in enumerate(FEATURES):
                tables["stability_importance.csv"].append(
                    {
                        "endpoint": endpoint,
                        "model": model,
                        "concept": feature,
                        "mean_absolute_importance": source["mean_absolute_importance"][feature],
                        "sample_sd": float(sd[i]) if sd is not None else None,
                        "sample_sd_status": reason or "available",
                        "sample_sd_ddof": 1,
                        "top5_inclusion_frequency": source["top5_inclusion_frequency"][feature],
                        "centered_contribution_rms_mean_over_patients": source[
                            "centered_contribution_rms_mean_over_patients"
                        ][feature],
                    }
                )
    return {"tables": tables, "metadata": metadata, "unavailable": unavailable}
