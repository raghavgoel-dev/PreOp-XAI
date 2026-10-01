"""Immutable configuration models."""

from typing import ClassVar, Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field, field_validator

from preop_xai.contracts import DataKind


class StrictConfigModel(BaseModel):
    """Shared strict and immutable Pydantic boundary policy."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


class PathsConfig(StrictConfigModel):
    """External storage roots."""

    inspire_data_dir: str | None = None
    private_work_dir: str | None = None
    runs_dir: str | None = None


class SyntheticConfig(StrictConfigModel):
    """Synthetic fixture budget."""

    seed: int = 42
    rows: int = Field(default=64, ge=2)


class SourceConfig(StrictConfigModel):
    """Canonical dataset source."""

    official_url: str


class WindowConfig(StrictConfigModel):
    """Feature lookback windows."""

    strict_days: int = Field(ge=1)
    proxy_days: int = Field(ge=1)


class SplitConfig(StrictConfigModel):
    """Patient-level partition policy."""

    strategy: Literal["grouped_random"]
    train_fraction: float = Field(gt=0.0, lt=1.0)
    validation_fraction: float = Field(gt=0.0, lt=1.0)
    test_fraction: float = Field(gt=0.0, lt=1.0)


class CrossValidationConfig(StrictConfigModel):
    """Training-only cross-validation budget."""

    folds: int = Field(ge=2)
    repeats: int = Field(ge=1)


class LogisticGrid(StrictConfigModel):
    """Penalized logistic-regression grid."""

    regularization_values: tuple[float, ...]

    @field_validator("regularization_values", mode="before")
    @classmethod
    def _parse_values(cls, value: list[float] | tuple[float, ...]) -> tuple[float, ...]:
        return tuple(value)


class TreeGrid(StrictConfigModel):
    """Tree ensemble grid."""

    estimator_values: tuple[int, ...]
    depth_values: tuple[int, ...]

    @field_validator("estimator_values", "depth_values", mode="before")
    @classmethod
    def _parse_values(cls, value: list[int] | tuple[int, ...]) -> tuple[int, ...]:
        return tuple(value)


class EbmGrid(StrictConfigModel):
    """Explainable Boosting Machine grid."""

    interaction_values: tuple[int, ...]
    round_values: tuple[int, ...]

    @field_validator("interaction_values", "round_values", mode="before")
    @classmethod
    def _parse_values(cls, value: list[int] | tuple[int, ...]) -> tuple[int, ...]:
        return tuple(value)


class ModelsConfig(StrictConfigModel):
    """The four frozen model-family grids."""

    logistic_regression: LogisticGrid
    random_forest: TreeGrid
    xgboost: TreeGrid
    explainable_boosting: EbmGrid


class WeightingConfig(StrictConfigModel):
    """Class-weighting policy."""

    strategy: Literal["balanced"]


class CalibrationConfig(StrictConfigModel):
    """Post-hoc calibration policy."""

    method: Literal["sigmoid"]


class ThresholdConfig(StrictConfigModel):
    """Classification-threshold policy."""

    policy: Literal["omit"]


class EvaluationConfig(StrictConfigModel):
    """Uncertainty and stability budgets."""

    bootstrap_replicates: int = Field(ge=1)
    refit_seeds: int = Field(ge=1)
    explanation_bootstrap_refits: int = Field(ge=1)


class ExplanationConfig(StrictConfigModel):
    """Explanation sampling budgets."""

    background_rows: int = Field(ge=1)
    evaluation_rows: int = Field(ge=1)


class SubgroupConfig(StrictConfigModel):
    """Subgroup analysis floor."""

    minimum_cell_size: int = Field(ge=1)


class SuppressionConfig(StrictConfigModel):
    """Small-count reporting suppression."""

    minimum_count: int = Field(ge=1)


class ResourceConfig(StrictConfigModel):
    """Bounded CPU and row budgets."""

    estimator_threads: int = Field(ge=1, le=2)
    max_rows: int | None = Field(default=None, ge=2)
    sequential_training: Literal[True]


class LoggingConfig(StrictConfigModel):
    """Local logging level."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class UiConfig(StrictConfigModel):
    """Localhost UI binding."""

    host: Literal["127.0.0.1", "localhost"]
    port: int = Field(ge=1024, le=65535)


class AppConfig(StrictConfigModel):
    """Validated application configuration."""

    release: str
    data_kind: DataKind
    source: SourceConfig | None = None
    paths: PathsConfig = Field(default_factory=PathsConfig)
    windows: WindowConfig | None = None
    split: SplitConfig | None = None
    cross_validation: CrossValidationConfig | None = None
    models: ModelsConfig | None = None
    weighting: WeightingConfig | None = None
    calibration: CalibrationConfig | None = None
    threshold: ThresholdConfig | None = None
    evaluation: EvaluationConfig | None = None
    explanations: ExplanationConfig | None = None
    subgroups: SubgroupConfig | None = None
    suppression: SuppressionConfig | None = None
    resources: ResourceConfig | None = None
    logging: LoggingConfig | None = None
    ui: UiConfig | None = None
    synthetic: SyntheticConfig = Field(default_factory=SyntheticConfig)

    @field_validator("data_kind", mode="before")
    @classmethod
    def parse_data_kind(cls, value: str | DataKind) -> DataKind:
        """Parse the serialized data-kind tag at the YAML boundary."""
        match value:
            case DataKind():
                return value
            case str():
                return DataKind(value)
            case _:
                assert_never(value)


class CliOverrides(StrictConfigModel):
    """Typed command-line configuration overrides."""

    runs_dir: str | None = None
    synthetic_rows: int | None = Field(default=None, ge=2)
