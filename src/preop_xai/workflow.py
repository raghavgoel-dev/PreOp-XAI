"""Persisted stage orchestration, partition isolation and frozen experiment state."""

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import joblib
import numpy as np
import pandas as pd
import typer
import yaml

from preop_xai.config import (
    MappingDocument,
    Settings,
    configuration_hash,
    file_hash,
    require_review,
    write_json,
)
from preop_xai.preprocessing import get_column


class EnvironmentManifest(TypedDict):
    code_commit: str
    configuration_sha256: str
    python: str
    uv: str
    os: str
    machine: str
    processor: str
    packages: dict[str, str]
    seed: int
    code_sha256: dict[str, str]
    lock_sha256: str
    review_evidence: str
    raw_input_sha256: dict[str, str]


def _read_yaml(path: Path) -> MappingDocument:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _guard_mutation(output: Path) -> None:
    if list(output.glob("*/freeze.json")):
        raise ValueError("Analysis is frozen. Use a new output directory for a protocol amendment.")


def _partition(output: Path, partition: str, endpoint: str) -> tuple[pd.DataFrame, pd.Series]:
    from preop_xai.preprocessing import FEATURES

    if partition not in {"train", "validation", "test"}:
        raise ValueError("Partition must be train, validation, or test.")
    frame = pd.read_parquet(output / f"{partition}.parquet")
    frame = frame.loc[get_column(frame, endpoint).notna()]
    if frame.empty:
        raise ValueError(f"No assessable {endpoint} patients in {partition}.")
    return frame.loc[:, list(FEATURES)], get_column(frame, endpoint).astype(int)


