from __future__ import annotations

from copy import deepcopy
from typing import Any

from panflow_service.companion import build_document_result, render_heading
from panflow_service.renderers.testcase_table import render as render_testcase_table


BASE_DOCUMENT_CONFIG: dict[str, object] = {
    "colgroup": ["7%", "9%", "2%", "20%", "4%", "6%", "9%", "8%", "1%", "30%"],
    "meta_labels": [
        "用例名称",
        "用例标识",
        "被测软件名称",
        "型号/版本",
        "用例说明",
        "前提和约束（包括初始化要求）",
        "测试终止条件",
    ],
    "footer_labels": [
        "设计人员",
        "设计日期",
        "测试结论",
        "缺陷标识",
        "测试人员",
        "测试时间",
    ],
}

STYLE_PRESETS: dict[str, dict[str, object]] = {
    "business": {
        "font_family": "微软雅黑",
        "font_size": "12pt",
        "fonts": {
            "title": {"font_family": "微软雅黑", "font_size": "14pt", "font_weight": "700", "text_align": "left"},
            "module": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700", "text_align": "left"},
            "case_title": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700", "text_align": "left"},
            "table": {"font_family": "微软雅黑", "font_size": "10.5pt"},
            "meta_label": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700"},
            "meta_value": {"font_family": "微软雅黑", "font_size": "12pt"},
            "section_label": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700"},
            "section_value": {"font_family": "微软雅黑", "font_size": "12pt"},
            "step_header": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700"},
            "step_index": {"font_family": "微软雅黑", "font_size": "12pt"},
            "step_value": {"font_family": "微软雅黑", "font_size": "12pt"},
            "footer_label": {"font_family": "微软雅黑", "font_size": "12pt", "font_weight": "700"},
            "footer_value": {"font_family": "微软雅黑", "font_size": "12pt"},
        },
    },
}


def render_document(
    markdown: str,
    metadata: dict[str, object],
    config: dict[str, object],
    context: dict[str, object],
) -> dict[str, str]:
    template_style = str(metadata.get("template_style", "business"))
    # 业务样例约定样式直接写在 py 里，避免表格再受外部 toml 覆盖。
    html_parts = _render_business_section(
        markdown,
        metadata,
        context,
        section_index=int(context.get("section_index", 1)),
        template_style=template_style,
    )
    return build_document_result(
        "\n".join(html_parts) + "\n",
        template_style=template_style,
    )
def _render_business_section(
    markdown: str,
    metadata: dict[str, object],
    context: dict[str, object],
    *,
    section_index: int,
    template_style: str,
) -> list[str]:
    parsed = _parse_business_markdown(markdown)
    document_config = _resolve_document_config(template_style)
    fonts = _read_font_config(document_config)

    table_payload = _build_table_payload(parsed, document_config, fonts)
    wrapper_prefix = f'<div class="pf-section pf-section-{template_style}" data-template-style="{template_style}">'
    wrapper_suffix = "</div>"
    parts = [
        wrapper_prefix,
        render_heading(
            parsed["title"],
            level=1,
            font_family=fonts["title"]["font_family"],
            font_size=fonts["title"]["font_size"],
            font_weight=fonts["title"]["font_weight"],
            text_align=fonts["title"]["text_align"],
        ),
        "",
        render_heading(
            parsed["module"],
            level=2,
            font_family=fonts["module"]["font_family"],
            font_size=fonts["module"]["font_size"],
            font_weight=fonts["module"]["font_weight"],
            text_align=fonts["module"]["text_align"],
        ),
        "",
        render_heading(
            parsed["case_title"],
            level=3,
            font_family=fonts["case_title"]["font_family"],
            font_size=fonts["case_title"]["font_size"],
            font_weight=fonts["case_title"]["font_weight"],
            text_align=fonts["case_title"]["text_align"],
        ),
        "",
        render_testcase_table(
            table_payload,
            {
                "block_key": "business",
                "block_index": section_index,
                "source_path": context["source_path"],
            },
        ),
        wrapper_suffix,
    ]
    return parts


def _parse_business_markdown(markdown: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in markdown.splitlines()]
    title = ""
    module = ""
    case_title = ""
    meta_items: list[tuple[str, str]] = []
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("# "):
            title = line[2:].strip()
            current_section = None
            continue
        if line.startswith("## "):
            module = line[3:].strip()
            current_section = None
            continue
        if line.startswith("### "):
            case_title = line[4:].strip()
            current_section = None
            continue
        if line.startswith("#### "):
            current_section = line[5:].strip()
            sections[current_section] = []
            continue
        if line.startswith("- ") and "：" in line:
            label, value = line[2:].split("：", maxsplit=1)
            meta_items.append((label.strip(), value.strip()))
            continue

        if current_section is not None:
            sections[current_section].append(line)

    return {
        "title": title,
        "module": module,
        "case_title": case_title,
        "meta_items": meta_items,
        "sections": sections,
    }


