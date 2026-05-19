"""Shared filesystem defaults for package CLIs."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent


def default_trace_dir() -> Path:
    return PACKAGE_ROOT / "data" / "traces"


def resolve_output_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return Path.cwd() / path
