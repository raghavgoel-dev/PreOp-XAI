"""Strict feature-only inference from trusted local, version-matched artifacts.

CSV values declare the canonical units in bundle.json; no unit conversion or
preoperative timestamp verification is possible at this boundary. Joblib files
are executable Python artifacts and must only come from a trusted local source.
"""

import csv
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Final, NotRequired, TypedDict

import joblib
import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.validation import check_is_fitted
from xgboost import XGBClassifier

from preop_xai.audit import _numeric_series
from preop_xai.calibration import calibration_status, raw_scores
from preop_xai.config import MappingDocument, file_hash, write_json
from preop_xai.preprocessing import FEATURES, LABS, NUMERIC, get_column
from preop_xai.train import ModelBundle


class RuntimeMetadata(TypedDict):
    python: str
    packages: dict[str, str]


class FeatureSpec(TypedDict):
    name: str
    kind: str
    canonical_unit: NotRequired[str]
    min: NotRequired[float]
    max: NotRequired[float]
    missing: NotRequired[str]


class CategorySpec(TypedDict):
    allowed: list[str] | str
    missing: str


class CategoryPolicy(TypedDict):
    asa: CategorySpec
    sex: CategorySpec
    unseen: str


class BundleMetadata(TypedDict):
    artifact_version: int
    endpoint: str
    synthetic_only: bool
    data_review_status: str
    models_sha256: str
    runtime: RuntimeMetadata
    schema: list[FeatureSpec]
    feature_mapping: MappingDocument
    categorical_policy: CategoryPolicy
    input_units: str
    positive_event: int
    clinical_use: str
    internal_validation_status: str


ARTIFACT_VERSION: Final = 1
PACKAGES: Final = ("numpy", "scipy", "scikit-learn", "xgboost", "pandas", "joblib")
CANONICAL_UNITS: Final = {
    "hemoglobin": "g/dL",
    "platelets": "10^9/L",
    "creatinine": "mg/dL",
    "bun": "mg/dL",
    "sodium": "mmol/L",
    "potassium": "mmol/L",
    "glucose": "mg/dL",
}
CATEGORICAL_POLICY: Final[CategoryPolicy] = {
    "asa": {"allowed": ["1", "2", "3", "4", "5", "unknown"], "missing": "unknown"},
    "sex": {"allowed": "arbitrary-strings", "missing": "unknown"},
    "unseen": "ignore-with-fitted-one-hot-encoder",
}


def _runtime() -> RuntimeMetadata:
    return {
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in PACKAGES},
    }


def _schema(feature_mapping: MappingDocument) -> list[FeatureSpec]:
    if not isinstance(feature_mapping, dict) or feature_mapping.get("reviewed") is not True:
        raise ValueError("Inference requires a reviewed feature mapping.")
    labs = feature_mapping.get("labs")
    if not isinstance(labs, dict) or set(labs) != set(LABS):
        raise ValueError("Feature mapping must contain exactly the seven canonical labs.")
    schema: list[FeatureSpec] = [
        {"name": "age", "kind": "numeric", "canonical_unit": "years", "min": 18, "max": 90},
        {"name": "sex", "kind": "categorical"},
        {"name": "asa", "kind": "categorical"},
    ]
    for name in LABS:
        spec = labs[name]
        if not isinstance(spec, dict):
            raise ValueError(f"Invalid lab mapping: {name}")
        units = spec.get("units", {})
        if not isinstance(units, dict) or not units:
            raise ValueError(f"Canonical unit missing for {name}.")
        try:
            factors = np.asarray(list(units.values()), dtype=float)
            bounds = np.asarray([spec["min"], spec["max"]], dtype=float)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid units or bounds for {name}.") from error
        if (
            not np.isfinite(factors).all()
            or (factors <= 0).any()
            or not np.isfinite(bounds).all()
            or bounds[0] >= bounds[1]
        ):
            raise ValueError(f"Invalid units or bounds for {name}.")
        # These are targets of upstream normalization, not source-unit aliases.
        # A source dictionary need not contain a factor-one spelling of its target.
        canonical = CANONICAL_UNITS[name]
        schema.append(
            {
                "name": name,
                "kind": "numeric",
                "canonical_unit": canonical,
                "min": float(bounds[0]),
                "max": float(bounds[1]),
                "missing": "permitted",
            }
        )
    return schema


