# PanFlow

一个离线优先的 Markdown 转 Word 工具。

PanFlow 的核心思路不是“把 Markdown 直接丢给 pandoc”，而是先用 Python 脚本把业务内容渲染成更可控的 HTML，再交给 `pandoc` 生成 `.docx`，最后对复杂表格做一次 Word 样式回填。这样更适合需要精细控制字体、边框、行高、对齐和分页的文档场景。

## 特性

- 支持 TOML front matter 按 section 分发不同模板脚本
- 支持 `examples/*.py` 直接输出用于 Word 的 HTML
- 支持 JSON 代码块 renderer
- 支持 `reference.docx` 作为默认 Word 模板
- 支持对复杂表格做 `.docx` 后处理，补齐真实 Word 边框和单元格样式
- 支持 PyInstaller 打包
- 支持推送 `v*` tag 后由 GitHub Actions 自动产出 Windows `exe`

## 环境要求

- Python 3.12+
- 本机安装 `pandoc`

如果你使用仓库发布页下载的 Windows `exe`，则不需要单独准备 Python 环境；发布产物会把 `pandoc` 一起打进去。

## 快速开始

直接从源码运行：

```bash
python3 run_panflow.py examples/business.md
```

指定输出路径：

```bash
python3 run_panflow.py examples/business.md -o build/business.docx
```

只生成中间 HTML：

```bash
python3 run_panflow.py render examples/business.md
```

默认行为：

- 省略子命令时会自动走 `convert`
- `render` 默认输出 `同名.rendered.html`
- `convert` 默认输出 `同名.docx`

## 安装方式

开发时可以直接用 `run_panflow.py`，也可以安装成命令行工具：

```bash
python3 -m pip install -e .
panflow examples/business.md
```

如果只是打包：

```bash
python3 -m pip install ".[build]"
```

## 工作流

当前主链路如下：

1. Markdown 按 TOML front matter 切分 section
2. 每个 section 根据 `template_style` 选择对应的 `examples/*.py`
3. Python 模板脚本输出 HTML
4. `pandoc` 负责 `html -> docx`
5. 对复杂表格执行 `.docx` 后处理

### Section 分发规则

Markdown 示例：

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

PanFlow 会按下面的顺序查找 companion 脚本：

1. `examples/<template_style>.py`
2. `examples/<markdown同名>.py`
3. 如果都不存在，打印警告并跳过该 section

当前仓库里的示例文件：

- `examples/business.md`
- `examples/business.py`
- `examples/business_alt.py`

## 模板脚本

模板脚本需要暴露：

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

辅助函数在 `src/panflow_service/companion.py` 中，常用的有：

- `build_document_result(...)`
- `render_heading(...)`
- `build_inline_style(...)`

### 样式控制

PanFlow 的样式控制主要分成三层：

- Python 模板脚本决定标题、字体、字号、表格 HTML 和分页
- `reference.docx` 提供页面设置和基础 Word 样式
- `.docx` 后处理修正 pandoc 对复杂表格支持不足的部分

复杂表格通常直接在 HTML 中写这些属性：

- `border`
- `border_collapse`
- `table_layout`
- `line_height`
- `padding`
- `text_align`
- `vertical_align`
- `font_family`
- `font_size`
- `font_weight`

内置 renderer 位于：

- `src/panflow_service/renderers/testcase_table.py`
- `src/panflow_service/renderers/callout.py`
- `src/panflow_service/renderers/metrics.py`

## 配置文件

默认配置文件是仓库根目录的 `panflow.toml`：

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

它主要负责两类事情：

- 指定 `pandoc` 可执行文件和默认 `reference.docx`
- 指定 JSON 代码块 renderer 映射

如果你通过 `--config` 显式传入配置文件，运行时会使用你指定的那一份。

## CLI

安装后可使用命令：

```bash
panflow convert input.md -o output.docx
panflow render input.md -o output.rendered.html
```

常用参数：

- `--config`：指定配置文件
- `--intermediate-output`：保留中间渲染产物
- `--reference-doc`：覆盖默认 Word 模板

开发时同样可以继续使用：

```bash
python3 run_panflow.py ...
```

## 打包

仓库内置了 PyInstaller 打包脚本：

```bash
python3 scripts/build_app.py --mode onedir
```

输出目录默认在：

```text
dist/PanFlow/
```

如果要打单文件：

```bash
python3 scripts/build_app.py --mode onefile
```

如果你希望把本机 `pandoc` 一起打包进去：

```bash
python3 scripts/build_app.py --mode onefile --pandoc-binary "$(which pandoc)"
```

打包脚本会自动带上：

- `examples/`
- `templates/`
- `src/panflow_service/renderers/`

## GitHub 发布

仓库包含 Windows 发布工作流：

- `.github/workflows/release-windows.yml`

当你推送形如 `v*` 的 tag 时，GitHub Actions 会自动：

1. 在 `windows-latest` 上安装 Python 3.12
2. 安装 `pandoc`
3. 执行测试
4. 构建单文件 `PanFlow.exe`
5. 上传 artifact
6. 发布到对应 GitHub Release

发布命令示例：

```bash
git add .
git commit -m "Prepare release"
git push origin main
git tag v0.1.3
git push origin v0.1.3
```

发布成功后，Release 页面会出现类似这样的附件：

```text
PanFlow-v0.1.3-windows-x64.exe
```

## 测试

本地运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

当前测试覆盖了这些关键链路：

- CLI 默认行为
- renderer 映射
- companion section 分发
- `pandoc` 命令组装
- bundled 资源发现
- `.docx` 表格后处理

## 项目结构

```text
PanFlow/
├── examples/
├── scripts/
│   └── build_app.py
├── src/panflow_service/
│   ├── cli.py
│   ├── main.py
│   ├── config.py
│   ├── pandoc.py
│   ├── document_processor.py
│   ├── docx_postprocess.py
│   └── renderers/
├── templates/
│   └── reference.docx
├── tests/
├── panflow.toml
└── run_panflow.py
```

## 适用场景

PanFlow 更适合下面这类文档：

- 有明确业务模板的 Markdown 转 Word
- 需要固定字体、字号、边框和分页规则的交付文档
- 需要 Python 参与渲染逻辑的文档生成流程
- 需要把复杂表格稳定落到 Word 的场景
