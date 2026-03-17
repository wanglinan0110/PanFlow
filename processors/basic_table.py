"""普通二维表渲染脚本。"""

from __future__ import annotations

from html import escape
from typing import Any


def render_table(
    payload: dict[str, Any],
    *,
    table_index: int,
    block_index: int,
    context: dict[str, object],
) -> str:
    """把 keys + values 结构渲染成普通表格。"""
    columns = _resolve_columns(payload)
    rows = payload.get("values", [])
    if not isinstance(rows, list):
        raise ValueError(f"json:basic_table block #{block_index} 'values' must be a list.")

    header_html = (
        '<th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">序号</th>'
        + "".join(
        f'<th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{escape(description)}</th>'
        for _, description in columns
        )
    )
    body_rows = rows or [{}]
    body_html = "".join(
        "<tr>"
        + f'<td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{row_index}</td>'
        + "".join(
            f'<td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;">'
            f'{_render_cell_text(row, name)}'
            "</td>"
            for name, _ in columns
        )
        + "</tr>"
        for row_index, row in enumerate(body_rows, start=1)
    )

    return (
        f'<table id="design-doc-table-{table_index}" class="pf-table pf-design-doc-table pf-design-doc-normal-type" '
        'data-json-block-type="basic_table" '
        'style="width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #000000;">\n'
        "  <thead>\n"
        "    <tr>"
        f"{header_html}"
        "</tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{body_html}\n"
        "  </tbody>\n"
        "</table>"
    )


def _resolve_columns(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """从 keys 配置中提取列名和表头文案。"""
    keys = payload.get("keys", [])
    if not isinstance(keys, list):
        raise ValueError("json:basic_table 'keys' must be a list.")

    columns: list[tuple[str, str]] = []
    for item in keys:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        description = str(item.get("description", name)).strip() or name
        columns.append((name, description))
    if not columns:
        raise ValueError("json:basic_table must define at least one column in 'keys'.")
    return columns


def _render_cell_text(row: object, name: str) -> str:
    """读取普通单元格文本，并处理换行。"""
    if not isinstance(row, dict):
        return ""
    return escape(str(row.get(name, ""))).replace("\n", "<br />")
