"""CLI 参数解析与命令分发。"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

from panflow_service.config import resolve_runtime_config
from panflow_service.main import convert_markdown_file, render_markdown_file


def build_parser() -> argparse.ArgumentParser:
    # CLI 只暴露两条主线命令：渲染中间产物、转换 Word。
    parser = argparse.ArgumentParser(
        prog="panflow",
        description="Render JSON code blocks into HTML and convert Markdown to Word via pandoc.",
    )
    # 子命令拆分成 render / convert，便于单独调试各阶段。
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    # 为了让 `panflow demo.md` 这种最短命令成立，这里把裸参数归一化成 convert。
    normalized_argv = _normalize_argv_for_default_convert(raw_argv)
    args = parser.parse_args(normalized_argv)
    project_root = Path.cwd()

    if args.command in {"render", "r"}:
        # render 只负责产出中间 HTML/Markdown，不触发 pandoc。
        config = resolve_runtime_config(project_root, args.config)
        output_path = args.output or args.input.with_name(f"{args.input.stem}.rendered.html")
        render_markdown_file(args.input, output_path, config)
        print(f"Rendered output written to {output_path}")
        return 0

    if args.command in {"convert", "c"}:
        # convert 是主链路：先渲染，再转换成 docx。
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

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _normalize_argv_for_default_convert(argv: list[str] | None) -> list[str] | None:
    # 用户省略子命令时，自动把调用视为 convert，降低日常使用成本。
    if argv is None:
        return None
    if not argv:
        return argv
    if argv[0] in {"render", "r", "convert", "c", "-h", "--help"}:
        return argv
    return ["convert", *argv]
