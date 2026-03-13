from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from panflow_service.companion import build_document_result, render_heading
from panflow_service import cli as cli_module
from panflow_service.config import PandocConfig, ProjectConfig, discover_default_config, load_project_config, render_config_toml
from panflow_service.converter import MarkdownRenderError, render_markdown_text
from panflow_service.document_processor import discover_companion_document, parse_markdown_document, render_with_companion_processor
from panflow_service.docx_postprocess import apply_html_table_styles_to_docx
from panflow_service.main import convert_markdown_file
from panflow_service.pandoc import build_pandoc_command
from panflow_service.registry import RendererRegistry


class ConverterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.config = discover_default_config(self.project_root)
        # 测试统一复用默认配置扫描结果，避免每个用例自己拼 renderer 映射。
        self.registry = RendererRegistry(self.config.renderers)

    def test_render_markdown_replaces_json_callout_block(self) -> None:
        markdown = (
            "# Demo\n\n"
            "```json callout\n"
            '{"title": "提示", "body": "已替换", "tone": "info"}\n'
            "```\n"
        )

        rendered = render_markdown_text(markdown, self.registry)

        self.assertIn('class="pf-callout pf-callout-info"', rendered)
        self.assertIn("<strong>提示</strong>", rendered)
        self.assertNotIn("```json callout", rendered)

    def test_numeric_renderer_key_works_for_business_table(self) -> None:
        markdown = (
            "```json:1\n"
            '{'
            '"colgroup":["20%","80%"],'
            '"table_style":{"width":"100%","border":"1px solid #000000","border_collapse":"collapse","line_height":"1.6"},'
            '"rows":[['
            '{"text":"字段","text_align":"center","vertical_align":"middle","line_height":"1.6","padding":"6pt 8pt","border":"1px solid #000000","bold":true},'
            '{"text":"值","text_align":"center","vertical_align":"middle","line_height":"1.6","padding":"6pt 8pt","border":"1px solid #000000","bold":true}'
            '],['
            '{"text":"用例名称","text_align":"center","vertical_align":"middle","padding":"6pt 8pt","border":"1px solid #000000","bold":true},'
            '{"text":"BCMI评估数据接口适配建模","vertical_align":"middle","line_height":"1.6","padding":"6pt 8pt","border":"1px solid #000000"}'
            "]]}\n"
            "```"
        )

        rendered = render_markdown_text(markdown, self.registry)

        self.assertIn('class="pf-table pf-testcase-table"', rendered)
        self.assertIn("border-collapse: collapse;", rendered)
        self.assertIn("border: 1px solid #000000;", rendered)
        self.assertIn("vertical-align: middle;", rendered)
        self.assertIn("line-height: 1.6;", rendered)
        self.assertIn("padding: 6pt 8pt;", rendered)
        self.assertIn("<strong>字段</strong>", rendered)
        self.assertIn("BCMI评估数据接口适配建模", rendered)

    def test_invalid_json_raises_clear_error(self) -> None:
        markdown = "```json callout\n{invalid json}\n```"

        with self.assertRaises(MarkdownRenderError) as exc:
            render_markdown_text(markdown, self.registry)

        self.assertIn("Invalid JSON", str(exc.exception))

    def test_render_config_toml_lists_renderer_keys(self) -> None:
        toml_text = render_config_toml(
            self.config.renderers,
            base_dir=self.project_root,
        )

        self.assertIn("[renderers]", toml_text)
        self.assertIn('1 = "src/panflow_service/renderers/testcase_table.py"', toml_text)
        self.assertIn('callout = "src/panflow_service/renderers/callout.py"', toml_text)
        self.assertIn('metrics = "src/panflow_service/renderers/metrics.py"', toml_text)
        self.assertIn('testcase_table = "src/panflow_service/renderers/testcase_table.py"', toml_text)

    def test_build_pandoc_command_includes_reference_doc(self) -> None:
        command = build_pandoc_command(
            Path("input.md"),
            Path("output.docx"),
            input_format="gfm+raw_html",
            reference_doc=Path("templates/reference.docx"),
        )

        self.assertEqual(command[0], "pandoc")
        self.assertIn("gfm+raw_html", command)
        self.assertIn("--reference-doc", command)
        self.assertEqual(command[-1], str(Path("templates/reference.docx")))

    def test_cli_defaults_to_convert_when_subcommand_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "demo.md"
            input_path.write_text("# demo\n", encoding="utf-8")
            config = ProjectConfig(
                project_root=temp_path,
                renderers={},
                pandoc=PandocConfig(),
            )

            with patch.object(cli_module, "resolve_runtime_config", return_value=config), patch.object(
                cli_module,
                "convert_markdown_file",
            ) as mocked_convert:
                exit_code = cli_module.main([str(input_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(mocked_convert.called)
            self.assertEqual(mocked_convert.call_args.args[1], input_path.with_suffix(".docx"))

    def test_cli_render_uses_default_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "demo.md"
            input_path.write_text("# demo\n", encoding="utf-8")
            config = ProjectConfig(
                project_root=temp_path,
                renderers={},
                pandoc=PandocConfig(),
            )

            with patch.object(cli_module, "resolve_runtime_config", return_value=config), patch.object(
                cli_module,
                "render_markdown_file",
            ) as mocked_render:
                exit_code = cli_module.main(["render", str(input_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(mocked_render.called)
            self.assertEqual(mocked_render.call_args.args[1], input_path.with_name("demo.rendered.html"))

    def test_exported_config_can_be_reloaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            toml_text = render_config_toml(
                self.config.renderers,
                base_dir=temp_path,
            )
            config_path = Path(temp_dir) / "panflow.toml"
            config_path.write_text(toml_text, encoding="utf-8")

            reloaded = load_project_config(config_path)
            self.assertIn("callout", reloaded.renderers)
            self.assertEqual(
                reloaded.renderers["callout"].name,
                "callout.py",
            )

    def test_discover_default_config_uses_bundled_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir)
            renderers_dir = bundle_root / "renderers"
            renderers_dir.mkdir()
            (renderers_dir / "demo.py").write_text(
                "\n".join(
                    [
                        'RENDER_KEYS = ["demo"]',
                        "",
                        "def render(payload, context):",
                        '    return "<p>demo</p>"',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )
            templates_dir = bundle_root / "templates"
            templates_dir.mkdir()
            (templates_dir / "reference.docx").write_bytes(b"docx")
            bin_dir = bundle_root / "bin"
            bin_dir.mkdir()
            (bin_dir / ("pandoc.exe" if sys.platform.startswith("win") else "pandoc")).write_text(
                "#!/bin/sh\n",
                encoding="utf-8",
            )

            with patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                config = discover_default_config(bundle_root / "workspace")

            self.assertIn("demo", config.renderers)
            self.assertEqual(config.renderers["demo"].name, "demo.py")
            self.assertEqual(config.pandoc.reference_doc, (templates_dir / "reference.docx").resolve())
            self.assertEqual(config.pandoc.binary, str((bin_dir / ("pandoc.exe" if sys.platform.startswith("win") else "pandoc")).resolve()))

    def test_renderer_can_override_reference_doc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            renderer_path = temp_path / "hooked.py"
            renderer_path.write_text(
                "\n".join(
                    [
                        'RENDER_KEYS = ["hooked"]',
                        "from pathlib import Path",
                        "",
                        "def render(payload, context):",
                        '    return "<p>ok</p>"',
                        "",
                        "def prepare_reference_doc(reference_doc, blocks, context):",
                        '    target = Path(context["temp_dir"]) / "hooked-reference.docx"',
                        '    target.write_bytes(b"hooked")',
                        "    return target",
                    ],
                )
                + "\n",
                encoding="utf-8",
            )
            input_path = temp_path / "input.md"
            input_path.write_text('```json hooked\n{}\n```\n', encoding="utf-8")
            base_reference_doc = temp_path / "reference.docx"
            base_reference_doc.write_bytes(b"base")
            output_path = temp_path / "output.docx"

            config = ProjectConfig(
                project_root=temp_path,
                renderers={"hooked": renderer_path},
                pandoc=PandocConfig(
                    binary="pandoc",
                    reference_doc=base_reference_doc,
                ),
            )

            with patch("panflow_service.main.run_pandoc") as mocked_run_pandoc:
                convert_markdown_file(input_path, output_path, config)

            self.assertTrue(mocked_run_pandoc.called)
            called_reference_doc = mocked_run_pandoc.call_args.kwargs["reference_doc"]
            self.assertEqual(called_reference_doc.name, "hooked-reference.docx")

    def test_parse_markdown_document_supports_toml_front_matter(self) -> None:
        document = parse_markdown_document(
            "+++\n"
            'template_style = "business"\n'
            "+++\n"
            "# Body\n",
        )

        self.assertEqual(document.metadata["template_style"], "business")
        self.assertEqual(document.body, "# Body\n")
        self.assertEqual(len(document.sections), 1)
        self.assertEqual(document.sections[0].metadata["template_style"], "business")

    def test_parse_markdown_document_supports_multiple_template_sections(self) -> None:
        document = parse_markdown_document(
            "+++\n"
            'template_style = "business"\n'
            "+++\n"
            "# A\n"
            "+++\n"
            'template_style = "business_alt"\n'
            "+++\n"
            "# B\n",
        )

        self.assertEqual(document.metadata["template_style"], "business")
        self.assertEqual(len(document.sections), 2)
        self.assertEqual(document.sections[0].metadata["template_style"], "business")
        self.assertEqual(document.sections[1].metadata["template_style"], "business_alt")
        self.assertEqual(document.sections[0].body, "# A\n")
        self.assertEqual(document.sections[1].body, "# B\n")
        self.assertEqual(document.body, "# A\n# B\n")

    def test_build_document_result_uses_standard_protocol(self) -> None:
        result = build_document_result(
            "<h1>Demo</h1>\n",
            template_style="business",
            font_family="仿宋",
            font_size="12pt",
        )

        self.assertEqual(result["content"], "<h1>Demo</h1>\n")
        self.assertEqual(result["input_format"], "html")
        self.assertEqual(result["template_style"], "business")
        self.assertEqual(result["font_family"], "仿宋")
        self.assertEqual(result["font_size"], "12pt")

    def test_render_heading_supports_element_level_fonts(self) -> None:
        html = render_heading(
            "标题",
            level=1,
            font_family="黑体",
            font_size="18pt",
            font_weight="700",
            text_align="center",
        )

        self.assertIn("<h1", html)
        self.assertIn("font-family: 黑体;", html)
        self.assertIn("font-size: 18pt;", html)
        self.assertIn("font-weight: 700;", html)
        self.assertIn("text-align: center;", html)

    def test_companion_processor_uses_examples_same_name_py(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# content\n",
                encoding="utf-8",
            )
            (examples_dir / "a.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<h1>done</h1>", "input_format": "html", "font_family": "宋体", "font_size": "14pt"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )

            companion = discover_companion_document(markdown_path)
            result = render_with_companion_processor(
                companion,
                cli_reference_doc=None,
                project_root=temp_path,
                output_path=temp_path / "out.docx",
                temp_dir=temp_path / "tmp",
            )

            self.assertIn("font-family: 宋体;", result.content)
            self.assertIn("font-size: 14pt;", result.content)
            self.assertIn("<h1>done</h1>", result.content)
            self.assertEqual(result.input_format, "html")
            self.assertIsNone(result.reference_doc)

    def test_companion_processor_dispatches_sections_by_template_style_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# first\n"
                "+++\n"
                'template_style = "business_alt"\n'
                "+++\n"
                "# second\n",
                encoding="utf-8",
            )
            (examples_dir / "business.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<div>business-section</div>", "input_format": "html", "template_style": "business"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )
            (examples_dir / "business_alt.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<div>business-alt-section</div>", "input_format": "html", "template_style": "business_alt"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )

            companion = discover_companion_document(markdown_path)
            result = render_with_companion_processor(
                companion,
                cli_reference_doc=None,
                project_root=temp_path,
                output_path=temp_path / "out.docx",
                temp_dir=temp_path / "tmp",
            )

            self.assertIn("business-section", result.content)
            self.assertIn("business-alt-section", result.content)
            self.assertIn("page-break-before: always;", result.content)
            self.assertEqual(result.input_format, "html")
            self.assertIsNone(result.reference_doc)

    def test_convert_uses_template_style_processor_even_without_same_name_py(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# first\n",
                encoding="utf-8",
            )
            (examples_dir / "business.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<div>styled-section</div>", "input_format": "html", "template_style": "business"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )
            config = ProjectConfig(
                project_root=temp_path,
                renderers={},
                pandoc=PandocConfig(binary="pandoc"),
            )

            with patch("panflow_service.main.run_pandoc") as mocked_run_pandoc:
                convert_markdown_file(markdown_path, temp_path / "out.docx", config)

            self.assertTrue(mocked_run_pandoc.called)
            self.assertEqual(mocked_run_pandoc.call_args.kwargs["input_format"], "html")

    def test_template_style_falls_back_to_same_name_processor_when_style_script_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# first\n"
                "+++\n"
                'template_style = "business_alt"\n'
                "+++\n"
                "# second\n",
                encoding="utf-8",
            )
            (examples_dir / "a.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": f"<div>{metadata[\'template_style\']}-fallback</div>", "input_format": "html", "template_style": metadata.get("template_style")}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )

            companion = discover_companion_document(markdown_path)
            stderr = StringIO()
            with redirect_stderr(stderr):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            self.assertIn("business-fallback", result.content)
            self.assertIn("business_alt-fallback", result.content)
            self.assertIn("falling back to the same-name companion processor", stderr.getvalue())
            self.assertIsNone(result.reference_doc)

    def test_companion_processor_uses_bundled_examples_when_project_examples_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bundle_root = temp_path / "bundle"
            examples_dir = bundle_root / "examples"
            examples_dir.mkdir(parents=True)
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# first\n",
                encoding="utf-8",
            )
            (examples_dir / "business.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<div>bundled-business</div>", "input_format": "html", "template_style": "business"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )

            companion = discover_companion_document(markdown_path)
            with patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            self.assertIn("bundled-business", result.content)
            self.assertEqual(result.input_format, "html")

    def test_unknown_template_style_only_prints_warning_and_skips_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            markdown_path.write_text(
                "+++\n"
                'template_style = "missing_style"\n'
                "+++\n"
                "# skipped\n"
                "+++\n"
                'template_style = "business"\n'
                "+++\n"
                "# kept\n",
                encoding="utf-8",
            )
            (examples_dir / "business.py").write_text(
                "\n".join(
                    [
                        "def render_document(markdown, metadata, config, context):",
                        '    return {"content": "<div>kept-section</div>", "input_format": "html", "template_style": "business"}',
                    ],
                )
                + "\n",
                encoding="utf-8",
            )

            companion = discover_companion_document(markdown_path)
            stderr = StringIO()
            with redirect_stderr(stderr):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            self.assertIn("unknown template_style 'missing_style'", stderr.getvalue())
            self.assertIn("kept-section", result.content)
            self.assertNotIn("skipped", result.content)
            self.assertIsNone(result.reference_doc)

    def test_business_markdown_companion_processor_renders_table_html(self) -> None:
        business_md = self.project_root / "examples" / "business.md"
        companion = discover_companion_document(business_md)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = render_with_companion_processor(
                companion,
                cli_reference_doc=None,
                project_root=self.project_root,
                output_path=Path(temp_dir) / "out.docx",
                temp_dir=Path(temp_dir),
            )

        self.assertEqual(result.input_format, "html")
        self.assertEqual(len(companion.document.sections), 2)
        self.assertGreaterEqual(result.content.count("font-family:"), 6)
        self.assertIn("<h1", result.content)
        self.assertIn('data-template-style="business"', result.content)
        self.assertIn('data-template-style="business_alt"', result.content)
        self.assertIn('class="pf-section pf-section-business"', result.content)
        self.assertIn('class="pf-section pf-section-business_alt"', result.content)
        self.assertIn('page-break-before: always;', result.content)
        self.assertGreaterEqual(result.content.count('class="pf-table pf-testcase-table"'), 2)
        self.assertIn('class="pf-table pf-testcase-table"', result.content)
        self.assertIn("border-collapse: collapse;", result.content)
        self.assertIn("border: 1px solid #000000;", result.content)
        self.assertIn("vertical-align: middle;", result.content)
        self.assertIn("line-height: 1.6;", result.content)
        self.assertIn("padding: 6pt 8pt;", result.content)
        self.assertIn("BCMI评估数据接口适配建模", result.content)
        self.assertIsNone(result.reference_doc)

    def test_docx_postprocess_writes_real_table_borders_from_html(self) -> None:
        html = (
            '<table style="width: 100%; border: 1px solid #000000; border-collapse: collapse; table-layout: fixed; line-height: 1.6;">'
            "<tbody>"
            '<tr><td style="text-align: center; vertical-align: middle; line-height: 1.6; padding: 6pt 8pt; border: 1px solid #000000;">单元格</td></tr>'
            "</tbody>"
            "</table>"
        )
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            "<w:tbl>"
            "<w:tblPr><w:tblStyle w:val=\"Table\" /></w:tblPr>"
            "<w:tr>"
            "<w:tc><w:tcPr /><w:p><w:pPr /><w:r><w:t>单元格</w:t></w:r></w:p></w:tc>"
            "</w:tr>"
            "</w:tbl>"
            "</w:body>"
            "</w:document>"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "table.docx"
            with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as docx_file:
                docx_file.writestr("word/document.xml", document_xml)

            changed = apply_html_table_styles_to_docx(html, docx_path)

            self.assertTrue(changed)
            with ZipFile(docx_path, "r") as docx_file:
                updated_xml = docx_file.read("word/document.xml").decode("utf-8")

        self.assertIn("w:tblBorders", updated_xml)
        self.assertIn('w:val="single"', updated_xml)
        self.assertIn('w:color="000000"', updated_xml)
        self.assertIn("w:tcBorders", updated_xml)
        self.assertIn('w:vAlign w:val="center"', updated_xml)
        self.assertIn('w:spacing w:line="384" w:lineRule="auto"', updated_xml)
        self.assertIn('w:trHeight w:val="384" w:hRule="atLeast"', updated_xml)
        self.assertIn('w:top w:w="120" w:type="dxa"', updated_xml)
        self.assertIn('w:left w:w="160" w:type="dxa"', updated_xml)
        self.assertNotIn("w:tblStyle", updated_xml)


if __name__ == "__main__":
    unittest.main()
