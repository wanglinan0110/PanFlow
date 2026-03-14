"""PyInstaller 打包脚本。

负责把 CLI、模板资源以及可选的 pandoc 一起封装成可分发应用。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    # 打包只暴露三个核心维度：应用名、打包模式、是否内置 pandoc。
    parser = argparse.ArgumentParser(description="Build a standalone PanFlow application with PyInstaller.")
    parser.add_argument("--name", default="PanFlow", help="Application name. Default: PanFlow.")
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
    examples_dir = project_root / "examples"
    templates_dir = project_root / "templates"
    pyinstaller = _resolve_pyinstaller()

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
        str(project_root / "dist"),
        "--workpath",
        str(project_root / "build" / "pyinstaller"),
        "--specpath",
        str(project_root / "build" / "pyinstaller"),
        "--add-data",
        _add_data_arg(examples_dir, "examples"),
        "--add-data",
        _add_data_arg(templates_dir, "templates"),
        str(entry_script),
    ]

    if args.pandoc_binary is not None:
        # 如果显式传入 pandoc，就把它放到应用内置的 bin/ 目录里。
        command.extend(
            [
                "--add-binary",
                _add_data_arg(args.pandoc_binary.resolve(), f"bin/{args.pandoc_binary.name}"),
            ],
        )

    subprocess.run(command, check=True)
    target = _target_path(project_root, args.name, args.mode)
    print(f"Built application at {target}")
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


def _target_path(project_root: Path, name: str, mode: str) -> Path:
    # onefile 模式输出单文件，onedir 模式输出目录。
    dist_dir = project_root / "dist"
    if mode == "onefile":
        suffix = ".exe" if sys.platform.startswith("win") else ""
        return dist_dir / f"{name}{suffix}"
    return dist_dir / name


if __name__ == "__main__":
    raise SystemExit(main())