def environment_manifest(settings: Settings) -> EnvironmentManifest:
    """Record observed tools and current code, never invented version numbers."""
    packages = (
        "polars",
        "pyarrow",
        "pandas",
        "numpy",
        "scipy",
        "scikit-learn",
        "xgboost",
        "shap",
        "matplotlib",
        "seaborn",
        "pyyaml",
        "joblib",
        "typer",
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    uv_version = subprocess.run(
        ["uv", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    raw_audit = json.loads((settings.output_dir / "audit/audit.json").read_text(encoding="utf-8"))
    return {
        "code_commit": commit,
        "configuration_sha256": configuration_hash(settings),
        "python": sys.version,
        "uv": uv_version,
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": {p: importlib.metadata.version(p) for p in packages},
        "seed": settings.seed,
        "code_sha256": {str(p): file_hash(p) for p in sorted(Path("src/preop_xai").glob("*.py"))},
        "lock_sha256": file_hash(Path("uv.lock")),
        "review_evidence": settings.review_evidence,
        "raw_input_sha256": {name: table["sha256"] for name, table in raw_audit["tables"].items()},
    }


def _sealed_inputs(settings: Settings, endpoint: str) -> dict[str, str]:
    output = settings.output_dir
    paths = [
        settings.path,
        settings.feature_map,
        settings.outcomes,
        Path("uv.lock"),
        *sorted(Path("src/preop_xai").glob("*.py")),
        *(output / f"{p}.parquet" for p in ("train", "validation", "test")),
        output / endpoint / "models.joblib",
        output / endpoint / "bundle.json",
        output / endpoint / "calibration.json",
        output / endpoint / "explain.json",
        output / endpoint / "stability.json",
    ]
    return {str(p): file_hash(p) for p in paths}


def _check_seal(settings: Settings, endpoint: str) -> None:
    path = settings.output_dir / endpoint / "freeze.json"
    if not path.exists():
        raise ValueError(
            "Freeze models, calibration, threshold and explanations before test access."
        )
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen["inputs"] != _sealed_inputs(settings, endpoint):
        raise ValueError(
            "Frozen inputs changed; test access rejected. Do not retune on test findings."
        )


def run_stage(
    stage: str, settings: Settings, endpoint: str = "mortality", partition: str = "validation"
) -> None:
    """Execute one explicit stage; no implicit fitting or test access."""
    output = settings.output_dir
    destination = output / endpoint
    output.mkdir(parents=True, exist_ok=True)
    if stage == "audit":
        from preop_xai.audit import audit_raw
        from preop_xai.status import write_status

        typer.echo(str(audit_raw(settings.raw_dir, output / "audit")))
        write_status(settings, stage)
        return
    if stage == "report":
        from preop_xai.reporting import build_report
        from preop_xai.status import write_status

        write_status(settings, stage)
        typer.echo(str(build_report(output)))
        return
    require_review(settings, endpoint)
    if stage in {"build-cohort", "build-labels", "build-features", "split", "train", "calibrate"}:
        _guard_mutation(output)
    match stage:
        case "build-cohort":
            from preop_xai.cohort import REVIEW_GATES, build_cohort, load_information

            information = load_information(settings.raw_dir)
            information.attrs["review"] = dict.fromkeys(REVIEW_GATES, True)
            cohort = build_cohort(information)
            exclusions = cohort.attrs.pop("exclusions")
            exclusions.to_parquet(output / "cohort_exclusions.parquet", index=False)
            cohort.to_parquet(output / "cohort.parquet", index=False)
            information.to_parquet(output / "information.parquet", index=False)
            write_json(
                output / "cohort_flow.json",
                {
                    "information_rows": len(information),
                    "indexed_patients": len(cohort),
                    "exclusions": exclusions["reason"].value_counts().to_dict(),
                },
            )
        case "build-labels":
            from preop_xai.labels import build_labels, load_complications

            config = _read_yaml(settings.outcomes)
            if config.get("respiratory", {}).get("enabled"):
                require_review(settings, "respiratory")
            labels = build_labels(
                pd.read_parquet(output / "cohort.parquet"),
                pd.read_parquet(output / "information.parquet"),
                load_complications(settings.raw_dir),
                config,
            )
            labels.to_parquet(output / "labels.parquet", index=False)
            write_json(
                output / "assessability.json",
                {
                    ep: {
                        "assessable": int(np.sum(get_column(labels, ep).notna().to_numpy())),
                        "unknown": int(np.sum(get_column(labels, ep).isna().to_numpy())),
                        "events": int(get_column(labels, ep).sum()),
                    }
                    for ep in ("mortality", "respiratory")
                },
            )
        case "build-features":
            from preop_xai.features import build_features, load_labs

            cohort = pd.read_parquet(output / "cohort.parquet")
            mapping = _read_yaml(settings.feature_map)
            labs = load_labs(settings.raw_dir, cohort, mapping)
            write_json(output / "raw_lab_selection.json", labs.attrs["raw_selection_counts"])
            features, provenance = build_features(cohort, labs, mapping)
            features.to_parquet(output / "features.parquet", index=False)
            provenance.to_parquet(output / "provenance.parquet", index=False)
        case "audit-leakage":
            from preop_xai.features import audit_leakage

            audit_leakage(
                pd.read_parquet(output / "cohort.parquet"),
                pd.read_parquet(output / "features.parquet"),
                pd.read_parquet(output / "provenance.parquet"),
                _read_yaml(settings.feature_map),
            )
            write_json(output / "leakage_audit.json", {"passed": True})
        case "split":
            from preop_xai.features import audit_leakage
            from preop_xai.splits import assign_splits

            features = pd.read_parquet(output / "features.parquet")
            audit_leakage(
                pd.read_parquet(output / "cohort.parquet"),
                features,
                pd.read_parquet(output / "provenance.parquet"),
                _read_yaml(settings.feature_map),
            )
            splits = assign_splits(pd.read_parquet(output / "labels.parquet"), settings.seed)
            splits.to_parquet(output / "split_manifest.parquet", index=False)
            combined = features.merge(
                splits, on=["patient_id", "operation_id", "t0"], validate="one_to_one"
            )
            for name in ("train", "validation", "test"):
                combined.loc[combined.partition.eq(name)].to_parquet(
                    output / f"{name}.parquet",
                    index=False,
                )
            write_json(
                output / "split_counts.json",
                {
                    name: {
                        ep: {
                            "n": int(np.sum(get_column(group, ep).notna().to_numpy())),
                            "events": int(get_column(group, ep).sum()),
                        }
                        for ep in ("mortality", "respiratory")
                    }
                    for name, group in combined.groupby("partition")
                },
            )
            write_json(output / "manifest.json", environment_manifest(settings))
        case "train":
            from preop_xai.train import fit_models

            x, y = _partition(output, "train", endpoint)
            models = fit_models(x, y, settings.seed, settings.folds)
            destination.mkdir(exist_ok=True)
            joblib.dump(models, destination / "models.joblib")
            models["xgboost"].pipeline.named_steps["model"].save_model(
                destination / "xgboost.json",
            )
            write_json(
                destination / "selection.json",
                {
                    name: {
                        "parameters": b.parameters,
                        "cv_score": b.cv_score,
                        "training_prevalence": b.training_prevalence,
                        "diagnostics": b.diagnostics,
                        "candidate_scores": b.candidate_scores,
                    }
                    for name, b in models.items()
                },
            )
            linear = models["lr"].pipeline
            pd.DataFrame(
                {
                    "feature": linear.named_steps["preprocess"].get_feature_names_out(),
                    "coefficient": linear.named_steps["model"].coef_[0],
                    "scale": (
                        "training-imputed/scaled numeric; one-hot categories; binary missing flags"
                    ),
                }
            ).to_csv(destination / "lr_coefficients.csv", index=False)
        case "calibrate":
            from preop_xai.calibration import calibrate_models
            from preop_xai.inference import write_bundle_metadata

            models = joblib.load(destination / "models.joblib")
            x, y = _partition(output, "validation", endpoint)
            calibrate_models(models, x, y)
            joblib.dump(models, destination / "models.joblib")
            write_json(
                destination / "calibration.json",
                {name: bundle.diagnostics for name, bundle in models.items()},
            )
            write_bundle_metadata(
                destination,
                endpoint=endpoint,
                synthetic_only=settings.synthetic_only,
                review_status=(
                    "synthetic-fixture-only"
                    if settings.synthetic_only
                    else "attested-not-independently-verified"
                ),
                feature_mapping=_read_yaml(settings.feature_map),
            )
        case "explain":
            from preop_xai.explain import explain_models

            if partition == "test":
                _check_seal(settings, endpoint)
                if not (destination / "evaluation_complete.json").exists():
                    raise ValueError("Explain test predictions only after the frozen evaluation.")
            elif partition != "validation":
                raise ValueError("Explanation partition must be validation or test.")
            x_train, _ = _partition(output, "train", endpoint)
            x, y = _partition(output, partition, endpoint)
            target = destination if partition == "validation" else destination / "test_explanations"
            if partition == "validation":
                _guard_mutation(output)
            explain_models(
                joblib.load(destination / "models.joblib"), x_train, x, y, target, settings.seed
            )
        case "stability":
            from preop_xai.stability import run_stability

            _guard_mutation(output)
            x, y = _partition(output, "train", endpoint)
            validation, _ = _partition(output, "validation", endpoint)
            run_stability(
                joblib.load(destination / "models.joblib"),
                x,
                y,
                validation,
                destination,
                settings.stability_refits,
                settings.seed,
            )
        case "freeze":
            models = joblib.load(destination / "models.joblib")
            if any("calibration_status" not in b.diagnostics for b in models.values()):
                raise ValueError("Both models require a recorded validation calibration attempt.")
            path = destination / "freeze.json"
            if path.exists():
                raise ValueError("Analysis is already frozen.")
            write_json(
                path,
                {
                    "inputs": _sealed_inputs(settings, endpoint),
                    "manifest": environment_manifest(settings),
                },
            )
        case "evaluate":
            from preop_xai.evaluate import evaluate_models

            if partition != "test":
                raise ValueError("Final evaluation uses partition test only.")
            _check_seal(settings, endpoint)
            marker = destination / "evaluation_started.json"
            if marker.exists():
                raise ValueError(
                    "Test evaluation already unlocked; reuse frozen outputs, not reruns."
                )
            write_json(marker, {"frozen": True})
            x, y = _partition(output, "test", endpoint)
            evaluate_models(
                joblib.load(destination / "models.joblib"),
                x,
                y,
                destination,
                settings.evaluation_bootstraps,
                settings.seed,
            )
            write_json(
                destination / "evaluation_complete.json",
                {"completed": True, "models_sha256": file_hash(destination / "models.joblib")},
            )
        case _:
            raise ValueError(f"Unknown pipeline stage: {stage}")
    from preop_xai.status import write_status

    status_stage = f"explain-{partition}" if stage == "explain" and partition == "test" else stage
    write_status(settings, status_stage, endpoint)
    typer.echo(f"{stage}: complete ({output}); research execution, not clinical validation")
