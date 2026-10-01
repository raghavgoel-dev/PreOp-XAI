"""Privacy and external-path guards."""

from pathlib import Path
from re import IGNORECASE
from re import compile as compile_pattern

_CREDENTIAL_PATTERN = compile_pattern(
    r"(?:authorization\s*:\s*bearer|password\s*=|api[_-]?key\s*=)",
    IGNORECASE,
)


def require_external_path(path: Path, repository_root: Path) -> Path:
    """Return a resolved path only when it is external and not a placeholder."""
    raw = str(path)
    if any(marker in raw for marker in ("<", ">", "${", "}")):
        message = "Path contains a placeholder instead of a live external path"
        raise ValueError(message)
    resolved_path = path.expanduser().resolve()
    resolved_root = repository_root.resolve()
    if resolved_path == resolved_root or resolved_root in resolved_path.parents:
        message = "Path must be external to the repository"
        raise ValueError(message)
    return resolved_path


def require_safe_text(value: str) -> str:
    """Reject credential-like text before it reaches output or logs."""
    if _CREDENTIAL_PATTERN.search(value) is not None:
        message = "Text contains credential-like material"
        raise ValueError(message)
    return value
