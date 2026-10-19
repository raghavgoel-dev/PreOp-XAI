"""Validation of saved paired-refit evidence; no fitting or explanation calls."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .preprocessing import FEATURES
from .result_io import Row, load_json

if TYPE_CHECKING:
    from .stability import InsufficientStability, StabilitySummary


def integer(value, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"Invalid {name}: expected integer >= {minimum}.")
    return value


def number(value, name: str, lower: float = 0, upper: float = np.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid {name}: expected a finite number.")
    value = float(value)
    if not np.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"Invalid {name}: expected finite value in [{lower}, {upper}].")
    return value


def agree(actual, expected, name: str) -> None:
    if actual is None or expected is None:
        if actual is not None or expected is not None:
            raise ValueError(f"Stability source disagreement: {name}.")
    elif not np.allclose(actual, expected, rtol=1e-7, atol=1e-10):
        raise ValueError(f"Stability source disagreement: {name}.")


def sealed_hash(directory: Path, path: Path) -> str | None:
    """Recognize both portable and historical absolute freeze input paths."""
    for seal in (directory / "freeze.json", directory.parent / "freeze.json"):
        if not seal.is_file():
            continue
        for source, digest in load_json(seal).get("inputs", {}).items():
            portable = source.replace("\\", "/")
            if (
                portable == path.resolve().as_posix()
                or portable == f"private/{path.name}"
                or portable.endswith(f"/{directory.name}/private/{path.name}")
            ):
                return digest
    return None


def paired_rows(
    source: StabilitySummary | InsufficientStability, ids: list[int], endpoint: str, model: str
) -> tuple[list[Row], float | None, float | None, int]:
    pairs = source["pairwise"] if "pairwise" in source else []
    expected_pairs = set(combinations(range(len(ids)), 2))
    found = set()
    ranks, jaccards = [], []
    rows: list[Row] = []
    for pair in pairs:
        first = integer(pair["first_successful_refit"], "pair position")
        second = integer(pair["second_successful_refit"], "pair position")
        positions = (first, second)
        if positions not in expected_pairs or positions in found:
            raise ValueError(f"Invalid or duplicate stability pair for {model}.")
        found.add(positions)
        rank = pair["spearman"]
        if rank is not None:
            rank = number(rank, "Spearman", -1, 1)
            ranks.append(rank)
        jaccard = number(pair["top5_jaccard"], "top-five Jaccard", 0, 1)
        jaccards.append(jaccard)
        rows.append(
            {
                "endpoint": endpoint,
                "model": model,
                "pair_id": f"{ids[first]}:{ids[second]}",
                "first_draw_id": ids[first],
                "second_draw_id": ids[second],
                "spearman": rank,
                "top5_jaccard": jaccard,
            }
        )
    if found != expected_pairs:
        raise ValueError(f"Expected {len(expected_pairs)} unique stability pairs for {model}.")
    rank_mean = float(np.mean(ranks)) if ranks else None
    jaccard_mean = float(np.mean(jaccards)) if jaccards else None
    if len(ids) >= 2:
        if "pairwise" not in source:
            raise ValueError(f"Missing stability pairs for {model}.")
        for key, expected, actual in (
            ("spearman_mean", rank_mean, source["spearman_mean"]),
            ("top5_jaccard_mean", jaccard_mean, source["top5_jaccard_mean"]),
        ):
            if actual is not None:
                number(actual, key, -1 if key == "spearman_mean" else 0, 1)
            agree(actual, expected, key)
        for key, expected, actual in (
            ("spearman_defined_pairs", len(ranks), source["spearman_defined_pairs"]),
            (
                "spearman_undefined_pairs",
                len(pairs) - len(ranks),
                source["spearman_undefined_pairs"],
            ),
        ):
            agree(integer(actual, key), expected, key)
    return rows, rank_mean, jaccard_mean, len(ranks)


def _rank_correlation(first: np.ndarray, second: np.ndarray) -> float | None:
    if np.ptp(first) == 0 or np.ptp(second) == 0:
        return None
    ranks = []
    for values in (first, second):
        _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
        starts = np.cumsum(counts) - counts
        ranks.append((starts + (counts - 1) / 2)[inverse])
    return float(np.corrcoef(ranks[0], ranks[1])[0, 1])


def saved_sd(path: Path, source: StabilitySummary, ids: list[int], n: int) -> np.ndarray:
    """Validate saved arrays against all aggregate evidence before deriving SD."""
    k = len(ids)
    with np.load(path, allow_pickle=False) as saved:
        draw_ids = saved["successful_draws"]
        if draw_ids.dtype.kind not in "iu" or not np.array_equal(draw_ids, ids):
            raise ValueError(f"Invalid successful draw IDs in {path.name}.")
        arrays = {}
        for key, shape in (
            ("grouped_contributions", (k, n, len(FEATURES))),
            ("baselines", (k, n)),
            ("centered_contributions", (k, n, len(FEATURES))),
            ("baseline_shifts", (k, n)),
        ):
            if key not in saved and key in {"centered_contributions", "baseline_shifts"}:
                continue
            value = saved[key]
            if (
                value.dtype.kind not in "fiu"
                or value.shape != shape
                or not np.isfinite(value).all()
            ):
                raise ValueError(f"Invalid {key} dimensions or finite values in {path.name}.")
            arrays[key] = value
    if k < 2:
        return np.full(len(FEATURES), np.nan)
    grouped, baselines = arrays["grouped_contributions"], arrays["baselines"]
    importance = np.abs(grouped).mean(axis=1)
    centered = grouped - grouped.mean(axis=0, keepdims=True)
    shifts = baselines - baselines.mean(axis=0, keepdims=True)
    for key, expected in (("centered_contributions", centered), ("baseline_shifts", shifts)):
        if key in arrays:
            agree(arrays[key], expected, key)
    top = np.argsort(-importance, axis=1, kind="stable")[:, : min(5, len(FEATURES))]
    frequencies = np.array([(top == i).any(axis=1).mean() for i in range(len(FEATURES))])
    for expected, actual, name in (
        (
            importance.mean(axis=0),
            [source["mean_absolute_importance"][feature] for feature in FEATURES],
            "mean_absolute_importance",
        ),
        (
            frequencies,
            [source["top5_inclusion_frequency"][feature] for feature in FEATURES],
            "top5_inclusion_frequency",
        ),
        (
            np.sqrt((centered**2).mean(axis=0)).mean(axis=0),
            [source["centered_contribution_rms_mean_over_patients"][f] for f in FEATURES],
            "centered_contribution_rms_mean_over_patients",
        ),
    ):
        agree(actual, expected, name)
    agree(source["baseline_mean_by_successful_refit"], baselines.mean(axis=1), "baseline means")
    agree(source["baseline_shift_rms"], np.sqrt((shifts**2).mean()), "baseline_shift_rms")
    for pair in source["pairwise"]:
        first, second = pair["first_successful_refit"], pair["second_successful_refit"]
        agree(
            pair["spearman"], _rank_correlation(importance[first], importance[second]), "Spearman"
        )
        a, b = set(top[first]), set(top[second])
        agree(pair["top5_jaccard"], len(a & b) / len(a | b), "top-five Jaccard")
    return importance.std(axis=0, ddof=1)
