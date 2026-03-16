"""静态分析表渲染脚本。"""

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
    """把静态分析 JSON 结构渲染成支持首列合并的表格。"""
    columns, merge_key = _resolve_columns(payload)
    rows = payload.get("values", [])
    if not isinstance(rows, list):
        raise ValueError(f"json:static_analysis block #{block_index} 'values' must be a list.")

    normalized_rows = [row if isinstance(row, dict) else {} for row in (rows or [{}])]
    merge_rowspans = _build_merge_rowspans(normalized_rows, merge_key)

    header_html = "".join(
        f'<th style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{escape(description)}</th>'
        for name, description in columns
        if name != "merge_level"
    )

    body_parts: list[str] = []
    for row_index, row in enumerate(normalized_rows):
        body_parts.append("    <tr>")
        for name, _ in columns:
            if name == "merge_level":
                continue

            if name == merge_key:
                rowspan = merge_rowspans[row_index]
                if rowspan == 0:
                    continue
                rowspan_attr = f' rowspan="{rowspan}"' if rowspan > 1 else ""
                body_parts.append(
                    f'      <td{rowspan_attr} style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">'
                    f'{escape(str(row.get(name, ""))).replace("\n", "<br />")}</td>',
                )
                continue

            body_parts.append(
                '      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;">'
                f'{escape(str(row.get(name, ""))).replace("\n", "<br />")}</td>',
            )
        body_parts.append("    </tr>")

    body_html = "\n".join(body_parts)
    return (
        f'<table id="design-doc-table-{table_index}" class="pf-table pf-design-doc-table pf-design-doc-static-analysis" '
        'data-json-block-type="static_analysis" '
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


def _resolve_columns(payload: dict[str, Any]) -> tuple[list[tuple[str, str]], str | None]:
    """读取列定义，并识别是否存在需要纵向合并的主键列。"""
    keys = payload.get("keys", [])
    if not isinstance(keys, list):
        raise ValueError("json:static_analysis 'keys' must be a list.")

    columns: list[tuple[str, str]] = []
    merge_key: str | None = None
    for item in keys:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        description = str(item.get("description", name)).strip() or name
        columns.append((name, description))
        if item.get("isMergeKey") is True:
            merge_key = name

    if not columns:
        raise ValueError("json:static_analysis must define at least one column in 'keys'.")
    return columns, merge_key


def _build_merge_rowspans(rows: list[dict[str, Any]], merge_key: str | None) -> list[int]:
    """把相邻且 merge_level 相同的行压成同一组，返回每行对应的 rowspan。"""
    if merge_key is None:
        return [1] * len(rows)

    rowspans = [1] * len(rows)
    row_index = 0
    while row_index < len(rows):
        merge_value = rows[row_index].get("merge_level")
        if merge_value in (None, ""):
            row_index += 1
            continue

        group_end = row_index + 1
        while group_end < len(rows) and rows[group_end].get("merge_level") == merge_value:
            group_end += 1

        group_size = group_end - row_index
        rowspans[row_index] = group_size
        for hidden_index in range(row_index + 1, group_end):
            rowspans[hidden_index] = 0
        row_index = group_end

    return rowspans
