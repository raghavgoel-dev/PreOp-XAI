"""Stability figures rendered exclusively from aggregate CSV exports."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def plot_stability(directory: Path, endpoint: str) -> list[str]:
    """Render descriptive sample SD and agreement, never patient-level inputs."""
    import matplotlib.pyplot as plt

    directory = Path(directory)
    rows: dict[str, list[dict[str, str]]] = {}
    for name in ("stability_summary.csv", "stability_importance.csv"):
        path = directory / name
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                rows[name] = list(csv.DictReader(handle))
        else:
            rows[name] = []
    summaries = {row["model"]: row for row in rows["stability_summary.csv"]}
    models = list(dict.fromkeys(["lr", "xgboost", *summaries]))
    paths = []
    for kind in ("importance", "agreement"):
        fig, axes = plt.subplots(1, len(models), figsize=(7 * len(models), 5), squeeze=False)
        for ax, model in zip(axes[0], models, strict=True):
            summary = summaries.get(model)
            importance = [row for row in rows["stability_importance.csv"] if row["model"] == model]
            title = f"{endpoint}: {model}"
            if summary:
                title += (
                    f"\n{summary['successful_paired_refits']}/{summary['requested_refits']}"
                    f" successful refits; {summary['pair_count']} pairs ({summary['status']})"
                )
            ax.set_title(title, fontsize=10)
            if not summary or (kind == "importance" and not importance):
                ax.text(
                    0.5,
                    0.5,
                    "Unavailable: "
                    + (summary["status"] if summary else "no saved stability evidence"),
                    ha="center",
                    va="center",
                    wrap=True,
                    transform=ax.transAxes,
                )
                ax.set_axis_off()
                continue
            if kind == "importance":
                means = [float(row["mean_absolute_importance"]) for row in importance]
                positions = np.arange(len(importance))
                ax.barh(positions, means, color="steelblue")
                defined = [i for i, row in enumerate(importance) if row["sample_sd"] != ""]
                if defined:
                    ax.errorbar(
                        [means[i] for i in defined],
                        positions[defined],
                        xerr=[float(importance[i]["sample_sd"]) for i in defined],
                        fmt="none",
                        color="black",
                        capsize=3,
                    )
                else:
                    ax.text(
                        0.02,
                        0.02,
                        "Sample SD unavailable: " + summary["sample_sd_status"],
                        transform=ax.transAxes,
                        fontsize=8,
                        wrap=True,
                    )
                ax.set_yticks(positions, [row["concept"] for row in importance])
                ax.invert_yaxis()
                ax.set_xlabel(
                    "Mean absolute grouped importance (raw log-odds)\n"
                    "error bars: sample SD (ddof=1), not CI"
                )
            else:
                for i, field in enumerate(("spearman_mean", "top5_jaccard_mean")):
                    value = summary[field]
                    if value == "":
                        ax.text(i, 0.05, "Unavailable", ha="center", fontsize=9)
                    else:
                        ax.bar(i, float(value), color="steelblue")
                        ax.annotate(
                            f"{float(value):.3f}",
                            (i, float(value)),
                            xytext=(0, 5),
                            textcoords="offset points",
                            ha="center",
                        )
                ax.set_xticks([0, 1], ["Spearman", "Top-five Jaccard"])
                ax.set_xlim(-0.6, 1.6)
                ax.set_ylim(-1.15, 1.2)
                ax.set_ylabel("Mean pairwise agreement (descriptive, not CI)")
                ax.text(
                    0.02,
                    0.02,
                    f"Spearman: {summary['spearman_defined_pairs']} defined; "
                    f"{summary['spearman_undefined_pairs']} undefined pairs",
                    transform=ax.transAxes,
                    fontsize=8,
                )
                ax.axhline(0, color="gray", linewidth=0.5)
        fig.tight_layout()
        name = f"stability_{kind}.png"
        fig.savefig(directory / name, dpi=160)
        plt.close(fig)
        paths.append(name)
    return paths