def _build_table_payload(
    parsed: dict[str, Any],
    document_config: dict[str, object],
    fonts: dict[str, dict[str, str | None]],
) -> dict[str, object]:
    # 复杂表格的行高、居中方式和边框都直接在 a.py 里声明，
    # 由 renderer 原样输出成 HTML，pandoc 再按 HTML 输入转 docx。
    table_style = {
        "font_family": fonts["table"]["font_family"],
        "font_size": fonts["table"]["font_size"],
        "width": "100%",
        "border": "1px solid #000000",
        "border_collapse": "collapse",
        "table_layout": "fixed",
        "line_height": "1.6",
    }
    colgroup = document_config.get(
        "colgroup",
        ["7%", "9%", "2%", "20%", "4%", "6%", "9%", "8%", "1%", "30%"],
    )
    meta_labels = _string_list(
        document_config.get(
            "meta_labels",
            [
                "用例名称",
                "用例标识",
                "被测软件名称",
                "型号/版本",
                "用例说明",
                "前提和约束（包括初始化要求）",
                "测试终止条件",
            ],
        ),
    )
    footer_labels = _string_list(
        document_config.get(
            "footer_labels",
            [
                "设计人员",
                "设计日期",
                "测试结论",
                "缺陷标识",
                "测试人员",
                "测试时间",
            ],
        ),
    )

    meta_map = {label: value for label, value in parsed["meta_items"]}
    sections = parsed["sections"]
    steps = _extract_steps(sections.get("测试步骤", []))

    rows: list[list[dict[str, object]]] = [
        [
            _cell("用例名称", colspan=2, align="center", bold=True, font=fonts["meta_label"]),
            _cell(meta_map.get("用例名称", parsed["case_title"]), colspan=3, font=fonts["meta_value"]),
            _cell("用例标识", colspan=2, align="center", bold=True, font=fonts["meta_label"]),
            _cell(meta_map.get("用例标识", ""), colspan=3, font=fonts["meta_value"]),
        ],
        [
            _cell("被测软件名称", colspan=2, align="center", bold=True, font=fonts["meta_label"]),
            _cell(meta_map.get("被测软件名称", ""), colspan=3, font=fonts["meta_value"]),
            _cell("型号/版本", colspan=2, align="center", bold=True, font=fonts["meta_label"]),
            _cell(meta_map.get("型号/版本", ""), colspan=3, font=fonts["meta_value"]),
        ],
    ]

    for label in meta_labels[4:]:
        rows.append(
            [
                _cell(label, colspan=2, align="center", bold=True, font=fonts["section_label"]),
                _cell(_lookup_section_or_meta(label, sections, meta_map), colspan=8, font=fonts["section_value"]),
            ],
        )

    rows.extend(
        [
            [_cell("测试过程", colspan=10, align="center", bold=True, font=fonts["step_header"])],
            [
                _cell("序号", align="center", bold=True, font=fonts["step_header"]),
                _cell("测试输入、规程", colspan=3, align="center", bold=True, font=fonts["step_header"]),
                _cell("预期结果", colspan=5, align="center", bold=True, font=fonts["step_header"]),
                _cell("实际测试结果", align="center", bold=True, font=fonts["step_header"]),
            ],
        ],
    )

    for index, step in enumerate(steps, start=1):
        rows.append(
            [
                _cell(f"{index}.", align="center", font=fonts["step_index"]),
                _cell(step, colspan=3, font=fonts["step_value"]),
                _cell("", colspan=5, font=fonts["step_value"]),
                _cell("", font=fonts["step_value"]),
            ],
        )

    footer_values = [meta_map.get(label, "") for label in footer_labels]
    if len(footer_values) == 6:
        rows.extend(
            [
                [
                    _cell(footer_labels[0], colspan=3, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[0], colspan=3, align="center", font=fonts["footer_value"]),
                    _cell(footer_labels[1], colspan=2, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[1], colspan=2, align="center", font=fonts["footer_value"]),
                ],
                [
                    _cell(footer_labels[2], colspan=3, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[2], colspan=3, align="center", font=fonts["footer_value"]),
                    _cell(footer_labels[3], colspan=2, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[3], colspan=2, align="center", font=fonts["footer_value"]),
                ],
                [
                    _cell(footer_labels[4], colspan=3, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[4], colspan=3, align="center", font=fonts["footer_value"]),
                    _cell(footer_labels[5], colspan=2, align="center", bold=True, font=fonts["footer_label"]),
                    _cell(footer_values[5], colspan=2, align="center", font=fonts["footer_value"]),
                ],
            ],
        )

    return {
        "colgroup": colgroup,
        "table_style": table_style,
        "rows": rows,
    }


