from __future__ import annotations

from pathlib import Path
import subprocess


class PandocExecutionError(RuntimeError):
    """Raised when pandoc execution fails."""


def build_pandoc_command(
    input_path: Path,
    output_path: Path,
    *,
    binary: str = "pandoc",
    input_format: str = "gfm+raw_html",
    reference_doc: Path | None = None,
) -> list[str]:
    # 启用 raw_html，让前一步生成的 HTML 表格能被 pandoc 正常消费。
    command = [
        binary,
        str(input_path),
        "--from",
        input_format,
        "--to",
        "docx",
        "--output",
        str(output_path),
    ]
    if reference_doc is not None:
        command.extend(["--reference-doc", str(reference_doc)])
    return command


def run_pandoc(
    input_path: Path,
    output_path: Path,
    *,
    binary: str = "pandoc",
    input_format: str = "gfm+raw_html",
    reference_doc: Path | None = None,
) -> None:
    command = build_pandoc_command(
        input_path,
        output_path,
        binary=binary,
        input_format=input_format,
        reference_doc=reference_doc,
    )
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PandocExecutionError(
            f"Pandoc binary '{binary}' was not found. Install pandoc or override [pandoc].binary in panflow.toml.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise PandocExecutionError(
            f"Pandoc failed with exit code {exc.returncode}: {exc.stderr.strip()}",
        ) from exc
