"""Markdown 中 JSON renderer 代码块的替换逻辑。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from panflow_service.registry import RendererLoadError, RendererRegistry


FENCED_BLOCK_PATTERN = re.compile(
    r"```(?P<info>[^\n`]*)\n(?P<body>.*?)\n```",
    re.DOTALL,
)


class MarkdownRenderError(RuntimeError):
    """Raised when markdown cannot be rendered into HTML."""


@dataclass(frozen=True)
class RenderResult:
    # 除了渲染后的 markdown，也保留每个块的元信息，给模板钩子复用。
    markdown: str
    blocks: list[dict[str, object]]


def render_markdown_document(
    markdown: str,
    registry: RendererRegistry,
    *,
    source_path: Path | None = None,
) -> RenderResult:
    # 这个函数是“JSON 代码块 -> HTML”的主入口。
    blocks: list[dict[str, object]] = []
    block_index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal block_index
        info = match.group("info").strip()
        block_key = parse_block_key(info)
        if block_key is None:
            # 非目标代码块原样保留，避免误伤普通 fenced block。
            return match.group(0)

        block_index += 1
        body = match.group("body")
        payload = _parse_json_payload(body, block_key, source_path, block_index)
        # context 用于让 renderer 感知块序号、来源文件等外围信息。
        context = {
            "block_key": block_key,
            "block_index": block_index,
            "source_path": str(source_path) if source_path is not None else None,
        }
        try:
            html = registry.render(block_key, payload, context)
            blocks.append(
                {
                    "block_key": block_key,
                    "block_index": block_index,
                    "payload": payload,
                    "context": context.copy(),
                    "renderer_path": str(registry.get_renderer_path(block_key)),
                },
            )
        except RendererLoadError as exc:
            raise MarkdownRenderError(str(exc)) from exc
        except Exception as exc:
            location = str(source_path) if source_path is not None else "<memory>"
            raise MarkdownRenderError(
                f"Renderer '{block_key}' failed at {location}#{block_index}: {exc}",
            ) from exc
        return html

    # 用单次正则扫描完成替换，保证 markdown 其余部分不被重写。
    rendered_markdown = FENCED_BLOCK_PATTERN.sub(replace, markdown)
    return RenderResult(markdown=rendered_markdown, blocks=blocks)


def render_markdown_text(
    markdown: str,
    registry: RendererRegistry,
    *,
    source_path: Path | None = None,
) -> str:
    # 纯字符串接口，适合测试或不关心 block 元数据的调用方。
    return render_markdown_document(
        markdown,
        registry,
        source_path=source_path,
    ).markdown


def parse_block_key(info: str) -> str | None:
    # 兼容两种标记风格：```json key 与 ```json:key。
    if not info:
        return None

    tokens = info.split()
    # 兼容 ```json key 和 ```json:key 两种写法。
    if tokens[0] == "json" and len(tokens) >= 2:
        return tokens[1]
    if tokens[0].startswith("json:"):
        block_key = tokens[0].split(":", maxsplit=1)[1].strip()
        return block_key or None
    return None


def _parse_json_payload(
    body: str,
    block_key: str,
    source_path: Path | None,
    block_index: int,
) -> Any:
    # 解析失败时把来源文件和块序号一起带上，方便定位 markdown 里的坏数据。
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        location = str(source_path) if source_path is not None else "<memory>"
        raise MarkdownRenderError(
            f"Invalid JSON in renderer block '{block_key}' at {location}#{block_index}: {exc}",
        ) from exc
