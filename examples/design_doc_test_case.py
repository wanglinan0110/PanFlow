"""测试用例大表渲染脚本。"""

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
    """把单条测试用例 JSON 渲染成测试步骤明细表。"""
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError(f"json:test_case block #{block_index} 'steps' must be a list.")

    step_rows_html = "".join(
        f"""    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;">{_text(step.get("no")) or str(index)}</td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="3">{_text(step.get("input_procedure"))}</td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="3">{_text(step.get("expected_result")) or _text(step.get("expectation"))}</td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="3">{_text(step.get("note"))}</td>
    </tr>
"""
        for index, step in enumerate((item if isinstance(item, dict) else {} for item in steps), start=1)
    )

    return (
        f'<table id="design-doc-table-{table_index}" class="pf-table pf-design-doc-table pf-design-doc-test-case" '
        'data-json-block-type="test_case" '
        'style="width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #000000;">\n'
        "  <tbody>\n"
        f"""    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>用例名称</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="4">{_text(payload.get("use_case_name"))}</td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>用例标识</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="2">{_text(payload.get("use_case_id"))}</td>
    </tr>
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>测试跟踪</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="8">{_text(payload.get("test_track"))}</td>
    </tr>
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>前提和约束</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="8">{_text(payload.get("preconditions"))}</td>
    </tr>
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>终止条件</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="8">{_text(payload.get("termination_conditions"))}</td>
    </tr>
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;"><strong>序号</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="3"><strong>测试输入、规程</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="3"><strong>预期结果</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="3"><strong>备注</strong></td>
    </tr>
{step_rows_html}    
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>预期结果</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="8">{_text(payload.get("result_expectation"))}</td>
    </tr>
    <tr>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>设计人员</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="3">{_text(payload.get("designer"))}</td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: center; vertical-align: middle;" colspan="2"><strong>设计日期</strong></td>
      <td style="border: 1px solid #000000; padding: 6pt 8pt; text-align: left; vertical-align: middle;" colspan="3">{_text(payload.get("design_date"))}</td>
    </tr>
  </tbody>\n"""
        "</table>"
    )


def _text(value: object) -> str:
    """输出适合放进 td 的 HTML 文本。"""
    return escape("" if value is None else str(value)).replace("\n", "<br />")
