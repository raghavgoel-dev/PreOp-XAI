"""Deterministic synthetic fixture generation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from preop_xai.contracts import DataKind

MINIMUM_SYNTHETIC_ROWS = 2


@dataclass(frozen=True, slots=True)
class SyntheticDataset:
    """Separated synthetic predictor and label tables."""

    operations: pl.DataFrame
    labs: pl.DataFrame
    labels: pl.DataFrame


def generate_synthetic(*, seed: int, rows: int) -> SyntheticDataset:
    """Generate a deterministic synthetic-only dataset."""
    if rows < MINIMUM_SYNTHETIC_ROWS:
        message = "Synthetic fixture requires at least two rows"
        raise ValueError(message)

    rng = np.random.default_rng(seed)
    patient_ids = [f"SYN-{seed:08x}-{index:06d}" for index in range(rows)]
    operation_ids = [f"SYN-OP-{seed:08x}-{index:06d}" for index in range(rows)]
    base = datetime(2025, 1, 1, 8, tzinfo=UTC)
    operation_starts = [base + timedelta(days=index) for index in range(rows)]
    ages = rng.integers(18, 91, size=rows)
    asa_classes = rng.integers(1, 6, size=rows)
    creatinine = rng.lognormal(mean=0.0, sigma=0.35, size=rows)
    available_at = [value - timedelta(hours=2) for value in operation_starts]
    mortality_score = -6.0 + (ages - 50) * 0.035 + (asa_classes - 1) * 0.55
    mortality_probability = 1.0 / (1.0 + np.exp(-mortality_score))
    mortality = rng.binomial(1, mortality_probability)

    operations = pl.DataFrame(
        {
            "patient_id": patient_ids,
            "operation_id": operation_ids,
            "operation_start": operation_starts,
            "age_years": ages,
            "asa_class": asa_classes,
            "data_kind": [DataKind.SYNTHETIC] * rows,
        }
    )
    labs = pl.DataFrame(
        {
            "operation_id": operation_ids,
            "logical_test": ["creatinine"] * rows,
            "value": creatinine,
            "available_at": available_at,
            "availability_verified": [True] * rows,
        }
    )
    labels = pl.DataFrame(
        {
            "operation_id": operation_ids,
            "in_hospital_mortality": mortality,
            "data_kind": [DataKind.SYNTHETIC] * rows,
        }
    )
    return SyntheticDataset(operations=operations, labs=labs, labels=labels)
