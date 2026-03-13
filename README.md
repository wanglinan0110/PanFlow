# PanFlow

一个离线优先的 Markdown 转 Word 工具。

当前工程的主链路是：

- `md` 用 TOML front matter 声明每个 section 的 `template_style`
- PanFlow 固定去 `examples/` 下查找对应的 `*.py` 处理脚本
- `*.py` 直接生成用于 Word 的 HTML，字体、边框、行高、对齐都在脚本里定义
- `pandoc` 只负责 `HTML -> docx`
- 对复杂表格，再补一层 docx 后处理，把边框、行高、对齐和字体写成真实 Word 样式

## 快速开始

环境要求：

- Python 3.11+
- 本机已安装 `pandoc`

最常用命令：

```bash
# 直接生成同名 Word
python3 run_panflow.py examples/business.md

# 指定输出路径
python3 run_panflow.py examples/business.md -o build/business.docx

# 只看 py 生成的中间 HTML
python3 run_panflow.py render examples/business.md

# 导出全局 JSON renderer 配置
python3 run_panflow.py export-config -o panflow.generated.toml
```

默认情况下：

- 省略子命令时会自动走 `convert`
- `render` 默认输出 `同名.rendered.html`
- `convert` 默认输出 `同名.docx`

## 打包应用

仓库里已经补了一个 PyInstaller 打包脚本：[build_app.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/scripts/build_app.py#L1)。

先安装打包依赖：

```bash
python3 -m pip install ".[build]"
```

打包成目录版应用：

```bash
python3 scripts/build_app.py --mode onedir
```

输出目录默认在：

```text
dist/PanFlow/
```

如果你想把本机 `pandoc` 也一起打进应用里，让目标机器不再单独安装 `pandoc`，可以这样打包：

```bash
python3 scripts/build_app.py --mode onedir --pandoc-binary "$(which pandoc)"
```

说明：

- 打包脚本会把 `examples/`、`templates/`、内置 `renderers/` 一起带进应用
- 应用启动后会优先查找内置资源，所以打包后依然能命中 `examples/business.py`
- 如果同时打包了 `pandoc`，应用会优先使用内置 `bin/pandoc`

### GitHub tag 自动产出 exe

仓库里现在带有 Windows 发布工作流：[release-windows.yml](/Users/wanglinan/Documents/huaru/AI/PanFlow/.github/workflows/release-windows.yml#L1)。

当你推送形如 `v*` 的 tag 时，GitHub Actions 会自动：

- 在 `windows-latest` 上安装 Python 3.11
- 安装 `pandoc`
- 执行测试
- 用 `PyInstaller` 构建单文件版 `PanFlow.exe`
- 把产物上传到对应的 GitHub Release

常用发布命令：

```bash
git add .
git commit -m "Add Windows release workflow"
git tag v0.1.0
git push origin main
git push origin v0.1.0
```

发布完成后，你可以在 GitHub 的 Release 页面下载：

```text
PanFlow-v0.1.0-windows-x64.exe
```

## 当前工作方式

### 1. Section 分发

`md` 文件通过 TOML front matter 分段：

```markdown
+++
template_style = "business"
+++
# 第一段

+++
template_style = "business_alt"
+++
# 第二段
```

PanFlow 会按 section 逐段处理：

1. 优先查找 `examples/<template_style>.py`
2. 如果没找到，再回退到 `examples/<md同名>.py`
3. 如果仍然没找到，这一段会在控制台打印警告，但不会影响其他 section 继续生成

这套逻辑在 [document_processor.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/document_processor.py#L120)。

### 2. Python 脚本产出 HTML

每个样式脚本都需要暴露：

```python
def render_document(markdown, metadata, config, context):
    ...
```

推荐返回：

```python
{
    "content": "<h1>...</h1>",
    "input_format": "html",
    "template_style": "business",
}
```

辅助函数在 [companion.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/companion.py#L1)：

- `build_document_result(...)`
- `render_heading(...)`
- `build_inline_style(...)`

### 3. pandoc 只做转换

当前 companion 链路里，`py` 产出的 HTML 会直接交给 `pandoc`：

- 输入格式：`html`
- 输出格式：`docx`
- 可选模板：`--reference-doc`

对应实现见 [main.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/main.py#L120) 和 [pandoc.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/pandoc.py#L1)。

### 4. docx 后处理

`pandoc` 对复杂 HTML 表格的 CSS 支持不完整，所以生成完 `.docx` 后，PanFlow 会再写回真实 Word 样式：

- 表格边框
- 单元格边框
- 垂直居中
- 行高
- 字体
- 字号
- 加粗
- 单元格内边距

对应实现见 [docx_postprocess.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/docx_postprocess.py#L1)。

## 示例文件

当前仓库里真实存在并可直接运行的示例是：

- Markdown 示例：[business.md](/Users/wanglinan/Documents/huaru/AI/PanFlow/examples/business.md)
- 第一套样式脚本：[business.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/examples/business.py#L1)
- 第二套样式脚本：[business_alt.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/examples/business_alt.py#L1)

`business.md` 里有两个 section：

- `template_style = "business"` 会命中 `examples/business.py`
- `template_style = "business_alt"` 会命中 `examples/business_alt.py`

## 表格样式怎么定义

复杂表格的样式不再依赖外部样式表，也不依赖 companion TOML。

表格相关样式直接在 `py` 里写进 HTML payload，例如：

- 表格级：
  - `width`
  - `border`
  - `border_collapse`
  - `table_layout`
  - `line_height`
  - `font_family`
  - `font_size`
- 单元格级：
  - `text_align`
  - `vertical_align`
  - `line_height`
  - `padding`
  - `border`
  - `font_family`
  - `font_size`
  - `font_weight`

参考实现见 [testcase_table.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/renderers/testcase_table.py#L1)。

## 标题和字体怎么定义

`# / ## / ###` 对应的标题样式由样式脚本自己决定，不由 Markdown 本身决定。

当前业务样例里是这样做的：

- [business.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/examples/business.py#L27) 里定义 `STYLE_PRESETS`
- [business_alt.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/examples/business_alt.py#L27) 里定义另一套 `STYLE_PRESETS`
- 再通过 `render_heading(...)` 把字体、字号、粗细、对齐写进 HTML

如果你要改带 `#` 的标题样式，改对应脚本里的：

- `title`
- `module`
- `case_title`

## 全局配置

工程里还保留一份全局配置 [panflow.toml](/Users/wanglinan/Documents/huaru/AI/PanFlow/panflow.toml#L1)，它只负责两类事情：

1. 配置 `pandoc`
2. 配置“全局 JSON 代码块 renderer”模式

当前内容大致是：

```toml
[pandoc]
binary = "pandoc"
reference_doc = "templates/reference.docx"

[renderers]
1 = "src/panflow_service/renderers/testcase_table.py"
callout = "src/panflow_service/renderers/callout.py"
json_table = "src/panflow_service/renderers/testcase_table.py"
metrics = "src/panflow_service/renderers/metrics.py"
table = "src/panflow_service/renderers/testcase_table.py"
testcase_table = "src/panflow_service/renderers/testcase_table.py"
```

说明：

- `panflow.toml` 仍然有用
- 它不再参与 `examples/*.py` 的 section 分发
- 但它仍然影响默认 `pandoc` 路径、默认 `reference.docx`，以及 JSON 代码块渲染模式

配置读取逻辑在 [config.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/config.py#L1)。

## reference.docx 的作用

[reference.docx](/Users/wanglinan/Documents/huaru/AI/PanFlow/templates/reference.docx) 现在仍然是默认 Word 模板。

它主要负责兜底这些内容：

- 页面大小
- 页边距
- 默认段落样式
- Word 原生标题样式
- 没有被 `py + docx 后处理` 显式覆盖的部分

如果 `py` 返回了自己的 `reference_doc`，或者命令行显式传了 `--reference-doc`，就会覆盖默认模板。

## 目录结构

```text
PanFlow/
├── examples/
│   ├── business.md
│   ├── business.py
│   └── business_alt.py
├── panflow.toml
├── pyproject.toml
├── README.md
├── run_panflow.py
├── src/
│   └── panflow_service/
│       ├── cli.py
│       ├── companion.py
│       ├── config.py
│       ├── converter.py
│       ├── document_processor.py
│       ├── docx_postprocess.py
│       ├── main.py
│       ├── pandoc.py
│       ├── registry.py
│       └── renderers/
│           ├── callout.py
│           ├── metrics.py
│           └── testcase_table.py
├── templates/
│   └── reference.docx
└── tests/
    └── test_converter.py
```

## 测试

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

当前测试覆盖了这些关键链路：

- CLI 默认 `convert`
- `template_style -> examples/*.py` 分发
- 同名脚本回退
- 未知 `template_style` 只告警不中断
- HTML 表格样式回填 docx

## 常见排查

### 1. 生成的 Word 没样式

优先检查：

1. `md` 里的 `template_style` 是否和 `examples/*.py` 对得上
2. 实际执行的是否是 `python3 run_panflow.py your.md`
3. `render your.md` 生成的 HTML 里是否已经有字体、边框、行高、对齐

### 2. 表格边框变成虚线

如果 HTML 里已经是实线，但 Word 里看起来还是虚线，通常是因为没经过 docx 后处理，或者查看器显示的是网格线。当前工程已经在 [main.py](/Users/wanglinan/Documents/huaru/AI/PanFlow/src/panflow_service/main.py#L155) 自动补这一步。

### 3. 字体没有按 py 生效

先看 `py` 输出的 HTML 是否真的带了 `font-family / font-size / font-weight`。如果 HTML 正确但 Word 里不对，再检查：

- 对应段落是否已经进入 docx 后处理
- 机器上是否安装了该字体
- `reference.docx` 是否有冲突样式

### 4. 某个 section 没生成

通常是：

- `template_style` 对应的 `examples/<template_style>.py` 不存在
- 同名回退脚本 `examples/<md同名>.py` 也不存在

这时控制台会打印 warning，但其他 section 仍会继续生成。

## 开发建议

如果你要新增一套业务样式，最简单的做法是：

1. 在 `md` 中新增一个 `template_style`
2. 在 `examples/` 新建同名 `*.py`
3. 在脚本里直接定义标题字体、表格样式、单元格边框和行高
4. 先跑 `render` 看 HTML
5. 再跑 `convert` 看最终 Word