def _internal_validation(destination: Path, metadata: BundleMetadata) -> str:
    marker = destination / "evaluation_complete.json"
    if not marker.exists():
        return "not-completed"
    completion = json.loads(marker.read_text(encoding="utf-8"))
    if (
        not isinstance(completion, dict)
        or completion.get("models_sha256") != metadata["models_sha256"]
    ):
        raise ValueError("Evaluation marker model hash does not match the bundle.")
    if completion.get("completed") is not True:
        return "not-completed"
    kind = "synthetic" if metadata["synthetic_only"] else "retrospective"
    return f"{kind}-internal-evaluation-complete"


def write_bundle_metadata(
    destination: Path,
    *,
    endpoint: str,
    synthetic_only: bool,
    review_status: str,
    feature_mapping: MappingDocument,
) -> None:
    """Describe existing models without loading or changing them; reject frozen exports."""
    destination = Path(destination)
    if (destination / "freeze.json").exists():
        raise ValueError("Analysis is frozen; do not modify an old campaign.")
    if endpoint not in {"mortality", "respiratory"}:
        raise ValueError("Endpoint must be mortality or respiratory.")
    if type(synthetic_only) is not bool or not isinstance(review_status, str) or not review_status:
        raise ValueError("Explicit synthetic_only and data review status are required.")
    schema = _schema(feature_mapping)
    metadata: BundleMetadata = {
        "artifact_version": ARTIFACT_VERSION,
        "endpoint": endpoint,
        "synthetic_only": synthetic_only,
        "data_review_status": review_status,
        "models_sha256": file_hash(destination / "models.joblib"),
        "runtime": _runtime(),
        "schema": schema,
        "feature_mapping": feature_mapping,
        "categorical_policy": CATEGORICAL_POLICY,
        "input_units": "canonical-only-no-conversion",
        "positive_event": 1,
        "clinical_use": "unsupported-research-only",
        "internal_validation_status": "not-completed",
    }
    metadata["internal_validation_status"] = _internal_validation(destination, metadata)
    write_json(destination / "bundle.json", metadata)


