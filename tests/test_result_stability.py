"""Deterministic saved-evidence contracts for aggregate stability exports."""

import csv
import json
from copy import deepcopy

import matplotlib
import numpy as np
import pytest

from preop_xai.preprocessing import FEATURES
from preop_xai.result_io import sha256, write_table
from preop_xai.result_stability import STABILITY_FIELDS, plot_stability, stability_tables
from preop_xai.stability import (
    InsufficientStability,
    StabilityResult,
    StabilitySummary,
    _summarize,
)

matplotlib.use("Agg")


def saved_fixture(directory, *, ids=(1, 4, 7), requested=8, constant=False, arrays=True):
    directory.mkdir(parents=True, exist_ok=True)
    private = directory / "private"
    private.mkdir(exist_ok=True)
    n = 4
    k = len(ids)
    base = np.arange(n * len(FEATURES), dtype=float).reshape(n, len(FEATURES)) / 11 - 1
    contributions = (
        np.stack([np.roll(base, i, axis=1) * (i + 1) for i in range(k)])
        if k
        else np.empty((0, n, len(FEATURES)))
    )
    if constant:
        contributions[:] = 0
    baselines = np.arange(k * n, dtype=float).reshape(k, n) / 10
    data: StabilityResult = {
        "seed": 42,
        "requested_refits": requested,
        "validation_n": n,
        "background_n": 6,
        "paired_draws": True,
        "scale": "raw model log-odds; calibrator uncertainty excluded",
        "background_convention": "fixed original training rows",
        "grouping": "clinical concepts including missingness",
        "limitations": [],
        "successful_paired_draws": list(ids),
        "models": {},
    }
    source: StabilitySummary | InsufficientStability
    if k < 2:
        source = {"status": "insufficient_successful_paired_refits", "successful_refits": k}
    else:
        source = _summarize(contributions, baselines)
        source["status"] = "complete" if k == requested else "partial"
        source["successful_refits"] = k
    data["models"]["lr"] = source
    (directory / "stability.json").write_text(json.dumps(data), encoding="utf-8")
    if arrays:
        np.savez_compressed(
            private / "lr_stability.npz",
            successful_draws=np.asarray(ids, dtype=int),
            grouped_contributions=contributions,
            baselines=baselines,
            centered_contributions=contributions - contributions.mean(axis=0, keepdims=True)
            if k
            else contributions,
            baseline_shifts=baselines - baselines.mean(axis=0, keepdims=True) if k else baselines,
        )
    return data, contributions, baselines


def test_original_draw_ids_sample_sd_and_source_immutability(tmp_path):
    data, contributions, _ = saved_fixture(tmp_path)
    source = data["models"]["lr"]
    assert "pairwise" in source
    before = {p.relative_to(tmp_path): sha256(p) for p in tmp_path.rglob("*") if p.is_file()}
    exported = stability_tables(tmp_path, "mortality")
    assert set(exported["tables"]) == set(STABILITY_FIELDS)
    (summary,) = exported["tables"]["stability_summary.csv"]
    assert summary["status"] == "partial"
    assert summary["successful_paired_refits"] == 3
    assert summary["pair_count"] == 3
    pairs = exported["tables"]["stability_pairs.csv"]
    assert [(p["first_draw_id"], p["second_draw_id"]) for p in pairs] == [(1, 4), (1, 7), (4, 7)]
    assert len({p["pair_id"] for p in pairs}) == 3
    per_refit = np.abs(contributions).mean(axis=1)
    importance = exported["tables"]["stability_importance.csv"]
    np.testing.assert_allclose(
        np.asarray([r["sample_sd"] for r in importance], dtype=float), per_refit.std(axis=0, ddof=1)
    )
    np.testing.assert_allclose(
        np.asarray([r["mean_absolute_importance"] for r in importance], dtype=float),
        per_refit.mean(axis=0),
    )
    assert not np.allclose(per_refit.std(axis=0, ddof=1), per_refit.std(axis=0, ddof=0))
    assert (
        importance[0]["centered_contribution_rms_mean_over_patients"]
        == source["centered_contribution_rms_mean_over_patients"][FEATURES[0]]
    )
    assert before == {
        p.relative_to(tmp_path): sha256(p) for p in tmp_path.rglob("*") if p.is_file()
    }
    assert exported["metadata"]["sample_sd_ddof"] == 1
    sources = exported["metadata"]["sources"]
    assert isinstance(sources, dict)
    assert sources["restricted-lr-stability"] == sha256(tmp_path / "private/lr_stability.npz")
    assert all("private/" not in key for key in sources)
    assert exported["unavailable"] == []
    private_keys = {
        "grouped_contributions",
        "baselines",
        "centered_contributions",
        "baseline_shifts",
        "successful_draws",
        "baseline_mean_by_successful_refit",
    }
    assert all(
        not private_keys.intersection(row) for rows in exported["tables"].values() for row in rows
    )


def test_complete_and_undefined_ranks_remain_null(tmp_path):
    saved_fixture(tmp_path, ids=(0, 1, 2), requested=3, constant=True)
    result = stability_tables(tmp_path, "respiratory")
    (summary,) = result["tables"]["stability_summary.csv"]
    assert summary["status"] == "complete"
    assert summary["spearman_mean"] is None
    assert summary["spearman_defined_pairs"] == 0
    assert summary["spearman_undefined_pairs"] == 3
    assert summary["top5_jaccard_mean"] == 1
    assert all(p["spearman"] is None for p in result["tables"]["stability_pairs.csv"])
    assert all(r["sample_sd"] == 0 for r in result["tables"]["stability_importance.csv"])
    assert any(r["artifact"] == "stability_spearman" for r in result["unavailable"])


