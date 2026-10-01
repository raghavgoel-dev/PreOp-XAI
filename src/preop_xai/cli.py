"""PreOp-XAI command-line interface."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import anyio
import httpx2
import typer
from pydantic import TypeAdapter
from typer.models import OptionInfo

from preop_xai.acquire.download import download_entry
from preop_xai.acquire.guards import (
    require_data_kind,
    require_release,
    require_verified_mappings,
)
from preop_xai.acquire.inventory import load_inventory
from preop_xai.acquire.plan import DownloadPlan, build_download_plan
from preop_xai.acquire.prepare import TableMapping, prepare_mapped_tables
from preop_xai.acquire.verify import verify_downloads
from preop_xai.artifacts import write_synthetic_artifacts
from preop_xai.audit import AuditEvidence, audit_capabilities
from preop_xai.config import CliOverrides, load_config
from preop_xai.config_models import AppConfig
from preop_xai.contracts import DataKind
from preop_xai.doctor import build_doctor_report
from preop_xai.privacy import require_external_path
from preop_xai.synthetic.generator import generate_synthetic

app = typer.Typer(no_args_is_help=True)


class DownloadScope(StrEnum):
    """Supported authenticated download scopes."""

    FULL_RELEASE = "full-release"
    REQUIRED_TABLES = "required-tables"


_REQUIRED_LOGICAL_ROLES = frozenset(
    {"operations", "preoperative_results", "admissions", "outcomes"}
)


def _external_root(value: str | None, variable_name: str) -> Path:
    if value is None:
        message = f"{variable_name} is required"
        raise typer.BadParameter(message)
    return require_external_path(Path(value), Path.cwd())


def _raw_root(config: AppConfig) -> Path:
    return _external_root(config.paths.inspire_data_dir, "INSPIRE_DATA_DIR")


def _work_root(config: AppConfig) -> Path:
    return _external_root(config.paths.private_work_dir, "PREOP_PRIVATE_WORK_DIR")


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    _ = temporary.write_text(content, encoding="utf-8")
    _ = temporary.replace(path)


def _load_plan(path: Path) -> DownloadPlan:
    return DownloadPlan.model_validate_json(path.read_text(encoding="utf-8"))


def _scope_plan(plan: DownloadPlan, scope: DownloadScope) -> DownloadPlan:
    if scope is DownloadScope.FULL_RELEASE:
        return plan
    entries = tuple(
        entry for entry in plan.entries if entry.logical_role in _REQUIRED_LOGICAL_ROLES
    )
    return plan.model_copy(update={"entries": entries})


async def _download_plan(
    plan: DownloadPlan,
    raw_root: Path,
    username: str,
    password: str,
) -> None:
    transport = httpx2.AsyncHTTPTransport(retries=3)
    timeout = httpx2.Timeout(30.0, connect=10.0)
    limits = httpx2.Limits(max_connections=2, max_keepalive_connections=2)
    async with httpx2.AsyncClient(
        auth=(username, password),
        transport=transport,
        timeout=timeout,
        limits=limits,
        http2=True,
        follow_redirects=False,
    ) as client:
        for entry in plan.entries:
            _ = await download_entry(client, entry, raw_root)


@app.command()
def doctor(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
) -> None:
    """Report software and scientific readiness."""
    loaded = load_config(config, repository_root=Path.cwd())
    report = build_doctor_report(loaded)
    typer.echo(report.model_dump_json(indent=2))


@app.command()
def synthetic(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
    runs_dir: Annotated[Path | None, OptionInfo(default=...)] = None,
) -> None:
    """Generate deterministic synthetic fixtures."""
    overrides = CliOverrides(runs_dir=str(runs_dir) if runs_dir is not None else None)
    loaded = load_config(config, repository_root=Path.cwd(), overrides=overrides)
    configured_root = loaded.paths.runs_dir
    if configured_root is None:
        message = "PREOP_RUNS_DIR or --runs-dir is required"
        raise typer.BadParameter(message)
    output_root = require_external_path(Path(configured_root), Path.cwd())
    dataset = generate_synthetic(
        seed=loaded.synthetic.seed,
        rows=loaded.synthetic.rows,
    )
    run_path = write_synthetic_artifacts(dataset, output_root)
    typer.echo(
        f"synthetic rows={dataset.operations.height} artifacts={run_path}",
    )


@app.command()
def plan_download(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
    scope: Annotated[
        DownloadScope,
        OptionInfo(default=...),
    ] = DownloadScope.FULL_RELEASE,
) -> None:
    """Build a host-locked plan from a local authenticated inventory."""
    loaded = load_config(config, repository_root=Path.cwd())
    raw_root = _raw_root(loaded)
    inventory = load_inventory(str(raw_root / "inventory.json"))
    require_release(inventory.release, loaded.release)
    plan = _scope_plan(build_download_plan(inventory), scope)
    _write_atomic(raw_root / "download-plan.json", plan.model_dump_json(indent=2))
    total_bytes = sum(entry.size_bytes for entry in plan.entries)
    typer.echo(f"scope={scope} files={len(plan.entries)} bytes={total_bytes}")


@app.command()
def download_data(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
    scope: Annotated[
        DownloadScope,
        OptionInfo(default=...),
    ] = DownloadScope.FULL_RELEASE,
) -> None:
    """Interactively download a validated plan with resumable transfers."""
    loaded = load_config(config, repository_root=Path.cwd())
    raw_root = _raw_root(loaded)
    plan = _scope_plan(_load_plan(raw_root / "download-plan.json"), scope)
    require_release(plan.release, loaded.release)
    username = typer.prompt("PhysioNet username")
    password = typer.prompt("PhysioNet password", hide_input=True)
    anyio.run(_download_plan, plan, raw_root, username, password)
    typer.echo(f"downloaded files={len(plan.entries)}")


@app.command()
def verify_data(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
) -> None:
    """Verify planned local files and write a provenance manifest."""
    loaded = load_config(config, repository_root=Path.cwd())
    raw_root = _raw_root(loaded)
    plan = _load_plan(raw_root / "download-plan.json")
    require_release(plan.release, loaded.release)
    verified = verify_downloads(plan, raw_root, raw_root / "quarantine")
    _write_atomic(
        raw_root / "verification-manifest.json",
        plan.model_dump_json(indent=2),
    )
    typer.echo(f"verified files={len(verified)}")


@app.command()
def prepare_data(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
) -> None:
    """Convert researcher-mapped verified tables to derived Parquet."""
    loaded = load_config(config, repository_root=Path.cwd())
    raw_root = _raw_root(loaded)
    work_root = _work_root(loaded)
    manifest = _load_plan(raw_root / "verification-manifest.json")
    require_release(manifest.release, loaded.release)
    mappings = TypeAdapter(tuple[TableMapping, ...]).validate_json(
        (work_root / "table-mappings.json").read_text(encoding="utf-8")
    )
    require_verified_mappings(mappings, manifest)
    outputs = prepare_mapped_tables(mappings, raw_root, work_root / "derived")
    typer.echo(f"prepared tables={len(outputs)}")


@app.command()
def audit_data(
    config: Annotated[
        Path,
        OptionInfo(default=..., exists=True, dir_okay=False),
    ],
) -> None:
    """Write a capability report derived only from explicit evidence."""
    loaded = load_config(config, repository_root=Path.cwd())
    work_root = _work_root(loaded)
    if loaded.data_kind is DataKind.SYNTHETIC:
        evidence = AuditEvidence(data_kind=DataKind.SYNTHETIC)
    else:
        evidence = AuditEvidence.model_validate_json(
            (work_root / "audit-evidence.json").read_text(encoding="utf-8")
        )
    require_data_kind(evidence.data_kind, loaded.data_kind)
    report = audit_capabilities(evidence)
    _write_atomic(work_root / "audit-report.json", report.model_dump_json(indent=2))
    typer.echo(report.model_dump_json())
