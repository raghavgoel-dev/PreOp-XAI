"""Independent serialized-export QA; no fitting, prediction or evaluation calls.

Run: uv run --locked python tests/result_verification.py --source SOURCE
     --output EXPORT --receipt NEW_JSON
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import numpy as np
import typer
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from preop_xai.result_io import load_json, save_json, sha256
from preop_xai.result_manifest import read_manifest, validate_manifest


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify(source: Path, output: Path) -> dict[str, int | str]:
    manifest = read_manifest(output / "report_artifacts.json")
    validate_manifest(output, manifest)
    repository = Path(__file__).resolve().parents[1]
    code_hashes = manifest["exporter"]["source_sha256"]
    assert isinstance(code_hashes, dict)
    for relative, expected in code_hashes.items():
        assert sha256(repository / relative) == expected
    for relative, expected in manifest["source_hashes"].items():
        endpoint, _, filename = relative.partition("/")
        if filename.startswith("restricted-") and filename.endswith("-stability"):
            model = filename.removeprefix("restricted-").removesuffix("-stability")
            assert model in {"lr", "xgboost"}
            path = source / endpoint / "private" / f"{model}_stability.npz"
        else:
            path = source / relative
        assert sha256(path) == expected
    assert (
        manifest["source_campaign"]["revision"]
        == load_json(source / "manifest.json")["code_commit"]
    )
    checked_series = 0
    checked_bins = 0
    for endpoint in manifest["endpoints"]:
        directory = output / endpoint
        with np.load(source / endpoint / "predictions.npz", allow_pickle=False) as archive:
            y = archive["y"]
            scores = dict(zip(archive["names"].tolist(), archive["probabilities"], strict=True))
        rows = _rows(directory / "discrimination_calibration.csv")
        for row in rows:
            p = scores[f"{row['model']}_{row['variant']}"]
            assert int(row["n"]) == len(y)
            assert int(row["events"]) == y.sum()
            expected = {
                "brier": brier_score_loss(y, p),
                "test_prevalence_brier_reference": y.mean() * (1 - y.mean()),
            }
            if len(np.unique(y)) == 2:
                expected.update(
                    auroc=roc_auc_score(y, p), average_precision=average_precision_score(y, p)
                )
            for key, value in expected.items():
                np.testing.assert_allclose(float(row[key]), value, rtol=1e-12, atol=1e-12)
            for filename in ("calibration_bins_fixed.csv", "calibration_bins_quantile.csv"):
                bins = [
                    r
                    for r in _rows(directory / filename)
                    if (r["model"], r["variant"]) == (row["model"], row["variant"])
                ]
                assert sum(int(r["n"]) for r in bins) == len(y)
                assert sum(int(r["events"]) for r in bins) == y.sum()
                if filename.endswith("fixed.csv"):
                    assert len(bins) == 5
                checked_bins += len(bins)
            for filename, x, z, metric in (
                ("roc_points.csv", "fpr", "tpr", "auroc"),
                ("pr_points.csv", "recall", "precision", "average_precision"),
            ):
                points = [
                    r
                    for r in _rows(directory / filename)
                    if (r["model"], r["variant"]) == (row["model"], row["variant"])
                ]
                if not points:
                    assert len(np.unique(y)) == 1
                    continue
                xs = np.array([float(r[x]) for r in points])
                ys = np.array([float(r[z]) for r in points])
                area = np.trapezoid(ys, xs) if metric == "auroc" else -np.sum(np.diff(xs) * ys[:-1])
                np.testing.assert_allclose(area, float(row[metric]), rtol=1e-12, atol=1e-12)
                sentinel = points[0] if metric == "auroc" else points[-1]
                assert sentinel["threshold"] == ""
                assert sentinel["threshold_kind"] == (
                    "positive_infinity" if metric == "auroc" else "none"
                )
            checked_series += 1
        for row in _rows(directory / "operating_point.csv"):
            p = scores[f"{row['model']}_calibrated"]
            predicted = p >= float(row["threshold"])
            tp, fp = np.sum((y == 1) & predicted), np.sum((y == 0) & predicted)
            tn, fn = np.sum((y == 0) & ~predicted), np.sum((y == 1) & ~predicted)
            assert [int(row[key]) for key in ("tp", "fp", "tn", "fn")] == [tp, fp, tn, fn]
            np.testing.assert_allclose(float(row["accuracy"]), (tp + tn) / len(y))
            np.testing.assert_allclose(
                float(row["predicted_positives_per_10000"]), 10000 * (tp + fp) / len(y)
            )
        importance = _rows(directory / "stability_importance.csv")
        for model in {row["model"] for row in importance}:
            array_path = source / endpoint / "private" / f"{model}_stability.npz"
            if not array_path.is_file():
                continue
            with np.load(array_path, allow_pickle=False) as archive:
                global_importance = np.abs(archive["grouped_contributions"]).mean(axis=1)
            model_rows = [r for r in importance if r["model"] == model]
            np.testing.assert_allclose(
                [float(r["sample_sd"]) for r in model_rows], global_importance.std(axis=0, ddof=1)
            )
    for path in output.rglob("*"):
        assert path.name.casefold() != "private"
        assert path.suffix not in {".npz", ".joblib", ".parquet"}
        if path.suffix in {".csv", ".json", ".md"}:
            assert "PRIVATE_SENTINEL_PATIENT" not in path.read_text(encoding="utf-8")
    report = (output / "report.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", report)
    assert all((output / unquote(link)).is_file() for link in links)
    assert sha256(source / "status.json") == manifest["source_hashes"]["status.json"]
    return {
        "status": "PASS",
        "checked_series": checked_series,
        "checked_bins": checked_bins,
        "checked_manifest_files": len(manifest["artifacts"]),
        "resolved_report_links": len(links),
        "privacy": "no private files, row arrays or fixture identifier values in aggregates",
        "verified_source_hashes": len(manifest["source_hashes"]),
    }


def main(
    source: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    receipt: Annotated[Path, typer.Option()],
) -> None:
    if receipt.exists():
        raise ValueError("QA receipt already exists.")
    result = verify(source, output)
    save_json(receipt, result)
    typer.echo(json.dumps(result))


if __name__ == "__main__":
    typer.run(main)
