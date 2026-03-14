"""业务测试用例模板示例。"""

from __future__ import annotations

from copy import deepcopy
from html import escape
from typing import Any

from panflow_service.companion import build_document_result

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
    # footer_labels 固定对应表格底部 3 行，每行排 2 组字段。
    # 这一块主要给设计、执行、结论留痕使用，通常由人工在 Word 中继续补充。
    "footer_labels": [
        "设计人员",
        "设计日期",
        "测试结论",
        "缺陷标识",
        "测试人员",
        "测试时间",
    ],
}

def render_document(
    markdown: str,
    metadata: dict[str, object],
    config: dict[str, object],
    context: dict[str, object],
) -> dict[str, str]:
    """把一个业务测试用例 section 渲染成最终交给 PanFlow 的 HTML 结果。"""
    template_style = str(metadata.get("template_style", "business"))
    parsed = _parse_business_markdown(markdown)
    document_config = deepcopy(BASE_DOCUMENT_CONFIG)
    table_html = _render_table_html(
        parsed,
        document_config,
        section_index=int(context.get("section_index", 1)),
    )

    html_parts = [
        f'<div class="pf-section pf-section-{template_style}" data-template-style="{template_style}">',
        f'<h1 style="font-family: simhei; font-size: 22pt; font-weight: 700; text-align: left">{escape(parsed["title"])}</h1>',
        "",
        f'<h2 style="font-family: simhei; font-size: 12pt; font-weight: 700; text-align: left">{escape(parsed["module"])}</h2>',
        "",
        f'<h3 style="font-family: simhei; font-size: 12pt; font-weight: 700; text-align: left">{escape(parsed["case_title"])}</h3>',
        "",
        table_html,
        "</div>",
    ]
    return build_document_result(
        "\n".join(html_parts) + "\n",
        template_style=template_style,
    )

def _parse_business_markdown(markdown: str) -> dict[str, Any]:
    """把业务 Markdown 拆成标题、短字段和分节正文，便于后面直接拼表格 HTML。"""
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

def _extract_steps(lines: list[str]) -> list[str]:
    """把“测试步骤”小节整理成纯步骤文本列表，去掉前面的数字序号噪音。"""
    steps: list[str] = []
    for line in lines:
        if ". " in line and line[0].isdigit():
            _, content = line.split(". ", maxsplit=1)
            steps.append(content.strip())
        else:
            steps.append(line.strip())
    return [step for step in steps if step]

def _render_table_html(
    parsed: dict[str, Any],
    document_config: dict[str, object],
    *,
    section_index: int,
) -> str:
    """按照业务模板的固定版式，把解析后的字段直接拼成一整段 table HTML。"""
    colgroup_value = document_config["colgroup"]
    meta_labels_value = document_config["meta_labels"]
    footer_labels_value = document_config["footer_labels"]
    if not isinstance(colgroup_value, list):
        raise ValueError("colgroup must be a list of strings.")
    if not isinstance(meta_labels_value, list):
        raise ValueError("meta_labels must be a list of strings.")
    if not isinstance(footer_labels_value, list):
        raise ValueError("footer_labels must be a list of strings.")

    colgroup = [str(item) for item in colgroup_value]
    meta_labels = [str(item) for item in meta_labels_value]
    footer_labels = [str(item) for item in footer_labels_value]
    if len(meta_labels) < 7:
        raise ValueError("meta_labels must define at least 7 labels.")
    if len(footer_labels) < 6:
        raise ValueError("footer_labels must define at least 6 labels.")

    meta_map = {label: value for label, value in parsed["meta_items"]}
    sections = parsed["sections"]
    steps = _extract_steps(sections.get("测试步骤", []))

    case_name_label = meta_labels[0]
    case_id_label = meta_labels[1]
    product_name_label = meta_labels[2]
    version_label = meta_labels[3]
    long_text_labels = meta_labels[4:]
    designer_label = footer_labels[0]
    design_date_label = footer_labels[1]
    conclusion_label = footer_labels[2]
    defect_label = footer_labels[3]
    tester_label = footer_labels[4]
    test_time_label = footer_labels[5]

    colgroup_html = "  <colgroup>\n" + "\n".join(
        f'    <col style="width: {escape(str(width))};" />' for width in colgroup
    ) + "\n  </colgroup>\n"
    case_title_text = escape(meta_map.get(case_name_label, str(parsed["case_title"]))).replace("\n", "<br />")
    case_id_text = escape(meta_map.get(case_id_label, "")).replace("\n", "<br />")
    product_name_text = escape(meta_map.get(product_name_label, "")).replace("\n", "<br />")
    version_text = escape(meta_map.get(version_label, "")).replace("\n", "<br />")
    designer_text = escape(meta_map.get(designer_label, "")).replace("\n", "<br />")
    design_date_text = escape(meta_map.get(design_date_label, "")).replace("\n", "<br />")
    conclusion_text = escape(meta_map.get(conclusion_label, "")).replace("\n", "<br />")
    defect_text = escape(meta_map.get(defect_label, "")).replace("\n", "<br />")
    tester_text = escape(meta_map.get(tester_label, "")).replace("\n", "<br />")
    test_time_text = escape(meta_map.get(test_time_label, "")).replace("\n", "<br />")

    meta_rows_html = f"""    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(case_name_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{case_title_text}</td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(case_id_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{case_id_text}</td>
    </tr>
    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(product_name_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{product_name_text}</td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(version_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{version_text}</td>
    </tr>
"""

    long_text_rows_html = "".join(
        f"""    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="8">{escape(meta_map.get(label) or " ".join(item.strip() for item in sections.get(label, []) if item.strip())).replace("\n", "<br />")}</td>
    </tr>
"""
        for label in long_text_labels
    )

    step_header_rows_html = """    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="10"><strong>测试过程</strong></td>
    </tr>
    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700"><strong>序号</strong></td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="3"><strong>测试输入、规程</strong></td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="5"><strong>预期结果</strong></td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700"><strong>实际测试结果</strong></td>
    </tr>
"""

    step_rows_html = "".join(
        f"""    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt">{index}.</td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{escape(step).replace("\n", "<br />")}</td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="5"></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt"></td>
    </tr>
"""
        for index, step in enumerate(steps, start=1)
    )

    footer_rows_html = f"""    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="3"><strong>{escape(designer_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{designer_text}</td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(design_date_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="2">{design_date_text}</td>
    </tr>
    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="3"><strong>{escape(conclusion_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{conclusion_text}</td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(defect_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="2">{defect_text}</td>
    </tr>
    <tr>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="3"><strong>{escape(tester_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="3">{tester_text}</td>
      <td style="text-align: center; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt; font-weight: 700" colspan="2"><strong>{escape(test_time_label)}</strong></td>
      <td style="text-align: left; line-height: 1; vertical-align: middle; border: 1px solid #000000; padding: 6pt 8pt; font-family: simhei; font-size: 12pt" colspan="2">{test_time_text}</td>
    </tr>
"""
    tbody_html = f"""  <tbody>
{meta_rows_html}{long_text_rows_html}{step_header_rows_html}{step_rows_html}{footer_rows_html}  </tbody>
"""

    return (
        f'<table id="table-{section_index}" class="pf-table pf-testcase-table" '
        'style="font-family: simhei; font-size: 10.5pt; line-height: 1; '
        'border: 1px solid #000000; width: 100%; border-collapse: collapse; '
        'table-layout: fixed">\n'
        f"{colgroup_html}"
        f"{tbody_html}"
        "</table>"
    )
