"""File-only performance plots; every mark comes from an aggregate CSV."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _save(fig, path: Path) -> None:
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _series(rows, model: str, variant: str):
    return [row for row in rows if row["model"] == model and row["variant"] == variant]


def _status(value: str) -> str:
    return "INVALID diagnostic (nonpositive slope)" if value == "nonpositive-slope" else value


def plot_endpoint(directory: Path, endpoint: str) -> list[str]:
    performance = read_table(directory / "discrimination_calibration.csv")
    models = list(dict.fromkeys(row["model"] for row in performance))
    roc = read_table(directory / "roc_points.csv")
    pr = read_table(directory / "pr_points.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    axes[0].plot([0, 1], [0, 1], "--", color="gray", label="Chance")
    for model in models:
        candidates = [row for row in performance if row["model"] == model]
        metric = next((r for r in candidates if r["variant"] == "calibrated"), candidates[0])
        variant = metric["variant"]
        status = _status(metric["calibration_status"])
        label = (
            f"{model} raw only (calibration unavailable: {status})"
            if variant == "raw"
            else f"{model} calibrated ({status})"
        )
        for ax, points, x, y, score, name in (
            (axes[0], roc, "fpr", "tpr", "auroc", "AUROC"),
            (axes[1], pr, "recall", "precision", "average_precision", "AP"),
        ):
            selected = _series(points, model, variant)
            if selected:
                ax.plot(
                    [float(r[x]) for r in selected],
                    [float(r[y]) for r in selected],
                    label=f"{label}; {name}={float(metric[score]):.4f}",
                    drawstyle="steps-post" if name == "AP" else "default",
                )
            else:
                ax.text(0.03, 0.3 + models.index(model) * 0.15, f"{label}: ranking unavailable")
    prevalence = float(performance[0]["prevalence"])
    axes[1].axhline(
        prevalence, linestyle="--", color="gray", label=f"Evaluation prevalence={prevalence:.4f}"
    )
    for ax, xlabel, ylabel, title in (
        (axes[0], "False positive rate", "True positive rate", "ROC"),
        (axes[1], "Recall", "Precision", "PR (AP, not trapezoidal area)"),
    ):
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel=xlabel, ylabel=ylabel, title=title)
        ax.legend(loc="best", fontsize=7)
    fig.suptitle(f"{endpoint}: saved evaluation predictions; research only")
    _save(fig, directory / "roc_pr.png")

    bins = read_table(directory / "calibration_bins_quantile.csv")
    fig, axes = plt.subplots(1, max(2, len(models)), figsize=(13, 5), layout="constrained")
    for ax, model in zip(axes, models, strict=False):
        ax.plot([0, 1], [0, 1], "--", color="gray", label="Ideal")
        for variant in ("raw", "calibrated"):
            points = [r for r in _series(bins, model, variant) if int(r["n"]) > 0]
            if points:
                status = points[0]["calibration_status"]
                label = (
                    f"raw (recalibrator: {status})"
                    if variant == "raw"
                    else (f"calibrated ({_status(status)})")
                )
                ax.plot(
                    [float(r["mean_predicted"]) for r in points],
                    [float(r["observed_fraction"]) for r in points],
                    "o-",
                    label=f"{label}; bins={len(points)}",
                )
        if not _series(bins, model, "calibrated"):
            status = next(r["calibration_status"] for r in performance if r["model"] == model)
            ax.text(0.03, 0.94, f"Calibrated unavailable: {status}", fontsize=8)
        ax.set(
            xlim=(0, 1),
            ylim=(0, 1),
            xlabel="Mean predicted probability",
            ylabel="Observed event fraction",
            title=f"{endpoint}: {model}",
        )
        ax.legend(fontsize=8)
    for ax in axes[len(models) :]:
        ax.text(0.1, 0.5, "Model unavailable")
        ax.set_axis_off()
    fig.suptitle("Descriptive quantile calibration; 10 requested bins, ties kept together")
    _save(fig, directory / "calibration_quantile.png")

    operating = read_table(directory / "operating_point.csv")
    fig, axes = plt.subplots(1, max(2, len(models)), figsize=(13, 5), layout="constrained")
    for ax, model in zip(axes, models, strict=False):
        row = next((r for r in operating if r["model"] == model), None)
        if row is None:
            status = next(r["calibration_status"] for r in performance if r["model"] == model)
            ax.text(0.05, 0.5, f"{model}: calibrated operating point\nunavailable ({status})")
            ax.set_axis_off()
            continue
        matrix = np.array([[int(row["tn"]), int(row["fp"])], [int(row["fn"]), int(row["tp"])]])
        positive = matrix[matrix > 0]
        if positive.size:
            image = ax.imshow(
                np.ma.masked_less_equal(matrix, 0),
                cmap="Blues",
                norm=LogNorm(
                    vmin=max(1, int(positive.min())),
                    vmax=max(int(positive.max()), int(positive.min()) + 1),
                ),
            )
            fig.colorbar(image, ax=ax, label="Positive-cell count (log shading)", shrink=0.65)
        for true in range(2):
            for predicted in range(2):
                ax.text(
                    predicted,
                    true,
                    str(matrix[true, predicted]),
                    ha="center",
                    va="center",
                    color="black",
                    bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
                )
        ax.set(
            xticks=[0, 1],
            yticks=[0, 1],
            xticklabels=["0: no event", "1: event"],
            yticklabels=["0: no event", "1: event"],
            xlabel="Predicted class",
            ylabel="True class",
            title=f"{model}: n={row['n']}; threshold={float(row['threshold']):.6g}\n"
            f"{_status(row['calibration_status'])}; research only",
        )
    for ax in axes[len(models) :]:
        ax.text(0.1, 0.5, "Model unavailable")
        ax.set_axis_off()
    fig.suptitle(f"{endpoint}: frozen validation threshold; p >= threshold")
    _save(fig, directory / "confusion_matrices.png")
    return ["roc_pr.png", "calibration_quantile.png", "confusion_matrices.png"]


def plot_comparison(output: Path, unavailable: list[str]) -> None:
    rows = read_table(output / "endpoint_comparison.csv")
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), layout="constrained")
    labels = [
        f"{r['endpoint']}\n{r['model']} {r['variant']}\n"
        + (
            "INVALID recalibration"
            if r["calibration_status"] == "nonpositive-slope"
            else r["calibration_status"]
        )
        for r in rows
    ]
    for ax, metric, title in (
        (axes[0], "auroc", "AUROC"),
        (axes[1], "average_precision", "AP (prevalence-dependent)"),
        (axes[2], "brier", "Brier (lower is better)"),
    ):
        for i, row in enumerate(rows):
            if row[metric]:
                value = float(row[metric])
                ax.bar(i, value)
                ax.text(i, value, f"{value:.4f}", ha="center", va="bottom", fontsize=8)
        ax.set(title=title, xticks=range(len(labels)), xticklabels=labels, ylim=(0, 1.08))
        ax.tick_params(axis="x", labelrotation=65, labelsize=7)
    context = "; ".join(
        f"{r['endpoint']}: prevalence={float(r['prevalence']):.4f}, "
        f"test-reference Brier={float(r['test_prevalence_brier_reference']):.4f}"
        for r in rows
        if r["model"] == rows[0]["model"] and r["variant"] == "raw"
    )
    fig.suptitle("Same-campaign descriptive comparison; no cross-endpoint significance claim")
    fig.supxlabel(
        context + ("\nUnavailable: " + "; ".join(unavailable) if unavailable else ""), fontsize=8
    )
    _save(fig, output / "endpoint_comparison.png")