@pytest.mark.parametrize("ids", [(), (4,)])
def test_insufficient_refits_are_not_zero_agreement(tmp_path, ids):
    saved_fixture(tmp_path, ids=ids, arrays=False)
    result = stability_tables(tmp_path, "mortality")
    (summary,) = result["tables"]["stability_summary.csv"]
    assert summary["status"] == "insufficient_successful_paired_refits"
    assert summary["successful_paired_refits"] == len(ids)
    assert summary["spearman_mean"] is None
    assert summary["top5_jaccard_mean"] is None
    assert summary["baseline_shift_rms"] is None
    assert result["tables"]["stability_importance.csv"] == []
    assert result["tables"]["stability_pairs.csv"] == []
    assert result["unavailable"]


def test_missing_unsealed_arrays_retain_importance_but_not_sd(tmp_path):
    saved_fixture(tmp_path, arrays=False)
    result = stability_tables(tmp_path, "mortality")
    assert result["tables"]["stability_summary.csv"][0]["pair_count"] == 3
    assert all(r["sample_sd"] is None for r in result["tables"]["stability_importance.csv"])
    assert any(r["artifact"] == "stability_importance_sample_sd" for r in result["unavailable"])


@pytest.mark.parametrize("changed", [False, True])
def test_missing_or_changed_sealed_arrays_fail(tmp_path, changed):
    saved_fixture(tmp_path, arrays=changed)
    array = tmp_path / "private/lr_stability.npz"
    (tmp_path / "freeze.json").write_text(
        json.dumps({"inputs": {str(array): "0" * 64}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="[Ss]ealed"):
        stability_tables(tmp_path, "mortality")


@pytest.mark.parametrize("field", ["draw_ids", "dimensions", "nonfinite", "centered", "baseline"])
def test_corrupt_saved_arrays_rejected(tmp_path, field):
    saved_fixture(tmp_path)
    path = tmp_path / "private/lr_stability.npz"
    with np.load(path) as saved:
        arrays = {key: saved[key].copy() for key in saved.files}
    if field == "draw_ids":
        arrays["successful_draws"] = np.array([1, 7, 4])
    elif field == "dimensions":
        arrays["grouped_contributions"] = arrays["grouped_contributions"][:, :-1]
    elif field == "nonfinite":
        arrays["grouped_contributions"][0, 0, 0] = np.nan
    elif field == "centered":
        arrays["centered_contributions"][0, 0, 0] += 1
    else:
        arrays["baselines"][0, 0] += 1
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError):
        stability_tables(tmp_path, "mortality")


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "mean", "counts", "importance", "ids", "status", "jaccard"]
)
def test_summary_disagreements_fail(tmp_path, mutation):
    data, _, _ = saved_fixture(tmp_path)
    data = deepcopy(data)
    source = data["models"]["lr"]
    assert "pairwise" in source
    if mutation == "duplicate":
        source["pairwise"][1] = deepcopy(source["pairwise"][0])
    elif mutation == "missing":
        source["pairwise"].pop()
    elif mutation == "mean":
        assert source["spearman_mean"] is not None
        source["spearman_mean"] += 0.1
    elif mutation == "counts":
        source["spearman_defined_pairs"] += 1
    elif mutation == "importance":
        source["mean_absolute_importance"][FEATURES[0]] += 0.1
    elif mutation == "ids":
        data["successful_paired_draws"] = [1, 1, 7]
    elif mutation == "status":
        source["status"] = "complete"
    else:
        source["pairwise"][0]["top5_jaccard"] = 1.1
    (tmp_path / "stability.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        stability_tables(tmp_path, "mortality")


def test_missing_stability_is_explicit(tmp_path):
    result = stability_tables(tmp_path, "mortality")
    assert all(rows == [] for rows in result["tables"].values())
    assert result["unavailable"]


@pytest.mark.parametrize(
    "kind", ["defined", "undefined", "insufficient", "missing_arrays", "absent"]
)
def test_actual_csv_only_figures(tmp_path, monkeypatch, kind):
    if kind != "absent":
        saved_fixture(
            tmp_path,
            ids=(4,) if kind == "insufficient" else (1, 4, 7),
            constant=kind == "undefined",
            arrays=kind != "missing_arrays",
        )
    result = stability_tables(tmp_path, "mortality")
    output = tmp_path / "aggregate"
    output.mkdir()
    for name, rows in result["tables"].items():
        write_table(output / name, rows, STABILITY_FIELDS[name])
        with (output / name).open(newline="", encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == STABILITY_FIELDS[name]

    def reject_private(*args, **kwargs):
        raise AssertionError("Plot must consume only aggregate CSVs")

    monkeypatch.setattr(np, "load", reject_private)
    paths = plot_stability(output, "mortality")
    assert paths == ["stability_importance.png", "stability_agreement.png"]
    import matplotlib.pyplot as plt

    for name in paths:
        image = plt.imread(output / name)
        assert image.shape[0] >= 500
        assert image.shape[1] >= 1000
        assert image.std() > 0.01
    assert {p.suffix for p in output.iterdir()} == {".csv", ".png"}