def _resolve_document_config(template_style: str) -> dict[str, object]:
    resolved = deepcopy(BASE_DOCUMENT_CONFIG)
    style_config = STYLE_PRESETS.get(template_style, STYLE_PRESETS["business"])
    return _deep_merge_dicts(resolved, style_config)


def _extract_steps(lines: list[str]) -> list[str]:
    steps: list[str] = []
    for line in lines:
        if ". " in line and line[0].isdigit():
            _, content = line.split(". ", maxsplit=1)
            steps.append(content.strip())
        else:
            steps.append(line.strip())
    return [step for step in steps if step]


def _lookup_section_or_meta(label: str, sections: dict[str, list[str]], meta_map: dict[str, str]) -> str:
    if label in meta_map:
        return meta_map[label]
    if label in sections:
        return " ".join(item.strip() for item in sections[label] if item.strip())
    return ""


def _cell(
    text: str,
    *,
    colspan: int = 1,
    align: str = "left",
    bold: bool = False,
    font: dict[str, str | None] | None = None,
) -> dict[str, object]:
    cell = {
        "text": text,
        "colspan": colspan,
        "text_align": align,
        "bold": bold,
        "vertical_align": "middle",
        "line_height": "1.6",
        "padding": "6pt 8pt",
        "border": "1px solid #000000",
    }
    if font is not None:
        if font.get("font_family"):
            cell["font_family"] = font["font_family"]
        if font.get("font_size"):
            cell["font_size"] = font["font_size"]
        if font.get("font_weight"):
            cell["font_weight"] = font["font_weight"]
    return cell


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings.")
    return [str(item) for item in value]


def _read_font_config(document_config: dict[str, object]) -> dict[str, dict[str, str | None]]:
    raw_fonts = document_config.get("fonts", {})
    if raw_fonts is not None and not isinstance(raw_fonts, dict):
        raise ValueError("document.fonts must be an object.")

    fonts = raw_fonts if isinstance(raw_fonts, dict) else {}
    base_family = str(document_config.get("font_family", "仿宋"))
    base_size = str(document_config.get("font_size", "12pt"))

    return {
        "title": _font_spec(fonts, "title", base_family, "22pt", "700", "center"),
        "module": _font_spec(fonts, "module", base_family, "16pt", "700", "center"),
        "case_title": _font_spec(fonts, "case_title", base_family, "14pt", "700", "center"),
        "table": _font_spec(fonts, "table", base_family, base_size, None, None),
        "meta_label": _font_spec(fonts, "meta_label", base_family, base_size, "700", None),
        "meta_value": _font_spec(fonts, "meta_value", base_family, base_size, None, None),
        "section_label": _font_spec(fonts, "section_label", base_family, base_size, "700", None),
        "section_value": _font_spec(fonts, "section_value", base_family, base_size, None, None),
        "step_header": _font_spec(fonts, "step_header", base_family, base_size, "700", None),
        "step_index": _font_spec(fonts, "step_index", base_family, base_size, None, None),
        "step_value": _font_spec(fonts, "step_value", base_family, base_size, None, None),
        "footer_label": _font_spec(fonts, "footer_label", base_family, base_size, "700", None),
        "footer_value": _font_spec(fonts, "footer_value", base_family, base_size, None, None),
    }


def _font_spec(
    fonts: dict[str, object],
    key: str,
    default_family: str,
    default_size: str,
    default_weight: str | None,
    default_align: str | None,
) -> dict[str, str | None]:
    value = fonts.get(key, {})
    if value is not None and not isinstance(value, dict):
        raise ValueError(f"document.fonts.{key} must be an object.")
    config = value if isinstance(value, dict) else {}
    return {
        "font_family": str(config.get("font_family", default_family)) if default_family or "font_family" in config else None,
        "font_size": str(config.get("font_size", default_size)) if default_size or "font_size" in config else None,
        "font_weight": str(config.get("font_weight", default_weight)) if default_weight is not None or "font_weight" in config else None,
        "text_align": str(config.get("text_align", default_align)) if default_align is not None or "text_align" in config else None,
    }


def _deep_merge_dicts(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged
