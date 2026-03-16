"""需求追踪矩阵渲染脚本。"""

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
    """把左右分组表头的追踪矩阵 JSON 渲染成 HTML 表格。"""
    columns = _resolve_columns(payload)
    rows = payload.get("values", [])
    if not isinstance(rows, list):
        raise ValueError(f"json:traceability_matrix block #{block_index} 'values' must be a list.")

    left_columns = [column for column in columns if column[2] == "header_left"]
    right_columns = [column for column in columns if column[2] == "header_right"]
    if not left_columns or not right_columns:
        raise ValueError("json:traceability_matrix must define both header_left and header_right columns.")

    top_header_html = (
        f'      <th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="{len(left_columns)}">'
        f'{escape(str(payload.get("header_left", "左侧分组")))}'
        "</th>\n"
        f'      <th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="{len(right_columns)}">'
        f'{escape(str(payload.get("header_right", "右侧分组")))}'
        "</th>"
    )
    second_header_html = "\n".join(
        f'      <th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{escape(description)}</th>'
        for _, description, _ in columns
    )
    body_html = "\n".join(
        "    <tr>\n"
        + "\n".join(
            '      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;">'
            f'{escape("" if not isinstance(row, dict) else str(row.get(name, ""))).replace("\n", "<br />")}</td>'
            for name, _, _ in columns
        )
        + "\n    </tr>"
        for row in (rows or [{}])
    )

    return (
        f'<table id="design-doc-table-{table_index}" class="pf-table pf-design-doc-table pf-design-doc-traceability-matrix" '
        'data-json-block-type="traceability_matrix" '
        'style="width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #000000;">\n'
        "  <thead>\n"
        "    <tr>\n"
        f"{top_header_html}\n"
        "    </tr>\n"
        "    <tr>\n"
        f"{second_header_html}\n"
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{body_html}\n"
        "  </tbody>\n"
        "</table>"
    )


def _resolve_columns(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """读取列定义并保留左右分组信息。"""
    keys = payload.get("keys", [])
    if not isinstance(keys, list):
        raise ValueError("json:traceability_matrix 'keys' must be a list.")

    columns: list[tuple[str, str, str]] = []
    for item in keys:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        description = str(item.get("description", name)).strip() or name
        group = str(item.get("type", "")).strip()
        columns.append((name, description, group))

    if not columns:
        raise ValueError("json:traceability_matrix must define at least one column in 'keys'.")
    return columns