def _read_metadata(destination: Path) -> BundleMetadata:
    metadata: BundleMetadata = json.loads((destination / "bundle.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or not BundleMetadata.__required_keys__ <= metadata.keys():
        raise ValueError("Inference metadata is missing required fields.")
    if not isinstance(metadata, dict) or type(metadata.get("artifact_version")) is not int:
        raise ValueError("Invalid inference artifact version.")
    if metadata["artifact_version"] != ARTIFACT_VERSION:
        raise ValueError("Unsupported inference artifact version.")
    if metadata.get("runtime") != _runtime():
        raise ValueError("Inference runtime versions do not match the saved bundle.")
    if metadata.get("schema") != _schema(metadata["feature_mapping"]):
        raise ValueError("Inference schema does not match the reviewed feature mapping.")
    if (
        metadata.get("categorical_policy") != CATEGORICAL_POLICY
        or metadata.get("input_units") != "canonical-only-no-conversion"
        or type(metadata.get("positive_event")) is not int
        or metadata["positive_event"] != 1
        or metadata.get("clinical_use") != "unsupported-research-only"
        or metadata.get("endpoint") not in {"mortality", "respiratory"}
        or type(metadata.get("synthetic_only")) is not bool
        or not isinstance(metadata.get("data_review_status"), str)
        or not metadata["data_review_status"]
    ):
        raise ValueError("Incompatible inference metadata or categorical policy.")
    if metadata.get("models_sha256") != file_hash(destination / "models.joblib"):
        raise ValueError("Model artifact SHA256 does not match bundle.json.")
    metadata["internal_validation_status"] = _internal_validation(destination, metadata)
    return metadata


def _read_features(input_path: Path, schema: list[FeatureSpec]) -> pd.DataFrame:
    names = [column["name"] for column in schema]
    try:
        with Path(input_path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, [])
            if (
                len(header) != len(names)
                or len(set(header)) != len(header)
                or set(header) != set(names)
            ):
                raise ValueError("CSV header requires exactly the ten unique canonical features.")
            rows = []
            for position, row in enumerate(reader):
                if len(row) != len(names):
                    raise ValueError(f"Invalid CSV column count at row_position {position}.")
                rows.append(row)
    except csv.Error as error:
        raise ValueError(f"Malformed CSV input: {error}") from error
    if not rows:
        raise ValueError("CSV must contain at least one nonempty feature row.")
    frame = pd.DataFrame(rows, columns=header).loc[:, names]
    for column in NUMERIC:
        text = get_column(frame, column).str.strip()
        missing = text.eq("")
        if column == "age" and missing.any():
            raise ValueError("Age is required and must be a finite adult age.")
        try:
            values = _numeric_series(text.mask(missing), errors="raise").astype(float)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Nonnumeric values in {column}.") from error
        if not np.isfinite(values.loc[~missing]).all():
            raise ValueError(f"Nonfinite values in {column}.")
        spec = next(item for item in schema if item["name"] == column)
        if "min" not in spec or "max" not in spec:
            raise ValueError(f"Missing canonical numeric bounds for {column}.")
        outside = values.lt(spec["min"])
        outside |= values.gt(spec["max"])
        if outside.any():
            raise ValueError(f"{column} is outside reviewed canonical bounds.")
        frame[column] = values
    frame["sex"] = frame["sex"].mask(frame["sex"].str.strip().eq(""), "unknown")
    asa = []
    for value in frame["asa"].str.strip():
        if value in {"", "unknown"}:
            asa.append("unknown")
            continue
        try:
            number = float(value)
        except ValueError as error:
            raise ValueError("ASA must be 1..5 or unknown.") from error
        if not np.isfinite(number) or number not in (1, 2, 3, 4, 5):
            raise ValueError("ASA must be 1..5 or unknown.")
        asa.append(str(int(number)))
    frame["asa"] = asa
    return frame


def _validate_model(bundle: ModelBundle, name: str) -> ModelBundle:
    if not isinstance(bundle, ModelBundle) or bundle.name != name:
        raise ValueError("Model artifact is not the requested ModelBundle.")
    pipeline = bundle.pipeline
    if not isinstance(pipeline, Pipeline) or list(pipeline.named_steps) != ["preprocess", "model"]:
        raise ValueError("Model artifact requires the fitted preprocessing/model pipeline.")
    preprocess = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    expected_type = LogisticRegression if name == "lr" else XGBClassifier
    if not isinstance(preprocess, ColumnTransformer) or not isinstance(model, expected_type):
        raise ValueError("Incompatible preprocessing or model family.")
    try:
        check_is_fitted(preprocess)
        check_is_fitted(model)
        encoder = preprocess.named_transformers_["categorical"]
        if not isinstance(encoder, OneHotEncoder) or encoder.handle_unknown != "ignore":
            raise ValueError("Fitted OneHotEncoder must ignore unknown categories.")
        check_is_fitted(encoder)
    except (NotFittedError, AttributeError, KeyError) as error:
        raise ValueError("Model and preprocessing must be fitted.") from error
    if not np.array_equal(np.asarray(getattr(preprocess, "feature_names_in_", None)), FEATURES):
        raise ValueError("Fitted preprocessing schema does not match the canonical features.")
    if not np.array_equal(model.classes_, [0, 1]):
        raise ValueError("Model classes must be [0, 1], with positive event 1.")
    return bundle


def _calibration_status(bundle: ModelBundle) -> str:
    calibrator = bundle.calibrator
    if calibrator is None:
        status = calibration_status(bundle)
        return "not-fitted" if status == "fitted" else status
    if not isinstance(calibrator, LogisticRegression):
        return "incompatible"
    try:
        check_is_fitted(calibrator)
        coefficient = np.asarray(calibrator.coef_, dtype=float)
        intercept = np.asarray(calibrator.intercept_, dtype=float)
        if (
            coefficient.shape != (1, 1)
            or intercept.shape != (1,)
            or getattr(calibrator, "n_features_in_", None) != 1
            or not np.array_equal(calibrator.classes_, [0, 1])
        ):
            return "incompatible"
    except (NotFittedError, AttributeError, TypeError, ValueError):
        return "unfitted"
    if not np.isfinite(coefficient).all() or not np.isfinite(intercept).all():
        return "nonfinite"
    return "fitted" if coefficient[0, 0] > 0 else "nonpositive-slope"


def predict_file(
    bundle: Path,
    input_path: Path,
    output: Path,
    model: str,
    research_only: bool = False,
) -> None:
    """Predict without fitting; invalid calibration requires explicit raw-only mode."""
    if model not in {"lr", "xgboost"}:
        raise ValueError("Model must be lr or xgboost.")
    destination = Path(bundle)
    metadata = _read_metadata(destination)
    frame = _read_features(input_path, metadata["schema"])
    # All declarative compatibility checks run before loading executable artifacts.
    models = joblib.load(destination / "models.joblib")
    if not isinstance(models, dict) or set(models) != {"lr", "xgboost"}:
        raise ValueError("Model artifact must contain the lr and xgboost ModelBundles.")
    fitted = _validate_model(models[model], model)
    status = _calibration_status(fitted)
    if status != "fitted" and not research_only:
        raise ValueError(
            f"Validation calibration is invalid ({status}); use research-only raw output."
        )
    if status == "fitted":
        threshold = fitted.threshold
        if (
            not isinstance(threshold, (int, float, np.integer, np.floating))
            or isinstance(threshold, (bool, np.bool_))
            or not np.isfinite(threshold)
            or not 0 <= threshold <= 1
        ):
            raise ValueError("A finite saved research threshold in [0, 1] is required.")
    score = np.asarray(raw_scores(fitted, frame), dtype=float)
    if score.shape != (len(frame),) or not np.isfinite(score).all():
        raise ValueError("Model produced invalid raw scores.")
    result = pd.DataFrame({"row_position": np.arange(len(frame)), "raw_score": score})
    result["raw_probability"] = expit(score)
    result["calibrated_probability"] = np.nan
    result["research_threshold"] = np.nan
    result["research_classification"] = pd.Series([None] * len(frame), dtype=object)
    if status == "fitted":
        calibrator = fitted.calibrator
        threshold = fitted.threshold
        if calibrator is None or threshold is None:
            raise ValueError("Fitted calibration and its saved threshold are required.")
        a = float(np.asarray(calibrator.intercept_).reshape(-1)[0])
        calibrated = expit(a + calibrator.coef_[0, 0] * score)
        result["calibrated_probability"] = calibrated
        result["research_threshold"] = fitted.threshold
        result["research_classification"] = (calibrated >= threshold).astype(int)
    result["model"] = model
    result["calibration_status"] = status
    for name in (
        "endpoint",
        "artifact_version",
        "synthetic_only",
        "internal_validation_status",
        "data_review_status",
        "clinical_use",
    ):
        result[name] = metadata[name]
    result["timing_status"] = "not-verifiable-from-feature-only-input"
    output = Path(output)
    protected = [destination / "models.joblib", destination / "bundle.json", Path(input_path)]
    within_bundle = destination.resolve() in output.resolve().parents
    if output.resolve() in [path.resolve() for path in protected] or within_bundle:
        raise ValueError("Prediction output must not overwrite inputs or bundle artifacts.")
    if output.suffix.lower() != ".csv" or output.exists():
        raise ValueError(
            "Prediction output must be a new .csv path; existing evidence is preserved."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
