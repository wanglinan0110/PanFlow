"""PanFlow 主流程编排。

这里负责把 companion 模板渲染、pandoc 调用和 docx 后处理串起来。
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from panflow_service.config import ProjectConfig
from panflow_service.document_processor import (
    discover_companion_document,
    render_with_companion_processor,
)
from panflow_service.docx_postprocess import apply_html_table_styles_to_docx
from panflow_service.pandoc import run_pandoc


def render_markdown_file(
    input_path: Path,
    output_path: Path,
    config: ProjectConfig,
) -> Path:
    # render 子命令只输出中间结果，不生成 docx。
    companion = discover_companion_document(input_path)
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        result = render_with_companion_processor(
            companion,
            cli_reference_doc=None,
            project_root=config.project_root,
            output_path=output_path,
            temp_dir=temp_root,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.content, encoding="utf-8")
        return output_path


def convert_markdown_file(
    input_path: Path,
    output_path: Path,
    config: ProjectConfig,
    *,
    intermediate_output: Path | None = None,
    reference_doc: Path | None = None,
) -> Path:
    # convert 是完整链路入口：当前只支持按 template_style 分 section 的 companion 模式。
    companion = discover_companion_document(input_path)
    return _convert_with_companion_processor(
        companion,
        output_path=output_path,
        config=config,
        intermediate_output=intermediate_output,
        cli_reference_doc=reference_doc,
    )


def _convert_with_companion_processor(
    companion,
    *,
    output_path: Path,
    config: ProjectConfig,
    intermediate_output: Path | None,
    cli_reference_doc: Path | None,
) -> Path:
    # companion 模式下，中间产物可能是 HTML，也可能是 gfm+raw_html。
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        result = render_with_companion_processor(
            companion,
            cli_reference_doc=cli_reference_doc,
            project_root=config.project_root,
            output_path=output_path,
            temp_dir=temp_root,
        )

        if intermediate_output is not None:
            intermediate_output.parent.mkdir(parents=True, exist_ok=True)
            intermediate_output.write_text(result.content, encoding="utf-8")
            rendered_input_path = intermediate_output
        else:
            suffix = ".html" if result.input_format == "html" else ".md"
            rendered_input_path = temp_root / f"{companion.markdown_path.stem}.rendered{suffix}"
            rendered_input_path.write_text(result.content, encoding="utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_pandoc(
            rendered_input_path,
            output_path,
            binary=config.pandoc.binary,
            input_format=result.input_format,
            reference_doc=result.reference_doc or config.pandoc.reference_doc,
        )
        if result.input_format == "html" and output_path.exists():
            # pandoc 对复杂 HTML 表格的 CSS 支持不完整，这里把边框和单元格样式回填到 docx。
            apply_html_table_styles_to_docx(result.content, output_path)
        return output_path
