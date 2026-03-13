from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib
from types import ModuleType
from typing import Any

from panflow_service.runtime_paths import resolve_examples_dir


class DocumentProcessorError(RuntimeError):
    """Raised when a companion markdown processor cannot be loaded or executed."""


@dataclass(frozen=True)
class MarkdownSection:
    metadata: dict[str, object]
    body: str


@dataclass(frozen=True)
class MarkdownDocument:
    metadata: dict[str, object]
    body: str
    sections: list[MarkdownSection]


@dataclass(frozen=True)
class CompanionDocument:
    markdown_path: Path
    document: MarkdownDocument


@dataclass(frozen=True)
class DocumentRenderResult:
    content: str
    input_format: str
    reference_doc: Path | None
    template_style: str | None
    font_family: str | None
    font_size: str | None


def discover_companion_document(markdown_path: Path) -> CompanionDocument:
    text = markdown_path.read_text(encoding="utf-8")
    document = parse_markdown_document(text)

    return CompanionDocument(
        markdown_path=markdown_path.resolve(),
        document=document,
    )


def has_companion_processor(companion: CompanionDocument, project_root: Path) -> bool:
    return any(
        _resolve_processor_path(companion, section.metadata.get("template_style"), project_root) is not None
        for section in companion.document.sections
    )


def parse_markdown_document(markdown: str) -> MarkdownDocument:
    lines = markdown.splitlines(keepends=True)
    sections: list[MarkdownSection] = []
    current_metadata: dict[str, object] = {}
    current_body: list[str] = []
    index = 0
    saw_metadata_block = False

    while index < len(lines):
        if lines[index] == "+++\n":
            closing_index = _find_front_matter_end(lines, index + 1)
            if closing_index is not None:
                parsed_metadata = tomllib.loads("".join(lines[index + 1:closing_index]))
                if saw_metadata_block or current_body:
                    sections.append(
                        MarkdownSection(
                            metadata=current_metadata,
                            body="".join(current_body),
                        ),
                    )
                    current_body = []
                current_metadata = parsed_metadata
                saw_metadata_block = True
                index = closing_index + 1
                continue
        current_body.append(lines[index])
        index += 1

    if saw_metadata_block:
        sections.append(
            MarkdownSection(
                metadata=current_metadata,
                body="".join(current_body),
            ),
        )
    else:
        sections.append(MarkdownSection(metadata={}, body=markdown))

    non_empty_sections = [
        section
        for section in sections
        if section.body.strip() or section.metadata
    ] or [MarkdownSection(metadata={}, body="")]
    metadata = non_empty_sections[0].metadata
    body = "\n".join(
        section.body.strip("\n")
        for section in non_empty_sections
        if section.body.strip()
    )
    if body:
        body += "\n"
    return MarkdownDocument(
        metadata=metadata,
        body=body,
        sections=non_empty_sections,
    )


def render_with_companion_processor(
    companion: CompanionDocument,
    *,
    cli_reference_doc: Path | None,
    project_root: Path,
    output_path: Path,
    temp_dir: Path,
) -> DocumentRenderResult:
    available_processor = has_companion_processor(companion, project_root)
    if not available_processor:
        examples_dir = resolve_examples_dir(project_root)
        raise DocumentProcessorError(
            f"No companion processor found for '{companion.markdown_path.name}'. Expected a matching script under '{examples_dir}'.",
        )

    base_context = {
        "project_root": str(project_root),
        "source_path": str(companion.markdown_path),
        "output_path": str(output_path),
        "temp_dir": str(temp_dir),
        "sections": [
            {
                "metadata": section.metadata,
                "body": section.body,
            }
            for section in companion.document.sections
        ],
    }

    module_cache: dict[Path, ModuleType] = {}
    html_parts: list[str] = []
    primary_reference_doc: Path | str | None = None
    primary_template_style: str | None = None
    primary_font_family: str | None = None
    primary_font_size: str | None = None
    final_input_format = "html"
    primary_metadata: dict[str, object] = companion.document.metadata

    for section_index, section in enumerate(companion.document.sections, start=1):
        if not section.body.strip():
            continue
        template_style = section.metadata.get("template_style")
        processor_path = _resolve_processor_path(companion, template_style, project_root)
        if processor_path is None:
            _emit_companion_warning(
                companion.markdown_path,
                template_style,
                section_index,
            )
            continue
        if (
            template_style is not None
            and processor_path.name == f"{companion.markdown_path.stem}.py"
            and str(template_style) != companion.markdown_path.stem
        ):
            _emit_companion_warning(
                companion.markdown_path,
                template_style,
                section_index,
                used_fallback=True,
            )
        module = module_cache.get(processor_path)
        if module is None:
            module = _load_module_from_path(processor_path)
            module_cache[processor_path] = module

        render_document = getattr(module, "render_document", None)
        if not callable(render_document):
            raise DocumentProcessorError(
                f"Companion processor '{processor_path}' must expose a callable 'render_document(markdown, metadata, config, context)'.",
            )

        context = dict(base_context)
        context.update(
            {
                "processor_path": str(processor_path),
                "section_index": section_index,
                "section_count": len(companion.document.sections),
                "current_section": {
                    "metadata": section.metadata,
                    "body": section.body,
                },
            },
        )

        result = render_document(
            section.body,
            section.metadata,
            {},
            context,
        )
        content, input_format, result_reference_doc, result_template_style, font_family, font_size = _normalize_render_result(result)
        if input_format != "html":
            final_input_format = input_format
        if input_format == "html":
            content = _wrap_html_with_font_style(
                content,
                font_family=font_family,
                font_size=font_size,
            )
            if section_index > 1 and html_parts:
                html_parts.append('<div style="page-break-before: always;"></div>')
        html_parts.append(content)

        if primary_reference_doc is None and result_reference_doc is not None:
            primary_reference_doc = result_reference_doc
        if primary_template_style is None:
            primary_template_style = result_template_style or (str(template_style) if template_style is not None else None)
            primary_metadata = section.metadata
        if primary_font_family is None and font_family is not None:
            primary_font_family = font_family
        if primary_font_size is None and font_size is not None:
            primary_font_size = font_size

    if not html_parts:
        raise DocumentProcessorError(
            f"No renderable sections found for '{companion.markdown_path.name}'. Check whether each template_style maps to an existing processor script.",
        )

    content = "\n".join(part for part in html_parts if part.strip()) + ("\n" if html_parts else "")
    reference_doc = _resolve_reference_doc(
        markdown_path=companion.markdown_path,
        metadata=primary_metadata,
        cli_reference_doc=cli_reference_doc,
        render_result_reference_doc=primary_reference_doc,
    )

    for processor_path, module in module_cache.items():
        prepare_reference_doc = getattr(module, "prepare_reference_doc", None)
        if prepare_reference_doc is None:
            continue
        if not callable(prepare_reference_doc):
            raise DocumentProcessorError(
                f"Companion processor '{processor_path}' exposes 'prepare_reference_doc' but it is not callable.",
            )
        context = dict(base_context)
        context["processor_path"] = str(processor_path)
        hook_result = prepare_reference_doc(
            reference_doc,
            companion.document.metadata,
            {},
            context,
        )
        reference_doc = _resolve_relative_path(hook_result, processor_path.parent) if hook_result is not None else reference_doc

    return DocumentRenderResult(
        content=content,
        input_format=final_input_format,
        reference_doc=reference_doc,
        template_style=primary_template_style,
        font_family=primary_font_family,
        font_size=primary_font_size,
    )

