"""Fold-local preprocessing on the fixed clinical allowlist."""

from typing import Final

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

LABS: Final = ("hemoglobin", "platelets", "creatinine", "bun", "sodium", "potassium", "glucose")
FEATURES: Final = ("age", "sex", "asa", *LABS)
NUMERIC: Final = ("age", *LABS)


def get_column(frame: pd.DataFrame, name: str) -> pd.Series:
    """Narrow pandas' column-selection union at the model boundary."""
    column = frame[name]
    if not isinstance(column, pd.Series):
        raise ValueError(f"Expected a unique column: {name}")
    return column


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Reject accidental extra inputs at the explicit model boundary."""
    if not frame.columns.is_unique:
        raise ValueError("Feature names must be unique.")
    if set(frame.columns) != set(FEATURES):
        raise ValueError(f"Expected fixed clinical inputs {FEATURES}; got {tuple(frame.columns)}")
    result = frame.loc[:, list(FEATURES)].copy()
    result[list(NUMERIC)] = result[list(NUMERIC)].astype(float)
    if np.isinf(result[list(NUMERIC)].to_numpy()).any():
        raise ValueError("Numeric predictors cannot contain nonfinite infinity values.")
    if get_column(result, "age").isna().any():
        raise ValueError("Age cannot be missing.")
    for column in ("sex", "asa"):
        result[column] = get_column(result, column).fillna("unknown").astype(str)
    return result


def binary_outcomes(frame: pd.DataFrame, labels: pd.Series) -> np.ndarray:
    """Require complete binary labels in exactly the feature-row index order."""
    if len(frame) != len(labels) or not frame.index.equals(labels.index):
        raise ValueError("Feature rows and outcome labels must be aligned by index.")
    if not len(labels) or labels.isna().any() or not labels.isin([0, 1]).all():
        raise ValueError("Outcomes must be nonempty, complete binary values 0 and 1.")
    return labels.to_numpy(dtype=int)


def make_preprocessor(scale: bool) -> ColumnTransformer:
    """Retain all-empty labs and fixed missing indicators inside each training fold."""
    numeric: list[tuple[str, SimpleImputer | StandardScaler]] = [
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True))
    ]
    if scale:
        numeric.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            ("numeric", Pipeline(numeric), list(NUMERIC)),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["sex", "asa"],
            ),
            ("missing", MissingIndicator(features="all", error_on_new=False), list(LABS)),
        ],
        verbose_feature_names_out=True,
    )
