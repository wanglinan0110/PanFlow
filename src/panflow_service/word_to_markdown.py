"""Word 反向转换链路。"""

from __future__ import annotations

from pathlib import Path
import subprocess

from panflow_service.config import ProjectConfig


def convert_word_to_markdown(
    input_path: Path,
    output_path: Path,
    config: ProjectConfig,
    *,
    html_output: Path | None = None,
) -> tuple[Path, Path]:
    """先把 docx 转成 HTML，再把 HTML 转成 Markdown。"""
    resolved_input = input_path.resolve()
    resolved_markdown = output_path.resolve()
    resolved_markdown.parent.mkdir(parents=True, exist_ok=True)
    resolved_html = (html_output or resolved_markdown.with_suffix(".html")).resolve()
    resolved_html.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            config.pandoc.binary,
            "--from",
            "docx",
            "--to",
            "html",
            str(resolved_input),
            "--output",
            str(resolved_html),
        ],
        check=True,
    )
    subprocess.run(
        [
            config.pandoc.binary,
            "--from",
            "html",
            "--to",
            "gfm-raw_html",
            str(resolved_html),
            "--output",
            str(resolved_markdown),
        ],
        check=True,
    )
    return resolved_html, resolved_markdown
