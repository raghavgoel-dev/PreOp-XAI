"""One reproducible patient assignment, stratified on known mortality."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .audit import _get_column
from .cohort import require_columns, validate_identity


def assign_splits(labels: pd.DataFrame, seed: int = 2026) -> pd.DataFrame:
    validate_identity(labels)
    require_columns(labels, ["mortality", "respiratory"])
    for endpoint in ("mortality", "respiratory"):
        if not _get_column(labels, endpoint).dropna().isin([0, 1]).to_numpy().all():
            raise ValueError(f"{endpoint} must contain only 0, 1 or missing")
    result = (
        labels.copy()
        .sort_values(["patient_id", "operation_id"], kind="stable")
        .reset_index(drop=True)
    )
    known = result.index[result["mortality"].notna()]
    counts = result.loc[known, "mortality"].value_counts()
    message = (
        "Insufficient mortality events/non-events for a stratified 70/15/15 "
        "split with both classes in every partition. Review sample adequacy "
        "and prespecify a revised design; do not search seeds."
    )
    if len(counts) != 2 or counts.min() < 3:
        raise ValueError(message)
    try:
        train, held = train_test_split(
            known,
            test_size=0.30,
            random_state=seed,
            stratify=result.loc[known, "mortality"].astype(int),
        )
        validation, test = train_test_split(
            held,
            test_size=0.5,
            random_state=seed,
            stratify=result.loc[held, "mortality"].astype(int),
        )
    except ValueError as error:
        raise ValueError(message) from error
    result["partition"] = pd.Series(index=result.index, dtype="string")
    for partition, indices in (("train", train), ("validation", validation), ("test", test)):
        if result.loc[indices, "mortality"].nunique() != 2:
            raise ValueError(message)
        result.loc[indices, "partition"] = partition

    # Unknown primary labels are assigned exactly once, independently of the
    # respiratory label. Largest-remainder allocation also handles tiny groups.
    unknown = result.index[result["mortality"].isna()].to_numpy(copy=True)
    rng = np.random.default_rng(seed)
    rng.shuffle(unknown)
    sizes = np.array([0.70, 0.15, 0.15]) * len(unknown)
    allocation = np.floor(sizes).astype(int)
    remainder = len(unknown) - allocation.sum()
    order = np.argsort(-(sizes - allocation), kind="stable")
    allocation[order[:remainder]] += 1
    offset = 0
    for partition, size in zip(("train", "validation", "test"), allocation, strict=True):
        result.loc[unknown[offset : offset + size], "partition"] = partition
        offset += size
    if _get_column(result, "partition").isna().to_numpy().any():
        raise RuntimeError("Internal error: unassigned patients")
    return result
