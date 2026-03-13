from __future__ import annotations

from pathlib import Path
import sys


def resolve_examples_dir(project_root: Path) -> Path:
    return _first_existing_path(
        [
            project_root / "examples",
            _bundle_root() / "examples" if _bundle_root() is not None else None,
            _source_checkout_root() / "examples",
        ],
    )


def resolve_renderers_dir(project_root: Path) -> Path:
    return _first_existing_path(
        [
            project_root / "src" / "panflow_service" / "renderers",
            _bundle_root() / "renderers" if _bundle_root() is not None else None,
            _package_dir() / "renderers",
        ],
    )


def resolve_reference_doc(project_root: Path) -> Path | None:
    candidates = [
        project_root / "templates" / "reference.docx",
        _bundle_root() / "templates" / "reference.docx" if _bundle_root() is not None else None,
        _source_checkout_root() / "templates" / "reference.docx",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate.resolve()
    return None


def resolve_pandoc_binary(project_root: Path) -> str:
    candidates = [
        project_root / "bin" / _pandoc_filename(),
        _bundle_root() / "bin" / _pandoc_filename() if _bundle_root() is not None else None,
        _source_checkout_root() / "bin" / _pandoc_filename(),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return str(candidate.resolve())
    return "pandoc"


def _first_existing_path(candidates: list[Path | None]) -> Path:
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate.resolve()
    for candidate in candidates:
        if candidate is not None:
            return candidate.resolve()
    raise RuntimeError("No runtime path candidates were provided.")


def _bundle_root() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is None:
        return None
    return Path(str(bundle_root)).resolve()


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _source_checkout_root() -> Path:
    return _package_dir().parents[2]


def _pandoc_filename() -> str:
    return "pandoc.exe" if sys.platform.startswith("win") else "pandoc"