def _normalize_render_result(
    result: Any,
) -> tuple[str, str, Path | str | None, str | None, str | None, str | None]:
    if isinstance(result, str):
        return result, "html", None, None, None, None

    if isinstance(result, dict):
        content = result.get("content")
        if not isinstance(content, str):
            raise DocumentProcessorError("Document processor result dict must include a string 'content'.")
        input_format = str(result.get("input_format", "html"))
        reference_doc = result.get("reference_doc")
        template_style = result.get("template_style")
        font_family = result.get("font_family")
        font_size = result.get("font_size")
        if input_format not in {"html", "gfm+raw_html"}:
            raise DocumentProcessorError(
                "Companion processor input_format must be either 'html' or 'gfm+raw_html'.",
            )
        return (
            content,
            input_format,
            reference_doc,
            str(template_style) if template_style is not None else None,
            str(font_family) if font_family is not None else None,
            str(font_size) if font_size is not None else None,
        )

    raise DocumentProcessorError(
        "Document processor must return HTML content or a dict with 'content'.",
    )


def _resolve_reference_doc(
    *,
    markdown_path: Path,
    metadata: dict[str, object],
    cli_reference_doc: Path | None,
    render_result_reference_doc: Path | str | None,
) -> Path | None:
    if cli_reference_doc is not None:
        return cli_reference_doc.resolve()

    if render_result_reference_doc is not None:
        return _resolve_relative_path(
            render_result_reference_doc,
            markdown_path.parent,
        )

    if "reference_doc" in metadata:
        return _resolve_relative_path(metadata["reference_doc"], markdown_path.parent)
    return None


def _resolve_relative_path(value: object, base_dir: Path) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def _resolve_processor_path(
    companion: CompanionDocument,
    template_style: object,
    project_root: Path,
) -> Path | None:
    examples_dir = resolve_examples_dir(project_root)
    default_processor = examples_dir / f"{companion.markdown_path.stem}.py"

    if template_style is not None:
        style_processor = examples_dir / f"{template_style}.py"
        if style_processor.exists():
            return style_processor.resolve()
        if default_processor.exists():
            return default_processor.resolve()
        return None

    if default_processor.exists():
        return default_processor.resolve()
    return None


def _emit_companion_warning(
    markdown_path: Path,
    template_style: object,
    section_index: int,
    *,
    used_fallback: bool = False,
) -> None:
    if used_fallback:
        print(
            f"[panflow] section {section_index} in '{markdown_path.name}' uses template_style '{template_style}', "
            f"but no dedicated '{template_style}.py' was found; falling back to the same-name companion processor.",
            file=sys.stderr,
        )
        return

    print(
        f"[panflow] section {section_index} in '{markdown_path.name}' uses unknown template_style '{template_style}'; "
        "skipping this section and continuing with the remaining sections.",
        file=sys.stderr,
    )


def _find_front_matter_end(lines: list[str], start_index: int) -> int | None:
    for index in range(start_index, len(lines)):
        if lines[index] == "+++\n":
            return index
    return None


def _load_module_from_path(path: Path) -> ModuleType:
    resolved_path = path.resolve()
    module_name = f"panflow_document_{resolved_path.stem}_{abs(hash(resolved_path))}"
    spec = spec_from_file_location(module_name, resolved_path)
    if spec is None or spec.loader is None:
        raise DocumentProcessorError(f"Unable to load companion processor from '{resolved_path}'.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wrap_html_with_font_style(
    content: str,
    *,
    font_family: str | None,
    font_size: str | None,
) -> str:
    styles: list[str] = []
    if font_family:
        styles.append(f"font-family: {font_family};")
    if font_size:
        styles.append(f"font-size: {font_size};")

    if not styles:
        return content

    style_text = " ".join(styles)
    return f'<div style="{style_text}">\n{content.rstrip()}\n</div>\n'
