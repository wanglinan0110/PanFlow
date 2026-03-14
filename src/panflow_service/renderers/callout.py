"""简单提示块 renderer。"""

RENDER_KEYS = ["callout"]


from html import escape
from typing import Any


def render(payload: Any, context: dict[str, object]) -> str:
    # callout 适合处理“标题 + 正文 + 语气”这类轻量信息块。
    if not isinstance(payload, dict):
        raise ValueError("callout renderer expects a JSON object.")

    title = escape(str(payload.get("title", "提示")))
    body = escape(str(payload.get("body", "")))
    tone = escape(str(payload.get("tone", "info")))
    # 不同 callout 块生成独立 id，后续如果加样式或锚点会更容易定位。
    block_id = f"callout-{context['block_index']}"
    return (
        f'<div id="{block_id}" class="pf-callout pf-callout-{tone}">\n'
        f"  <p><strong>{title}</strong></p>\n"
        f"  <p>{body}</p>\n"
        "</div>"
    )
