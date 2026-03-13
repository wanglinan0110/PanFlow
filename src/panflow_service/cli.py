from __future__ import annotations

import argparse
from pathlib import Path
import sys

from panflow_service.config import (
    DEFAULT_RENDERERS_DIR,
    PandocConfig,
    ProjectConfig,
    resolve_runtime_config,
    scan_renderer_scripts,
)
from panflow_service.main import convert_markdown_file, export_config_file, render_markdown_file
from panflow_service.runtime_paths import resolve_renderers_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panflow",
        description="Render JSON code blocks into HTML and convert Markdown to Word via pandoc.",
    )
    # 子命令拆分成 render / convert / export-config，便于单独调试各阶段。
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser(
        "render",
        aliases=["r"],
        help="Render the document to an intermediate HTML/Markdown file.",
    )
    render_parser.add_argument("input", type=Path, help="Source markdown file.")
    render_parser.add_argument("-o", "--output", type=Path, help="Rendered intermediate output path.")
    render_parser.add_argument("--config", type=Path, help="Path to panflow.toml.")

    convert_parser = subparsers.add_parser(
        "convert",
        aliases=["c"],
        help="Render JSON code blocks and then invoke pandoc to create a .docx file.",
    )
    convert_parser.add_argument("input", type=Path, help="Source markdown file.")
    convert_parser.add_argument("-o", "--output", type=Path, help="Target .docx file path.")
    convert_parser.add_argument("--config", type=Path, help="Path to panflow.toml.")
    convert_parser.add_argument(
        "--intermediate-output",
        type=Path,
        help="Optional path to keep the rendered markdown before pandoc runs.",
    )
    convert_parser.add_argument(
        "--reference-doc",
        type=Path,
        help="Optional override for pandoc --reference-doc.",
    )

    export_parser = subparsers.add_parser(
        "export-config",
        aliases=["e"],
        help="Scan renderer scripts and export a TOML mapping file.",
    )
    export_parser.add_argument("-o", "--output", type=Path, required=True, help="Target TOML file path.")
    export_parser.add_argument(
        "--renderers-dir",
        type=Path,
        default=DEFAULT_RENDERERS_DIR,
        help="Directory containing renderer python scripts.",
    )
    export_parser.add_argument(
        "--reference-doc",
        type=Path,
        default=Path("templates/reference.docx"),
        help="Default reference doc path written into TOML.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    normalized_argv = _normalize_argv_for_default_convert(raw_argv)
    args = parser.parse_args(normalized_argv)
    project_root = Path.cwd()

    if args.command in {"render", "r"}:
        config = resolve_runtime_config(project_root, args.config)
        output_path = args.output or args.input.with_name(f"{args.input.stem}.rendered.html")
        render_markdown_file(args.input, output_path, config)
        print(f"Rendered output written to {output_path}")
        return 0

    if args.command in {"convert", "c"}:
        config = resolve_runtime_config(project_root, args.config)
        output_path = args.output or args.input.with_suffix(".docx")
        convert_markdown_file(
            args.input,
            output_path,
            config,
            intermediate_output=args.intermediate_output,
            reference_doc=args.reference_doc,
        )
        print(f"Word document written to {output_path}")
        return 0

    if args.command in {"export-config", "e"}:
        # export-config 不依赖现有 TOML，而是直接扫描脚本目录生成最新映射。
        candidate_renderers_dir = (project_root / args.renderers_dir).resolve()
        renderers_dir = candidate_renderers_dir if candidate_renderers_dir.exists() else resolve_renderers_dir(project_root)
        config = ProjectConfig(
            project_root=project_root.resolve(),
            renderers=scan_renderer_scripts(renderers_dir),
            pandoc=PandocConfig(),
        )
        export_config_file(args.output, config, reference_doc=args.reference_doc)
        print(f"Config written to {args.output}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _normalize_argv_for_default_convert(argv: list[str] | None) -> list[str] | None:
    if argv is None:
        return None
    if not argv:
        return argv
    if argv[0] in {"render", "r", "convert", "c", "export-config", "e", "-h", "--help"}:
        return argv
    return ["convert", *argv]
