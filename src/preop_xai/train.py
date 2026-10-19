"""Training-only model selection with an explicit simpler-first candidate order."""

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from preop_xai.preprocessing import binary_outcomes, feature_matrix, make_preprocessor


@dataclass
class ModelBundle:
    """Mutable only to attach validation calibration after the base fit is fixed."""

    pipeline: Pipeline
    name: str
    parameters: dict[str, float | int]
    cv_score: float
    training_prevalence: float
    calibrator: LogisticRegression | None = None
    threshold: float | None = None
    diagnostics: dict[str, str | float | int] = field(default_factory=dict)
    candidate_scores: list[tuple[dict[str, float | int], float]] = field(default_factory=list)


def fit_models(
    X: pd.DataFrame,
    y: pd.Series,
    seed: int = 2026,
    folds: int = 5,
    quick: bool = False,
) -> dict[str, ModelBundle]:
    """Tune both families on identical training observations; never use validation."""
    x = feature_matrix(X)
    binary_outcomes(x, y)
    y = y.astype(int)
    counts = y.value_counts()
    if set(counts.index) != {0, 1} or int(counts.min()) < 2:
        raise ValueError("Training needs at least two independent patients in each class.")
    effective_folds = min(folds, int(counts.min()))
    if effective_folds < 2:
        raise ValueError("At least two stratified training folds are required.")
    cv = StratifiedKFold(effective_folds, shuffle=True, random_state=seed)
    lr_candidates: list[dict[str, float | int]] = [{"C": c} for c in (0.1, 1.0, 10.0)]
    tree_candidates: list[dict[str, float | int]] = [
        {
            "max_depth": depth,
            "n_estimators": trees,
            "learning_rate": rate,
            "min_child_weight": 5,
            "reg_lambda": 5.0,
        }
        for depth in (2, 3)
        for trees in (100, 200, 300)
        for rate in (0.03, 0.1)
    ]
    if quick:
        lr_candidates = lr_candidates[:1]
        tree_candidates = [
            {
                "max_depth": 2,
                "n_estimators": 30,
                "learning_rate": 0.1,
                "min_child_weight": 5,
                "reg_lambda": 5.0,
            }
        ]
    bundles: dict[str, ModelBundle] = {}
    for name, candidates in (("lr", lr_candidates), ("xgboost", tree_candidates)):
        candidate_scores: list[tuple[dict[str, float | int], float]] = []
        best_score = -np.inf
        best_pipeline = None
        best_parameters = None
        for parameters in candidates:
            model = (
                LogisticRegression(C=parameters["C"], solver="lbfgs", max_iter=3000)
                if name == "lr"
                else XGBClassifier(
                    **parameters,
                    objective="binary:logistic",
                    tree_method="hist",
                    random_state=seed,
                    n_jobs=1,
                )
            )
            pipeline = Pipeline(
                [
                    ("preprocess", make_preprocessor(scale=name == "lr")),
                    ("model", model),
                ]
            )
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                scores: list[float] = []
                for train_index, test_index in cv.split(x, y):
                    fold_pipeline = clone(pipeline)
                    if not isinstance(fold_pipeline, Pipeline):
                        raise TypeError("Cross-validation must clone the complete pipeline.")
                    fold_pipeline.fit(x.iloc[train_index], y.iloc[train_index])
                    probability = np.asarray(
                        fold_pipeline.predict_proba(x.iloc[test_index]), dtype=float
                    )[:, 1]
                    scores.append(float(average_precision_score(y.iloc[test_index], probability)))
            score = float(np.mean(scores))
            candidate_scores.append((parameters, score))
            # Earlier candidates are simpler; ties retain the first candidate.
            if score > best_score + 1e-12:
                best_score, best_pipeline, best_parameters = score, pipeline, parameters
        if best_pipeline is None or best_parameters is None:
            raise RuntimeError("No model candidate was evaluated.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            best_pipeline.fit(x, y)
        bundles[name] = ModelBundle(
            pipeline=best_pipeline,
            name=name,
            parameters=best_parameters,
            cv_score=best_score,
            training_prevalence=float(y.mean()),
            diagnostics={"folds": effective_folds, "mode": "synthetic-smoke" if quick else "full"},
            candidate_scores=candidate_scores,
        )
    return bundles
