"""运行时资源定位。

这层逻辑用于兼容三种场景：源码运行、安装后运行、PyInstaller 打包后运行。
"""

from __future__ import annotations

from pathlib import Path
import sys


def resolve_examples_dir(project_root: Path) -> Path:
    # 优先使用当前工程目录；打包后再回退到应用内资源。
    return _first_existing_path(
        [
            project_root / "examples",
            _bundle_root() / "examples" if _bundle_root() is not None else None,
            _source_checkout_root() / "examples",
        ],
    )


def resolve_renderers_dir(project_root: Path) -> Path:
    # renderers 在源码模式和打包模式下目录位置不同，这里统一兜底。
    return _first_existing_path(
        [
            project_root / "src" / "panflow_service" / "renderers",
            _bundle_root() / "renderers" if _bundle_root() is not None else None,
            _package_dir() / "renderers",
        ],
    )


def resolve_reference_doc(project_root: Path) -> Path | None:
    # reference.docx 允许来自工程目录、打包资源或源码 checkout。
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
    # 如果应用内打包了 pandoc，就优先走内置二进制；否则退回系统 pandoc。
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
    # 先返回真实存在的路径；如果都不存在，至少返回第一个候选路径供上层报错。
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate.resolve()
    for candidate in candidates:
        if candidate is not None:
            return candidate.resolve()
    raise RuntimeError("No runtime path candidates were provided.")


def _bundle_root() -> Path | None:
    # PyInstaller 运行时会通过 _MEIPASS 暴露临时解包目录。
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
