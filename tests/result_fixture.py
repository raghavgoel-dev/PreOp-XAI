"""Deterministic completed-export contract fixture, not fitted campaign results.

Run: uv run --locked python tests/result_fixture.py --output artifacts/NEW_FIXTURE
No models, calibrators, held-out evaluations or bootstrap refits are run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from preop_xai.result_io import save_json, sha256


def create_fixture(output: Path, *, respiratory: bool = True) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    save_json(
        output / "manifest.json",
        {
            "code_commit": "deterministic-export-contract-fixture",
            "fixture": True,
            "description": "Constructed saved arrays; no fitted model or clinical experiment.",
        },
    )
    endpoints = ["mortality", "respiratory"] if respiratory else ["mortality"]
    save_json(
        output / "status.json",
        {
            "synthetic_only": True,
            "pipeline_execution": "synthetic-export-contract-fixture",
            "data_review": "synthetic-fixture-only",
            "clinical_use": "unsupported-research-only",
            "endpoints": {
                endpoint: {
                    "review": "synthetic-fixture-only",
                    "internal_validation": "synthetic-evaluation-complete",
                    "predictive_reliability": "not-established",
                }
                for endpoint in endpoints
            },
        },
    )
    y = np.array([0, 1, 0, 0, 1, 0, 1, 0], dtype=int)
    for endpoint in endpoints:
        directory = output / endpoint
        directory.mkdir()
        # Deliberately not a serialized estimator. Any model-loading call must fail.
        (directory / "models.joblib").write_bytes(b"EXPORT FIXTURE: DO NOT DESERIALIZE\n")
        model_metrics = {}
        saved = {}
        for model, raw in (
            ("lr", np.array([0, 0.6, 0.2, 0.8, 1, 0.2, 0.6, 0.1])),
            ("xgboost", np.array([0.1, 0.8, 0.1, 0.5, 0.8, 0, 1, 0.2])),
        ):
            invalid = endpoint == "respiratory"
            p = 1 - raw if invalid else 0.1 + 0.7 * raw
            threshold = 0.45
            predicted = p >= threshold
            tp = int(np.sum((y == 1) & predicted))
            fp = int(np.sum((y == 0) & predicted))
            tn = int(np.sum((y == 0) & ~predicted))
            fn = int(np.sum((y == 1) & ~predicted))
            diagnostic = {
                "offset_intercept": None,
                "joint_intercept": None,
                "joint_slope": None,
                "converged": False,
                "status": "not-estimated-contract-fixture",
            }

            def ranking(probability):
                return {
                    "auroc": float(roc_auc_score(y, probability)),
                    "average_precision": float(average_precision_score(y, probability)),
                    "brier": float(brier_score_loss(y, probability)),
                }

            model_metrics[model] = {
                "raw": ranking(raw),
                "calibrated": ranking(p),
                "training_prevalence_brier": float(np.mean((y - 0.25) ** 2)),
                "raw_calibration": diagnostic,
                "calibration": diagnostic,
                "threshold": threshold,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "sensitivity": tp / (tp + fn),
                "specificity": tn / (tn + fp),
                "ppv": tp / (tp + fp),
                "npv": tn / (tn + fn) if tn + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn),
                "calibration_status": "nonpositive-slope" if invalid else "fitted",
                "probability_use": "invalid-diagnostic-only" if invalid else "research-only",
                "classification_use": "fixed validation operating point; not clinical advice",
                "bins": [],
                "raw_bins": [],
            }
            saved[f"{model}_raw"] = raw
            saved[f"{model}_calibrated"] = p
        save_json(
            directory / "metrics.json",
            {
                "n": len(y),
                "events": int(y.sum()),
                "prevalence": float(y.mean()),
                "models": model_metrics,
                "bootstrap_resamples": 0,
                "seed": 0,
                "intervals": {},
                "fixture": True,
            },
        )
        # Non-dictionary ordering exercises named alignment in the real CLI.
        names = ["xgboost_calibrated", "lr_raw", "xgboost_raw", "lr_calibrated"]
        np.savez_compressed(
            directory / "predictions.npz",
            y=y,
            names=np.array(names),
            probabilities=np.stack([saved[name] for name in names]),
            patient_ids=np.array([f"PRIVATE_SENTINEL_PATIENT_{i}" for i in range(len(y))]),
        )
        (directory / "intervals.csv").write_text(
            "comparison,lower,upper,effective_resamples,undefined\n", encoding="utf-8"
        )
        save_json(directory / "evaluation_started.json", {"frozen": True, "fixture": True})
        # Known per-refit contributions: patient-mean absolute importance SD is calculable.
        from preop_xai.preprocessing import FEATURES
        from preop_xai.stability import StabilityResult, _summarize

        private = directory / "private"
        private.mkdir()
        draws = [1, 4, 7]
        stability: StabilityResult = {
            "seed": 0,
            "requested_refits": 8,
            "successful_paired_draws": draws,
            "validation_n": 4,
            "background_n": 2,
            "paired_draws": True,
            "scale": "raw model log-odds",
            "background_convention": "deterministic contract fixture",
            "grouping": "clinical concepts",
            "limitations": ["Constructed export fixture; no refits performed."],
            "models": {},
        }
        for model in ("lr", "xgboost"):
            contributions = np.arange(1, 121, dtype=float).reshape(3, 4, len(FEATURES)) / 100
            if model == "xgboost":
                contributions = contributions[..., ::-1].copy()
            baselines = np.array([[0.1] * 4, [0.3] * 4, [0.2] * 4])
            model_summary = _summarize(contributions, baselines)
            model_summary.update(status="partial", successful_refits=3)
            stability["models"][model] = model_summary
            np.savez_compressed(
                private / f"{model}_stability.npz",
                successful_draws=np.array(draws),
                grouped_contributions=contributions,
                baselines=baselines,
            )
        save_json(directory / "stability.json", stability)
        freeze_paths = [
            directory / "models.joblib",
            directory / "stability.json",
            output / "manifest.json",
            output / "status.json",
        ]
        save_json(
            directory / "freeze.json",
            {
                "inputs": {str(path): sha256(path) for path in freeze_paths},
                "manifest": json.loads((output / "manifest.json").read_text(encoding="utf-8")),
            },
        )
        save_json(
            directory / "evaluation_complete.json",
            {
                "completed": True,
                "models_sha256": sha256(directory / "models.joblib"),
            },
        )
    return output


def main(output: Annotated[Path, typer.Option()]) -> None:
    typer.echo(create_fixture(output))


if __name__ == "__main__":
    typer.run(main)
