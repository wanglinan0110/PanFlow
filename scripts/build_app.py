"""PyInstaller 打包脚本。

负责把 CLI、模板资源以及可选的 pandoc 一起封装成可分发应用。
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
import subprocess
import sys

DEFAULT_LOGS_DIR = "logs"
DEFAULT_RELEASE_CONFIG_FILE = "config.json"


def build_parser() -> argparse.ArgumentParser:
    # 打包只暴露三个核心维度：应用名、打包模式、是否内置 pandoc。
    parser = argparse.ArgumentParser(description="Build a standalone PanFlow application with PyInstaller.")
    parser.add_argument("--name", default="PanFlow", help="Application name. Default: PanFlow.")
    parser.add_argument(
        "--release-dir-name",
        help="Output release directory name. Default: <name>_Release.",
    )
    parser.add_argument(
        "--mode",
        choices=["onedir", "onefile"],
        default="onedir",
        help="PyInstaller bundle mode. Default: onedir.",
    )
    parser.add_argument(
        "--pandoc-binary",
        type=Path,
        help="Optional path to a local pandoc binary to bundle into the app.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    entry_script = project_root / "run_panflow.py"
    processors_dir = project_root / "processors"
    templates_dir = project_root / "templates"
    pyinstaller_dist_dir = project_root / "dist" / "_pyinstaller"
    pyinstaller = _resolve_pyinstaller()
    release_dir_name = args.release_dir_name or f"{args.name}_Release"

    # 统一在这里拼装 PyInstaller 命令，确保源码资源和运行时资源一起打包。
    command = [
        sys.executable,
        "-m",
        pyinstaller,
        "--noconfirm",
        "--clean",
        f"--{args.mode}",
        "--name",
        args.name,
        "--distpath",
        str(pyinstaller_dist_dir),
        "--workpath",
        str(project_root / "build" / "pyinstaller"),
        "--specpath",
        str(project_root / "build" / "pyinstaller"),
        "--add-data",
        _add_data_arg(processors_dir, "processors"),
        "--add-data",
        _add_data_arg(templates_dir, "templates"),
        str(entry_script),
    ]

    if args.mode == "onedir":
        # onedir 模式固定把运行依赖收进 _internal，便于发布目录保持清晰。
        command.extend(["--contents-directory", "_internal"])

    if args.pandoc_binary is not None:
        # 如果显式传入 pandoc，就把它放到应用内置的 bin/ 目录里。
        command.extend(
            [
                "--add-binary",
                _add_data_arg(args.pandoc_binary.resolve(), f"bin/{args.pandoc_binary.name}"),
            ],
        )

    subprocess.run(command, check=True)
    target = _target_path(pyinstaller_dist_dir, args.name, args.mode)
    release_dir = _finalize_release_layout(
        project_root,
        target=target,
        release_dir_name=release_dir_name,
        mode=args.mode,
    )
    shutil.rmtree(pyinstaller_dist_dir, ignore_errors=True)
    print(f"Built application at {release_dir}")
    return 0


def _resolve_pyinstaller() -> str:
    try:
        import PyInstaller  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyInstaller is not installed. Run 'python3 -m pip install pyinstaller' first, "
            "or add it to your build environment before packaging.",
        ) from exc
    return "PyInstaller"


def _add_data_arg(source: Path, target: str) -> str:
    # PyInstaller 在 Windows 和 POSIX 上的数据参数分隔符不同。
    separator = ";" if sys.platform.startswith("win") else ":"
    return f"{source}{separator}{target}"


def _target_path(dist_root: Path, name: str, mode: str) -> Path:
    # onefile 模式输出单文件，onedir 模式输出目录。
    if mode == "onefile":
        suffix = ".exe" if sys.platform.startswith("win") else ""
        return dist_root / f"{name}{suffix}"
    return dist_root / name


def _finalize_release_layout(project_root: Path, *, target: Path, release_dir_name: str, mode: str) -> Path:
    # 发布目录统一收口成：exe / config.json / _internal(onedir) / logs。
    release_dir = (project_root / "dist" / release_dir_name).resolve()
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.parent.mkdir(parents=True, exist_ok=True)

    if mode == "onedir":
        shutil.move(str(target), str(release_dir))
    else:
        release_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(release_dir / target.name))

    _copy_release_config(project_root, release_dir)
    (release_dir / DEFAULT_LOGS_DIR).mkdir(exist_ok=True)
    return release_dir


def _copy_release_config(project_root: Path, release_dir: Path) -> None:
    # 外部 config.json 给 design_doc 这类脚本做映射表，记事本直接可改。
    source_config = project_root / DEFAULT_RELEASE_CONFIG_FILE
    if source_config.exists():
        shutil.copy2(source_config, release_dir / DEFAULT_RELEASE_CONFIG_FILE)


if __name__ == "__main__":
    raise SystemExit(main())
