"""Reproducible study commands; unreviewed clinical analysis fails closed."""

from pathlib import Path
from typing import Annotated

import typer

from preop_xai.config import load_settings, require_review

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
Config = Annotated[Path, typer.Option("--config", exists=True, dir_okay=False)]


def _run_stage(
    stage: str, config: Path, endpoint: str = "mortality", partition: str = "validation"
) -> None:
    from preop_xai.workflow import run_stage

    try:
        run_stage(stage, load_settings(config), endpoint, partition)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error


@app.command()
def audit(config: Config = Path("configs/study.yaml")) -> None:
    """Inventory actual raw tables without approving their clinical semantics."""
    _run_stage("audit", config)


@app.command()
def build_cohort(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("build-cohort", config)


@app.command()
def build_labels(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("build-labels", config)


@app.command()
def build_features(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("build-features", config)


@app.command()
def audit_leakage(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("audit-leakage", config)


@app.command()
def split(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("split", config)


@app.command()
def train(config: Config = Path("configs/study.yaml"), endpoint: str = "mortality") -> None:
    # Check before importing heavy scientific code or touching held-out tables.
    try:
        require_review(load_settings(config), endpoint)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    _run_stage("train", config, endpoint)


@app.command()
def calibrate(config: Config = Path("configs/study.yaml"), endpoint: str = "mortality") -> None:
    _run_stage("calibrate", config, endpoint)


@app.command()
def explain(
    config: Config = Path("configs/study.yaml"),
    endpoint: str = "mortality",
    partition: str = "validation",
) -> None:
    _run_stage("explain", config, endpoint, partition)


@app.command()
def stability(config: Config = Path("configs/study.yaml"), endpoint: str = "mortality") -> None:
    _run_stage("stability", config, endpoint)


@app.command()
def freeze(config: Config = Path("configs/study.yaml"), endpoint: str = "mortality") -> None:
    """Seal configuration, models, explanation outputs and development data."""
    _run_stage("freeze", config, endpoint)


@app.command()
def evaluate(
    config: Config = Path("configs/study.yaml"),
    endpoint: str = "mortality",
    partition: str = "test",
) -> None:
    _run_stage("evaluate", config, endpoint, partition)


@app.command()
def report(config: Config = Path("configs/study.yaml")) -> None:
    _run_stage("report", config)


@app.command()
def export_results(
    source: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option()],
) -> None:
    """Export completed saved evidence read-only into a fresh artifacts directory."""
    from preop_xai.result_artifacts import export_results as export

    try:
        manifest = export(source, output)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Saved aggregate result manifest: {manifest}; research only.")


@app.command()
def predict(
    bundle: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    input_path: Annotated[Path, typer.Option("--input", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option()],
    model: Annotated[str, typer.Option()],
    research_only: Annotated[bool, typer.Option("--research-only")] = False,
) -> None:
    """Predict canonical feature CSVs using trusted saved preprocessing, without fitting."""
    from preop_xai.inference import predict_file

    try:
        predict_file(bundle, input_path, output, model, research_only)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Predictions saved to {output}; research only, clinical use unsupported.")


@app.command()
def demo(
    output: Annotated[Path, typer.Option()] = Path("artifacts/demo"), seed: int = 2026
) -> None:
    """Run the full pipeline on synthetic patients, never clinical results."""
    from preop_xai.demo import run_demo

    run_demo(output, seed)


if __name__ == "__main__":
    app()
