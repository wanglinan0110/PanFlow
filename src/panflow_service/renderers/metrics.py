RENDER_KEYS = ["metrics"]


from html import escape
from typing import Any


def render(payload: Any, context: dict[str, object]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("metrics renderer expects a JSON object.")

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("metrics.items must be a list.")

    rows = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each metrics item must be an object.")
        label = escape(str(item.get("label", "")))
        value = escape(str(item.get("value", "")))
        # 指标表默认采用左右两列，适合在 Word 中保持紧凑展示。
        rows.append(f"  <tr><th>{label}</th><td>{value}</td></tr>")

    body = "\n".join(rows)
    return (
        '<table class="pf-metrics">\n'
        "  <tbody>\n"
        f"{body}\n"
        "  </tbody>\n"
        "</table>"
    )
