"""核心转换链路测试。

这些用例覆盖 CLI、renderer、companion 分发、打包资源发现以及 docx 后处理。
"""

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
from panflow_service.config import PandocConfig, ProjectConfig, discover_default_config
from panflow_service.converter import MarkdownRenderError, render_markdown_text
from panflow_service.document_processor import discover_companion_document, parse_markdown_document, render_with_companion_processor
from panflow_service.docx_postprocess import apply_html_table_styles_to_docx
from panflow_service.main import convert_markdown_file
from panflow_service.pandoc import build_pandoc_command
from panflow_service.registry import RendererRegistry


class ConverterTestCase(unittest.TestCase):
    # 统一在这个测试类里覆盖“从 Markdown 到 HTML/Word”的主要行为。
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.config = discover_default_config(self.project_root)
        # 测试统一复用默认配置扫描结果，避免每个用例自己拼 renderer 映射。
        self.registry = RendererRegistry(self.config.renderers)

    # 这一组测试关注“JSON 代码块 renderer”链路，验证 markdown 中的 fenced block
    # 是否能被正确识别、解析并替换成 HTML。
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
        # 原始 fenced block 应该已经被完全替换掉，而不是残留在输出中。
        self.assertNotIn("```json callout", rendered)

    def test_numeric_renderer_key_works_for_business_table(self) -> None:
        # 这里覆盖历史兼容语法：```json:1 应该命中数字 key 对应的 renderer。
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
        # 下面这些断言确保表格级和单元格级样式都已落到 HTML，后续 pandoc/docx
        # 后处理才有足够信息写回 Word。
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

        # 报错信息要尽量可定位，至少能一眼看出是 JSON 格式本身有问题。
        self.assertIn("Invalid JSON", str(exc.exception))

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
        # 这里用 str(Path(...))，保证断言在 Windows 和 POSIX 上都成立。
        self.assertEqual(command[-1], str(Path("templates/reference.docx")))

    # 这一组测试验证 CLI 默认行为，重点是“用户少敲命令时是否还能走对分支”。
    def test_cli_defaults_to_convert_when_subcommand_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # 这里不需要真实业务内容，只需要一个存在的 markdown 文件让 CLI 完成参数解析。
            input_path = temp_path / "demo.md"
            input_path.write_text("# demo\n", encoding="utf-8")
            config = ProjectConfig(
                project_root=temp_path,
                renderers={},
                pandoc=PandocConfig(),
            )

            # 通过 patch 隔离真正的渲染流程，只观察 CLI 最终把参数路由到哪条函数调用。
            with patch.object(cli_module, "resolve_runtime_config", return_value=config), patch.object(
                cli_module,
                "convert_markdown_file",
            ) as mocked_convert:
                exit_code = cli_module.main([str(input_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(mocked_convert.called)
            # 默认输出路径应该和 CLI 文档约定保持一致。
            self.assertEqual(mocked_convert.call_args.args[1], input_path.with_suffix(".docx"))

    def test_cli_render_uses_default_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # 和 convert 场景一样，这里只需要最小输入文件，不需要真实模板环境。
            input_path = temp_path / "demo.md"
            input_path.write_text("# demo\n", encoding="utf-8")
            config = ProjectConfig(
                project_root=temp_path,
                renderers={},
                pandoc=PandocConfig(),
            )

            # 同样只测试 CLI 路由与默认输出路径，不执行真实 render。
            with patch.object(cli_module, "resolve_runtime_config", return_value=config), patch.object(
                cli_module,
                "render_markdown_file",
            ) as mocked_render:
                exit_code = cli_module.main(["render", str(input_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(mocked_render.called)
            # render 子命令默认产出 `*.rendered.html`，这里直接锁定这个约定。
            self.assertEqual(mocked_render.call_args.args[1], input_path.with_name("demo.rendered.html"))

    # 这个测试模拟“打包后运行”的环境，确保资源查找不会只在源码目录下工作。
    def test_discover_default_config_uses_bundled_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir)
            # 人工拼出一个最小 bundle 目录结构，模拟 PyInstaller 解包后的资源布局。
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

            # _MEIPASS 是 PyInstaller 运行时用来标识临时解包目录的关键环境变量。
            with patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                config = discover_default_config(bundle_root / "workspace")

            self.assertIn("demo", config.renderers)
            self.assertEqual(config.renderers["demo"].name, "demo.py")
            # 这里同时验证 bundled 的模板和 bundled 的 pandoc 都能被发现。
            self.assertEqual(config.pandoc.reference_doc, (templates_dir / "reference.docx").resolve())
            self.assertEqual(config.pandoc.binary, str((bin_dir / ("pandoc.exe" if sys.platform.startswith("win") else "pandoc")).resolve()))

    # 这一组测试关注 renderer 对 reference.docx 的覆盖能力。
    def test_renderer_can_override_reference_doc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # 动态写一个最小 renderer，专门测试 prepare_reference_doc 钩子是否生效。
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
            # markdown 中只保留一个 hooked block，让测试聚焦在 reference_doc 覆盖逻辑。
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
            # 断言目标是：最终送进 pandoc 的模板已经变成 renderer 钩子返回的新文件。
            self.assertEqual(called_reference_doc.name, "hooked-reference.docx")

    # 这一组测试专门验证 Markdown front matter 切段逻辑。
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

    # 这一组测试覆盖 companion 辅助函数本身，属于模板脚本的基础能力。
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

    # 下面这几组是 companion 模板分发测试。
    # 它们都会临时创建一个“最小工程”，动态写 markdown 和 python 脚本，
    # 然后直接调用 render_with_companion_processor，避免依赖仓库外部状态。
    def test_companion_processor_uses_examples_same_name_py(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            # markdown 文件名是 a.md，下面故意只提供 a.py，验证“同名脚本命中”规则。
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

            # 这里重点验证：同名脚本 a.py 被命中，且字体包装逻辑已经生效。
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
            # 这里构造两段不同 template_style，验证 section 级分发而不是整文件只命中一个脚本。
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

            # 第一段和第二段应该分别命中 business.py / business_alt.py，
            # 两段之间还要自动插入分页占位。
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
            # 这里故意不提供 a.py，只提供 business.py，验证 convert 流程仍能命中 template_style 脚本。
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

            # patch run_pandoc 是为了只观察 convert 前半段路由和参数，不依赖系统 pandoc。
            with patch("panflow_service.main.run_pandoc") as mocked_run_pandoc:
                convert_markdown_file(markdown_path, temp_path / "out.docx", config)

            self.assertTrue(mocked_run_pandoc.called)
            # convert 流程应该识别出 companion 输出是 HTML，并把 input_format 透传给 pandoc。
            self.assertEqual(mocked_run_pandoc.call_args.kwargs["input_format"], "html")

    def test_template_style_falls_back_to_same_name_processor_when_style_script_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            # markdown 声明了 business / business_alt，但 examples/ 中只提供 a.py，
            # 用来验证“缺模板时回退到同名脚本”的容错行为。
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
            # 警告信息写到 stderr，因此这里显式抓取，避免遗漏容错提示是否存在。
            with redirect_stderr(stderr):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            # 当 template_style 对应脚本不存在时，应回退到同名脚本 a.py，而不是直接报错。
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
            # 当前工程目录不创建 examples/，强制资源查找走 bundle 回退路径。
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
            # 通过补丁模拟 PyInstaller 环境，让 resolve_examples_dir 命中 bundle_root。
            with patch.object(sys, "_MEIPASS", str(bundle_root), create=True):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            # 当前工程没有 examples/ 时，应该能回退到 bundle 里的 examples/。
            self.assertIn("bundled-business", result.content)
            self.assertEqual(result.input_format, "html")

    def test_unknown_template_style_only_prints_warning_and_skips_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            examples_dir = temp_path / "examples"
            examples_dir.mkdir()
            markdown_path = temp_path / "a.md"
            # 第一段模板不存在，第二段模板存在；测试目标是“跳过坏段，保留好段”。
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
            # 这里同时验证两个结果：stderr 有告警，HTML 输出仍然有可用 section。
            with redirect_stderr(stderr):
                result = render_with_companion_processor(
                    companion,
                    cli_reference_doc=None,
                    project_root=temp_path,
                    output_path=temp_path / "out.docx",
                    temp_dir=temp_path / "tmp",
                )

            # 未知模板只跳过当前 section，不影响后续已知 section 继续生成。
            self.assertIn("unknown template_style 'missing_style'", stderr.getvalue())
            self.assertIn("kept-section", result.content)
            self.assertNotIn("skipped", result.content)
            self.assertIsNone(result.reference_doc)

    # 这个测试直接走仓库内真实示例文件，目的是锁定“实际业务样例”当前输出长什么样。
    def test_business_markdown_companion_processor_renders_table_html(self) -> None:
        business_md = self.project_root / "examples" / "business.md"
        # 这里不再手写最小工程，而是直接验证仓库自带样例在当前版本下的真实输出。
        companion = discover_companion_document(business_md)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = render_with_companion_processor(
                companion,
                cli_reference_doc=None,
                project_root=self.project_root,
                output_path=Path(temp_dir) / "out.docx",
                temp_dir=Path(temp_dir),
            )

        # 这里是一个“综合性快照断言”：
        # 标题、分页、section class、表格样式和业务文本都应该同时出现。
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

    # 最后一组测试是 docx 后处理，直接验证 Word XML 是否被正确改写。
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
            # 这里手工造一个最小 docx，只包含 document.xml，避免依赖真实 Word 文件夹具。
            with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as docx_file:
                docx_file.writestr("word/document.xml", document_xml)

            changed = apply_html_table_styles_to_docx(html, docx_path)

            self.assertTrue(changed)
            with ZipFile(docx_path, "r") as docx_file:
                updated_xml = docx_file.read("word/document.xml").decode("utf-8")

        # 这里的断言全部针对 Word XML 关键节点，确保样式不是“看起来像生效”，
        # 而是真的被写成了 docx 原生结构。
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
