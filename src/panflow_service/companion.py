from __future__ import annotations

from html import escape


def build_document_result(
    content: str,
    *,
    template_style: str | None = None,
    reference_doc: str | None = None,
    font_family: str | None = None,
    font_size: str | None = None,
    input_format: str = "html",
) -> dict[str, str]:
    """Build a standard companion-processor result payload."""

    result: dict[str, str] = {
        "content": content,
        "input_format": input_format,
    }
    if template_style is not None:
        result["template_style"] = template_style
    if reference_doc is not None:
        result["reference_doc"] = reference_doc
    if font_family is not None:
        result["font_family"] = font_family
    if font_size is not None:
        result["font_size"] = font_size
    return result


def render_heading(
    text: str,
    *,
    level: int,
    font_family: str | None = None,
    font_size: str | None = None,
    font_weight: str | None = None,
    text_align: str | None = None,
    line_height: str | None = None,
) -> str:
    tag = f"h{level}"
    return render_html_block(
        tag,
        text,
        font_family=font_family,
        font_size=font_size,
        font_weight=font_weight,
        text_align=text_align,
        line_height=line_height,
    )


def render_html_block(
    tag: str,
    text: str,
    *,
    font_family: str | None = None,
    font_size: str | None = None,
    font_weight: str | None = None,
    text_align: str | None = None,
    line_height: str | None = None,
) -> str:
    style = build_inline_style(
        font_family=font_family,
        font_size=font_size,
        font_weight=font_weight,
        text_align=text_align,
        line_height=line_height,
    )
    style_attr = f' style="{style}"' if style else ""
    return f"<{tag}{style_attr}>{escape(text)}</{tag}>"


def build_inline_style(
    *,
    font_family: str | None = None,
    font_size: str | None = None,
    font_weight: str | None = None,
    text_align: str | None = None,
    line_height: str | None = None,
    vertical_align: str | None = None,
    border: str | None = None,
    border_top: str | None = None,
    border_right: str | None = None,
    border_bottom: str | None = None,
    border_left: str | None = None,
    padding: str | None = None,
    width: str | None = None,
    border_collapse: str | None = None,
    table_layout: str | None = None,
    background_color: str | None = None,
) -> str:
    styles: list[str] = []
    if font_family:
        styles.append(f"font-family: {font_family};")
    if font_size:
        styles.append(f"font-size: {font_size};")
    if font_weight:
        styles.append(f"font-weight: {font_weight};")
    if text_align:
        styles.append(f"text-align: {text_align};")
    if line_height:
        styles.append(f"line-height: {line_height};")
    if vertical_align:
        styles.append(f"vertical-align: {vertical_align};")
    if border:
        styles.append(f"border: {border};")
    if border_top:
        styles.append(f"border-top: {border_top};")
    if border_right:
        styles.append(f"border-right: {border_right};")
    if border_bottom:
        styles.append(f"border-bottom: {border_bottom};")
    if border_left:
        styles.append(f"border-left: {border_left};")
    if padding:
        styles.append(f"padding: {padding};")
    if width:
        styles.append(f"width: {width};")
    if border_collapse:
        styles.append(f"border-collapse: {border_collapse};")
    if table_layout:
        styles.append(f"table-layout: {table_layout};")
    if background_color:
        styles.append(f"background-color: {background_color};")
    return " ".join(styles)
