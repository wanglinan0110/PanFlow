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
        raise ValueError(f"json:normal_type block #{block_index} 'values' must be a list.")

    header_html = "".join(
        f'<th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{escape(description)}</th>'
        for _, description in columns
    )
    body_rows = rows or [{}]
    body_html = "".join(
        "<tr>"
        + "".join(
            f'<td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;">'
            f'{escape("" if not isinstance(row, dict) else str(row.get(name, ""))).replace("\n", "<br />")}'
            "</td>"
            for name, _ in columns
        )
        + "</tr>"
        for row in body_rows
    )

    return (
        f'<table id="design-doc-table-{table_index}" class="pf-table pf-design-doc-table pf-design-doc-normal-type" '
        'data-json-block-type="normal_type" '
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
        raise ValueError("json:normal_type 'keys' must be a list.")

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
        raise ValueError("json:normal_type must define at least one column in 'keys'.")
    return columns
