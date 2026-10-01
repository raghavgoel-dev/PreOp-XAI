from pathlib import Path

import pytest
from pydantic import ValidationError

from preop_xai.config import CliOverrides, load_config


def _write_config(path: Path, *, rows: int | None = None) -> None:
    rows_line = "" if rows is None else f"  rows: {rows}\n"
    content = f"""release: '1.4.2'
data_kind: synthetic
paths: {{}}
synthetic:
  seed: 42
{rows_line}"""
    _ = path.write_text(
        content,
        encoding="utf-8",
    )


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    # Given
    config_path = tmp_path / "invalid.yaml"
    _write_config(config_path)
    _ = config_path.write_text(
        config_path.read_text(encoding="utf-8") + "unknown_key: true\n",
        encoding="utf-8",
    )

    # When / Then
    with pytest.raises(ValidationError):
        _ = load_config(config_path, repository_root=tmp_path / "repository")


def test_config_precedence_is_cli_env_yaml_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, rows=11)
    monkeypatch.setenv("PREOP_SYNTHETIC_ROWS", "12")

    # When
    configured = load_config(
        config_path,
        repository_root=tmp_path / "repository",
        overrides=CliOverrides(synthetic_rows=13),
    )

    # Then
    assert configured.synthetic.rows == 13
    assert configured.synthetic.seed == 42


def test_config_uses_default_when_yaml_omits_value(tmp_path: Path) -> None:
    # Given
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    # When
    configured = load_config(
        config_path,
        repository_root=tmp_path / "repository",
    )

    # Then
    assert configured.synthetic.rows == 64


def test_config_loads_private_roots_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    monkeypatch.setenv("INSPIRE_DATA_DIR", str(raw_root))
    monkeypatch.setenv("PREOP_PRIVATE_WORK_DIR", str(work_root))

    # When
    configured = load_config(
        config_path,
        repository_root=tmp_path / "repository",
    )

    # Then
    assert configured.paths.inspire_data_dir == str(raw_root)
    assert configured.paths.private_work_dir == str(work_root)


def test_config_rejects_repository_internal_run_root(tmp_path: Path) -> None:
    # Given
    repository = tmp_path / "repository"
    repository.mkdir()
    config_path = tmp_path / "config.yaml"
    content = f"""release: '1.4.2'
data_kind: synthetic
paths:
  runs_dir: '{(repository / "runs").as_posix()}'
synthetic: {{seed: 42}}"""
    _ = config_path.write_text(
        content + "\n",
        encoding="utf-8",
    )

    # When / Then
    with pytest.raises(ValueError, match="external"):
        _ = load_config(config_path, repository_root=repository)
