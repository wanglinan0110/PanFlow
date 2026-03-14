"""PanFlow 主流程编排。

这里负责把 companion 渲染、JSON renderer 渲染、pandoc 调用和 docx 后处理串起来。
"""

from __future__ import annotations

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from panflow_service.config import ProjectConfig
from panflow_service.converter import render_markdown_document
from panflow_service.document_processor import (
    discover_companion_document,
    has_companion_processor,
    render_with_companion_processor,
)
from panflow_service.docx_postprocess import apply_html_table_styles_to_docx
from panflow_service.pandoc import run_pandoc
from panflow_service.registry import RendererRegistry


def render_markdown_file(
    input_path: Path,
    output_path: Path,
    config: ProjectConfig,
) -> Path:
    # render 子命令只输出中间结果，不生成 docx。
    companion = discover_companion_document(input_path)
    if has_companion_processor(companion, config.project_root):
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

    markdown = input_path.read_text(encoding="utf-8")
    registry = RendererRegistry(config.renderers)
    rendered = render_markdown_document(markdown, registry, source_path=input_path).markdown
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def convert_markdown_file(
    input_path: Path,
    output_path: Path,
    config: ProjectConfig,
    *,
    intermediate_output: Path | None = None,
    reference_doc: Path | None = None,
) -> Path:
    # convert 是完整链路入口：先判断是否走 companion，再决定是否进 JSON renderer。
    companion = discover_companion_document(input_path)
    if has_companion_processor(companion, config.project_root):
        return _convert_with_companion_processor(
            companion,
            output_path=output_path,
            config=config,
            intermediate_output=intermediate_output,
            cli_reference_doc=reference_doc,
        )

    markdown = input_path.read_text(encoding="utf-8")
    registry = RendererRegistry(config.renderers)
    render_result = render_markdown_document(markdown, registry, source_path=input_path)

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        if intermediate_output is not None:
            # 用户要求保留中间产物时，直接把渲染后的 markdown 落盘复用。
            intermediate_output.parent.mkdir(parents=True, exist_ok=True)
            intermediate_output.write_text(render_result.markdown, encoding="utf-8")
            rendered_markdown_path = intermediate_output
        else:
            # 默认只在临时目录保存中间 markdown，避免污染工作区。
            rendered_markdown_path = temp_root / f"{input_path.stem}.rendered.md"
            rendered_markdown_path.write_text(render_result.markdown, encoding="utf-8")

        prepared_reference_doc = _prepare_reference_doc(
            reference_doc or config.pandoc.reference_doc,
            registry=registry,
            block_records=render_result.blocks,
            project_root=config.project_root,
            source_path=input_path,
            output_path=output_path,
            temp_root=temp_root,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_pandoc(
            rendered_markdown_path,
            output_path,
            binary=config.pandoc.binary,
            reference_doc=prepared_reference_doc,
        )
        return output_path


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
        if result.input_format == "html":
            # pandoc 对复杂 HTML 表格的 CSS 支持不完整，这里把边框和单元格样式回填到 docx。
            apply_html_table_styles_to_docx(result.content, output_path)
        return output_path


def _prepare_reference_doc(
    base_reference_doc: Path | None,
    *,
    registry: RendererRegistry,
    block_records: list[dict[str, object]],
    project_root: Path,
    source_path: Path,
    output_path: Path,
    temp_root: Path,
) -> Path | None:
    # reference.docx 会先复制到临时目录，再允许 renderer 钩子按块修改。
    working_reference_doc = None
    if base_reference_doc is not None:
        # 先复制一份模板副本，避免脚本处理时改写原始 reference.docx。
        working_reference_doc = temp_root / base_reference_doc.name
        shutil.copy2(base_reference_doc, working_reference_doc)

    return registry.apply_template_hooks(
        working_reference_doc,
        block_records,
        {
            "project_root": str(project_root),
            "source_path": str(source_path),
            "output_path": str(output_path),
            "temp_dir": str(temp_root),
        },
    )
