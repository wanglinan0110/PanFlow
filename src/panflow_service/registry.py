"""Renderer 注册表与按需加载逻辑。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any


Renderer = Callable[[Any, dict[str, object]], str]
TemplateHook = Callable[[Path | None, list[dict[str, object]], dict[str, object]], Path | str | None]


class RendererLoadError(RuntimeError):
    """Raised when a renderer cannot be loaded or executed."""


@dataclass(frozen=True)
class LoadedRenderer:
    # 把脚本路径、模块对象、render 函数和模板钩子收口到一个对象里。
    key: str
    path: Path
    module: ModuleType
    render: Renderer
    prepare_reference_doc: TemplateHook | None


class RendererRegistry:
    def __init__(self, mapping: dict[str, Path]) -> None:
        self.mapping = mapping
        # renderer 按需加载并缓存，避免一次转换里重复 import 同一脚本。
        self._cache: dict[str, LoadedRenderer] = {}

    def render(self, key: str, payload: Any, context: dict[str, object]) -> str:
        # 真正渲染前先确保脚本已经被加载并校验过接口。
        renderer = self._load_renderer(key)
        html = renderer.render(payload, context)
        if not isinstance(html, str):
            raise RendererLoadError(f"Renderer '{key}' must return a string of HTML.")
        return html

    def get_renderer_path(self, key: str) -> Path:
        return self._load_renderer(key).path

    def apply_template_hooks(
        self,
        current_reference_doc: Path | None,
        block_records: list[dict[str, object]],
        context: dict[str, object],
    ) -> Path | None:
        # 模板钩子按 renderer 分组执行，避免同一个脚本对同一批块重复处理。
        reference_doc = current_reference_doc
        ordered_groups: list[tuple[LoadedRenderer, list[dict[str, object]]]] = []
        groups_by_path: dict[Path, list[dict[str, object]]] = {}

        for block_record in block_records:
            renderer_key = str(block_record["block_key"])
            renderer = self._load_renderer(renderer_key)
            group = groups_by_path.get(renderer.path)
            if group is None:
                group = []
                groups_by_path[renderer.path] = group
                ordered_groups.append((renderer, group))
            group.append(block_record)

        for renderer, records in ordered_groups:
            hook = renderer.prepare_reference_doc
            if hook is None:
                continue

            result = hook(
                reference_doc,
                records,
                {
                    **context,
                    "renderer_key": renderer.key,
                    "renderer_path": str(renderer.path),
                },
            )
            reference_doc = _normalize_template_result(
                result,
                current_reference_doc=reference_doc,
                renderer_path=renderer.path,
            )

        return reference_doc

    def _load_renderer(self, key: str) -> LoadedRenderer:
        # renderer 首次使用时动态导入，后续直接走缓存。
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        path = self.mapping.get(key)
        if path is None:
            available = ", ".join(sorted(self.mapping)) or "<none>"
            raise RendererLoadError(
                f"Unknown renderer '{key}'. Available renderers: {available}.",
            )

        module = _load_module_from_path(key, path)
        render = getattr(module, "render", None)
        if not callable(render):
            raise RendererLoadError(
                f"Renderer script '{path}' must expose a callable 'render(payload, context)'.",
            )

        prepare_reference_doc = getattr(module, "prepare_reference_doc", None)
        if prepare_reference_doc is not None and not callable(prepare_reference_doc):
            raise RendererLoadError(
                f"Renderer script '{path}' exposes 'prepare_reference_doc' but it is not callable.",
            )

        loaded = LoadedRenderer(
            key=key,
            path=path.resolve(),
            module=module,
            render=render,
            prepare_reference_doc=prepare_reference_doc,
        )
        self._cache[key] = loaded
        return loaded


def _load_module_from_path(key: str, path: Path) -> ModuleType:
    resolved_path = path.resolve()
    module_name = f"panflow_renderer_{key}_{abs(hash(resolved_path))}"
    spec = spec_from_file_location(module_name, resolved_path)
    if spec is None or spec.loader is None:
        raise RendererLoadError(f"Unable to load renderer module from '{resolved_path}'.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_template_result(
    result: Path | str | None,
    *,
    current_reference_doc: Path | None,
    renderer_path: Path,
) -> Path | None:
    # 钩子允许返回 Path、字符串路径或 None，这里统一归一化。
    if result is None:
        return current_reference_doc

    if isinstance(result, Path):
        return result.resolve() if result.is_absolute() else (renderer_path.parent / result).resolve()

    if isinstance(result, str):
        candidate = Path(result)
        return candidate.resolve() if candidate.is_absolute() else (renderer_path.parent / candidate).resolve()

    raise RendererLoadError(
        f"Renderer script '{renderer_path}' returned an unsupported reference doc result: {type(result)!r}.",
    )
