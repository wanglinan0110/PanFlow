# PanFlow

一个离线优先的 Markdown 转 Word 工具。

PanFlow 的核心思路不是“把 Markdown 直接丢给 pandoc”，而是先用 Python 脚本把业务内容渲染成更可控的 HTML，再交给 `pandoc` 生成 `.docx`，最后对复杂表格做一次 Word 样式回填。这样更适合需要精细控制字体、边框、行高、对齐和分页的文档场景。

## 特性

- 支持 TOML front matter 按 section 分发不同模板脚本
- 支持 `processors/*.py` 直接输出用于 Word 的 HTML
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
python3 run_panflow.py design_doc.md
```

指定输出路径：

```bash
python3 run_panflow.py design_doc.md -o build/design_doc.docx
```

只生成中间 HTML：

```bash
python3 run_panflow.py render design_doc.md
```

默认行为：

- 省略子命令时会自动走 `convert`
- `render` 默认输出 `同名.rendered.html`
- `convert` 默认输出 `同名.docx`

## 安装方式

开发时可以直接用 `run_panflow.py`，也可以安装成命令行工具：

```bash
python3 -m pip install -e .
mdToWord design_doc.md
```

如果只是打包：

```bash
python3 -m pip install ".[build]"
```

## 工作流

当前主链路如下：

1. Markdown 按 TOML front matter 切分 section
2. 每个 section 根据 `template_style` 选择对应的 `processors/*.py`
3. Python 模板脚本输出 HTML
4. `pandoc` 负责 `html -> docx`
5. 对复杂表格执行 `.docx` 后处理

### Section 分发规则

Markdown 示例：

```markdown
+++
template_style = "template_a"
+++
# 第一段

+++
template_style = "template_b"
+++
# 第二段
```

PanFlow 会按下面的顺序查找 companion 脚本：

1. `processors/<template_style>.py`
2. `processors/<markdown同名>.py`
3. 如果都不存在，打印警告并跳过该 section

当前仓库里的示例文件：

- `design_doc.md`
- `processors/design_doc.py`
- `config.json`
- `processors/basic_table.py`
- `processors/static_analysis_table.py`
- `processors/test_case_table.py`
- `processors/traceability_matrix_table.py`

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
    "template_style": "template_a",
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

共享 HTML 辅助脚本位于：

- `src/panflow_service/renderers/testcase_table.py`

## 配置文件

默认配置文件是仓库根目录的 `panflow.toml`：

```toml
[pandoc]
binary = "pandoc"
reference_doc = "templates/reference.docx"
```

它目前主要负责：

- 指定 `pandoc` 可执行文件和默认 `reference.docx`

当前仓库支持两类主输入方式：

- section + `template_style`：通过 `+++` front matter 分发到对应模板脚本
- same-name companion：例如 `design_doc.md` 直接对应 `design_doc.py`，脚本内部再解析 `json:类型`

`design_doc.py` 这类脚本如果还需要把 `json:类型` 再分发到多个子脚本，当前仓库推荐通过 JSON 配置文件维护映射：

- 开发态：项目根目录 `config.json`
- 打包后：`MyService.exe` 同目录下的 `config.json`
- 说明字段：`_meta`
- 顶层对象：`renderers`
- 键：`block_type`
- 值：`script_name`

脚本路径支持两种写法：

- 直接写脚本名，例如 `basic_table.py`
- 写相对目录，例如 `renderers/custom_table.py`

相对路径一律相对 `config.json` 所在目录解析。这样打包成 `exe` 后，只要把自定义脚本放到相对目录下，再改 `config.json`，就可以直接扩展。

JSON 本身不支持注释，如果你想补说明，建议写到 `_meta` 里，不影响运行时读取。

查看映射：

```bash
cat config.json
```

新增一种类型：

```json
{
  "_meta": {
    "template_style": "design_doc"
  },
  "renderers": {
    "basic_table": "basic_table.py",
    "new_type": "renderers/design_doc_new_type.py"
  }
}
```

如果你通过 `--config` 显式传入配置文件，运行时会使用你指定的那一份。

## CLI

安装后可使用命令：

```bash
mdToWord convert input.md -o output.docx
mdToWord render input.md -o output.rendered.html
mdToWord reverse input.docx -o output.md
```

常用参数：

- `--config`：指定配置文件
- `--intermediate-output`：保留中间渲染产物
- `--reference-doc`：覆盖默认 Word 模板
- `--html-output`：在 `reverse` 时保留中间 HTML

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
dist/PanFlow_Release/
├── PanFlow.exe
├── config.json
├── _internal/
└── logs/
```

如果你想把发布目录名和 exe 名分开：

```bash
python3 scripts/build_app.py --mode onedir --name MyService --release-dir-name MyProject_Release
```

这样会得到：

```text
dist/MyProject_Release/
├── MyService.exe
├── config.json
├── _internal/
└── logs/
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

- `processors/`
- `templates/`
- `src/panflow_service/renderers/testcase_table.py` 所在包资源
- 发布目录根下的 `config.json`
- 发布目录根下的 `logs/`

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
- companion section 分发
- `pandoc` 命令组装
- bundled 资源发现
- `.docx` 表格后处理

## 项目结构

```text
PanFlow/
├── processors/
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
