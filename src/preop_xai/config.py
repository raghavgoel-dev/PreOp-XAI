"""Strict YAML loading and configuration precedence."""

import os
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from preop_xai.config_models import AppConfig, CliOverrides
from preop_xai.privacy import require_external_path

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

__all__ = ["AppConfig", "CliOverrides", "load_config"]


def load_config(
    path: Path,
    *,
    repository_root: Path,
    overrides: CliOverrides | None = None,
) -> AppConfig:
    """Load validated YAML with CLI-over-environment precedence."""
    with path.open(encoding="utf-8") as stream:
        raw = TypeAdapter(dict[str, JsonValue]).validate_python(yaml.safe_load(stream))
    config = AppConfig.model_validate(raw)

    environment_rows = os.environ.get("PREOP_SYNTHETIC_ROWS")
    if environment_rows is not None:
        config = config.model_copy(
            update={
                "synthetic": config.synthetic.model_copy(
                    update={"rows": int(environment_rows)},
                )
            }
        )
    environment_paths = {
        field_name: value
        for field_name, variable_name in (
            ("inspire_data_dir", "INSPIRE_DATA_DIR"),
            ("private_work_dir", "PREOP_PRIVATE_WORK_DIR"),
            ("runs_dir", "PREOP_RUNS_DIR"),
        )
        if (value := os.environ.get(variable_name)) is not None
    }
    if environment_paths:
        config = config.model_copy(
            update={
                "paths": config.paths.model_copy(
                    update=environment_paths,
                )
            }
        )
    if overrides is not None:
        if overrides.synthetic_rows is not None:
            config = config.model_copy(
                update={
                    "synthetic": config.synthetic.model_copy(
                        update={"rows": overrides.synthetic_rows},
                    )
                }
            )
        if overrides.runs_dir is not None:
            config = config.model_copy(
                update={
                    "paths": config.paths.model_copy(
                        update={"runs_dir": overrides.runs_dir},
                    )
                }
            )

    for configured_path in (
        config.paths.inspire_data_dir,
        config.paths.private_work_dir,
        config.paths.runs_dir,
    ):
        if configured_path is not None:
            _ = require_external_path(Path(configured_path), repository_root)
    return config
