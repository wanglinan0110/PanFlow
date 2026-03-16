"""design_doc Markdown 的 JSON 表格分发脚本。"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from html import escape
import json
from pathlib import Path
import re
from types import ModuleType
from typing import Any, Callable

from panflow_service.companion import build_document_result

TEMPLATE_STYLE = "design_doc"
BODY_INDENT = "\u00A0" * 4
FENCE_START_PATTERN = re.compile(r"```json:([A-Za-z0-9_]+)")
CENTER_TAG_PATTERN = re.compile(r"<text-center>(.*?)</text-center>")
CENTER_PREFIX_PATTERN = re.compile(r"^\s*text-center(?:\s+|:\s*)")

_MODULE_CACHE: dict[Path, ModuleType] = {}


def render_document(
    markdown: str,
    metadata: dict[str, object],
    config: dict[str, object],
    context: dict[str, object],
) -> dict[str, str]:
    """把 design_doc.md 中的 json:表格类型 代码块替换成对应 HTML 表格。"""
    output_lines, table_placeholders = _replace_json_blocks_with_placeholders(markdown, context)
    content = _render_markdown_lines_as_html(output_lines, table_placeholders).rstrip() + "\n"
    return build_document_result(content, input_format="html", template_style=TEMPLATE_STYLE)


def _replace_json_blocks_with_placeholders(
    markdown: str,
    context: dict[str, object],
) -> tuple[list[str], dict[str, str]]:
    """扫描 Markdown，把 json:类型 代码块替换成 HTML 表格占位符。"""
    lines = markdown.splitlines()
    output_lines: list[str] = []
    table_placeholders: dict[str, str] = {}
    block_index = 0
    table_index = 0
    line_index = 0

    while line_index < len(lines):
        block_type = _match_json_block_type(lines[line_index])
        if block_type is None:
            output_lines.append(lines[line_index])
            line_index += 1
            continue

        block_index += 1
        table_index += 1
        line_index, table_html = _render_json_block_as_table(
            lines,
            start_index=line_index,
            block_type=block_type,
            block_index=block_index,
            table_index=table_index,
            context=context,
        )
        placeholder = f"__DESIGN_DOC_TABLE_{table_index}__"
        table_placeholders[placeholder] = table_html
        output_lines.extend(["", placeholder, ""])

    return output_lines, table_placeholders


def _match_json_block_type(line: str) -> str | None:
    """判断当前行是否是 json:类型 代码块的起始行。"""
    start_match = FENCE_START_PATTERN.fullmatch(line.strip())
    if start_match is None:
        return None
    return start_match.group(1)


def _render_json_block_as_table(
    lines: list[str],
    *,
    start_index: int,
    block_type: str,
    block_index: int,
    table_index: int,
    context: dict[str, object],
) -> tuple[int, str]:
    """读取一个完整 json 代码块，并调用对应脚本输出 HTML 表格。"""
    line_index = start_index + 1
    block_lines: list[str] = []

    while line_index < len(lines) and lines[line_index].strip() != "```":
        block_lines.append(lines[line_index])
        line_index += 1
    if line_index >= len(lines):
        raise ValueError(f"Unclosed json code fence for block type '{block_type}'.")

    payload = _parse_loose_json("\n".join(block_lines), block_type=block_type, block_index=block_index)
    render_table = _load_renderer(block_type)
    table_html = render_table(
        payload,
        table_index=table_index,
        block_index=block_index,
        context=context,
    )
    return line_index + 1, table_html


def _parse_loose_json(raw_text: str, *, block_type: str, block_index: int) -> dict[str, Any]:
    """把接近 JSON 的代码块尽量整理成真正可解析的 JSON。"""
    normalized = raw_text.strip()
    normalized = re.sub(r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', normalized)
    normalized = re.sub(r"}\s*{", "},{", normalized)
    normalized = re.sub(
        r'(["0-9}\]])(\s*)(?=("([^"\\]|\\.)*"|[A-Za-z_][A-Za-z0-9_]*)\s*:)',
        r"\1,\2",
        normalized,
    )
    normalized = re.sub(r'\],\s*\}\],\s*(?="values"\s*:)', "], ", normalized)
    normalized = re.sub(r",\s*([}\]])", r"\1", normalized)

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Unable to parse json:{block_type} block #{block_index}: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(f"json:{block_type} block #{block_index} must parse to an object.")
    return payload


def _load_renderer(block_type: str) -> Callable[..., str]:
    """按 json:表格类型 查找对应的 Python 脚本并返回渲染函数。"""
    script_path = _resolve_renderer_path(block_type)
    module = _MODULE_CACHE.get(script_path)
    if module is None:
        spec = spec_from_file_location(f"panflow_design_doc_{script_path.stem}", script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load renderer script '{script_path.name}'.")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[script_path] = module

    render_table = getattr(module, "render_table", None)
    if not callable(render_table):
        raise RuntimeError(f"Renderer script '{script_path.name}' must expose render_table(payload, ...).")
    return render_table


def _resolve_renderer_path(block_type: str) -> Path:
    """根据 json:类型 按命名约定查找同目录下的渲染脚本。"""
    script_path = Path(__file__).with_name(f"{TEMPLATE_STYLE}_{block_type}.py").resolve()
    if script_path.exists():
        return script_path

    current_prefix = f"{TEMPLATE_STYLE}_"
    supported = sorted(
        path.stem.removeprefix(current_prefix)
        for path in Path(__file__).parent.glob(f"{current_prefix}*.py")
        if path.stem != Path(__file__).stem
    )
    supported_text = ", ".join(supported) if supported else "none"
    raise ValueError(f"Unsupported json table type '{block_type}'. Supported types: {supported_text}.")


def _render_markdown_lines_as_html(lines: list[str], table_placeholders: dict[str, str]) -> str:
    """把 design_doc 的普通 Markdown 文本渲染成纯 HTML，并内联替换表格占位符。"""
    html_parts: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        paragraph_html = _render_paragraph_lines(paragraph_buffer)
        if paragraph_html:
            html_parts.append(paragraph_html)
        paragraph_buffer.clear()

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if stripped in table_placeholders:
            flush_paragraph()
            html_parts.append(table_placeholders[stripped])
            continue
        heading_html = _render_heading_line(stripped)
        if heading_html is not None:
            flush_paragraph()
            html_parts.append(heading_html)
            continue
        paragraph_buffer.append(line)

    flush_paragraph()
    return "\n".join(html_parts)


def _render_heading_line(stripped_line: str) -> str | None:
    """把 Markdown 标题行转成对应层级的 HTML 标题。"""
    if not stripped_line.startswith("#"):
        return None
    heading_match = re.fullmatch(r"(#{1,4})\s+(.*)", stripped_line)
    if heading_match is None:
        return None
    level = len(heading_match.group(1))
    title = _render_inline_text(heading_match.group(2))
    return f"<h{level}>{title}</h{level}>"


def _render_paragraph_lines(lines: list[str]) -> str:
    """把段落中的每一行独立输出，只保留正文默认缩进和居中控制。"""
    rendered_lines: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        content = _render_inline_text(_strip_control_tags(line).strip())
        indent_prefix = _build_body_indent_prefix(line)
        line_style = _build_line_style(line)
        style_attr = f' style="{line_style}"' if line_style else ""
        rendered_lines.append(f"<div{style_attr}>{indent_prefix}{content}</div>")
    if not rendered_lines:
        return ""
    return '<div class="pf-design-doc-paragraph">' + "".join(rendered_lines) + "</div>"


def _build_body_indent_prefix(text: str) -> str:
    """标题下方正文默认缩进 4 个空格。"""
    if _is_center_line(text):
        return ""
    return BODY_INDENT


def _build_line_style(text: str) -> str:
    """生成当前行的额外样式，例如居中。"""
    styles: list[str] = []
    if _is_center_line(text):
        styles.append("text-align: center;")
    return " ".join(styles)


def _is_center_line(text: str) -> bool:
    """判断当前行是否声明为居中显示。"""
    return CENTER_TAG_PATTERN.search(text) is not None or CENTER_PREFIX_PATTERN.match(text) is not None


def _strip_center_tags(text: str) -> str:
    """移除居中控制标记，仅保留正文内容。"""
    without_wrapped_tags = CENTER_TAG_PATTERN.sub(lambda match: match.group(1), text)
    return CENTER_PREFIX_PATTERN.sub("", without_wrapped_tags, count=1)


def _strip_control_tags(text: str) -> str:
    """统一移除当前仍支持的控制标记。"""
    return _strip_center_tags(text)


def _render_inline_text(text: str) -> str:
    """处理正文里的粗体等极少量内联 Markdown，输出安全的 HTML 文本。"""
    escaped = escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
