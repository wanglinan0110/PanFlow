RENDER_KEYS = ["1", "table", "testcase_table", "json_table"]


from html import escape
from pathlib import Path
from typing import Any

from panflow_service.companion import build_inline_style


def render(payload: Any, context: dict[str, object]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("testcase_table renderer expects a JSON object.")

    colgroup = payload.get("colgroup", [])
    rows = payload.get("rows", [])
    if not isinstance(colgroup, list):
        raise ValueError("colgroup must be a list.")
    if not isinstance(rows, list):
        raise ValueError("rows must be a list.")

    table_style = payload.get("table_style", {})
    if table_style is not None and not isinstance(table_style, dict):
        raise ValueError("table_style must be an object when provided.")

    colgroup_html = _render_colgroup(colgroup)
    body_rows = "\n".join(_render_row(row, table_style) for row in rows)
    # block_index 用来生成稳定且可追踪的表格 id。
    table_id = f"table-{context['block_index']}"
    table_style_attr = _render_table_style_attr(table_style)
    return (
        f'<table id="{table_id}" class="pf-table pf-testcase-table"{table_style_attr}>\n'
        f"{colgroup_html}"
        "  <tbody>\n"
        f"{body_rows}\n"
        "  </tbody>\n"
        "</table>"
    )


def _render_colgroup(colgroup: list[Any]) -> str:
    if not colgroup:
        return ""

    cols = []
    for width in colgroup:
        width_text = escape(str(width))
        cols.append(f'    <col style="width: {width_text};" />')
    return "  <colgroup>\n" + "\n".join(cols) + "\n  </colgroup>\n"


def _render_row(row: Any, table_style: dict[str, Any]) -> str:
    if not isinstance(row, list):
        raise ValueError("Each row must be a list.")

    cells = "\n".join(_render_cell(cell, table_style) for cell in row)
    return f"    <tr>\n{cells}\n    </tr>"


def _render_cell(cell: Any, table_style: dict[str, Any]) -> str:
    if not isinstance(cell, dict):
        raise ValueError("Each cell must be an object.")

    text = escape(str(cell.get("text", ""))).replace("\n", "<br />")
    text_align = _pick_style_value(cell, table_style, "text_align")
    if text_align is None:
        text_align = str(cell.get("align", "left"))
    colspan = int(cell.get("colspan", 1))
    rowspan = int(cell.get("rowspan", 1))
    bold = bool(cell.get("bold", False))

    inline_style = build_inline_style(
        font_family=_pick_style_value(cell, table_style, "font_family"),
        font_size=_pick_style_value(cell, table_style, "font_size"),
        font_weight=_pick_style_value(cell, table_style, "font_weight") or ("700" if bold else None),
        text_align=text_align,
        line_height=_pick_style_value(cell, table_style, "line_height"),
        vertical_align=_pick_style_value(cell, table_style, "vertical_align"),
        border=_pick_style_value(cell, table_style, "border"),
        border_top=_pick_style_value(cell, table_style, "border_top"),
        border_right=_pick_style_value(cell, table_style, "border_right"),
        border_bottom=_pick_style_value(cell, table_style, "border_bottom"),
        border_left=_pick_style_value(cell, table_style, "border_left"),
        padding=_pick_style_value(cell, table_style, "padding"),
        background_color=_pick_style_value(cell, table_style, "background_color"),
    )
    attrs = [f'style="{inline_style}"'] if inline_style else []
    if colspan > 1:
        attrs.append(f'colspan="{colspan}"')
    if rowspan > 1:
        attrs.append(f'rowspan="{rowspan}"')

    # 统一输出 td，避免 pandoc/Word 因 th 触发表头样式而覆盖业务脚本里的样式。
    content = f"<strong>{text}</strong>" if bold else text
    return f"      <td {' '.join(attrs)}>{content}</td>"


def _render_table_style_attr(table_style: dict[str, Any]) -> str:
    inline_style = build_inline_style(
        font_family=str(table_style["font_family"]) if "font_family" in table_style else None,
        font_size=str(table_style["font_size"]) if "font_size" in table_style else None,
        line_height=str(table_style["line_height"]) if "line_height" in table_style else None,
        border=str(table_style["border"]) if "border" in table_style else None,
        border_top=str(table_style["border_top"]) if "border_top" in table_style else None,
        border_right=str(table_style["border_right"]) if "border_right" in table_style else None,
        border_bottom=str(table_style["border_bottom"]) if "border_bottom" in table_style else None,
        border_left=str(table_style["border_left"]) if "border_left" in table_style else None,
        width=str(table_style["width"]) if "width" in table_style else None,
        border_collapse=str(table_style["border_collapse"]) if "border_collapse" in table_style else None,
        table_layout=str(table_style["table_layout"]) if "table_layout" in table_style else None,
        background_color=str(table_style["background_color"]) if "background_color" in table_style else None,
    )
    if not inline_style:
        return ""
    return f' style="{inline_style}"'


def _pick_style_value(
    cell: dict[str, Any],
    table_style: dict[str, Any],
    key: str,
) -> str | None:
    if key in cell and cell[key] is not None:
        return str(cell[key])
    if key in table_style and table_style[key] is not None:
        return str(table_style[key])
    return None


def prepare_reference_doc(
    reference_doc: Path | None,
    blocks: list[dict[str, object]],
    context: dict[str, object],
) -> Path | None:
    # 业务表格类块允许绑定专用模板；若工程提供了该模板，则优先切换过去。
    project_root = Path(str(context["project_root"]))
    preferred_template = project_root / "templates" / "testcase-table-reference.docx"
    if preferred_template.exists():
        return preferred_template

    return reference_doc
