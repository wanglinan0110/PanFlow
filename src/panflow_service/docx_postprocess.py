"""HTML 表格样式回填到 Word XML。

pandoc 对复杂表格 CSS 的支持有限，这个模块负责把关键样式写回真正的 docx 结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NAMESPACE}}}"


# 下面这些 dataclass 是“从 HTML 样式抽出的中间表示”，便于后续映射到 Word XML。
@dataclass(frozen=True)
class BorderSpec:
    value: str
    size: int
    color: str


@dataclass(frozen=True)
class PaddingSpec:
    top: int
    right: int
    bottom: int
    left: int


@dataclass(frozen=True)
class CellStyleSpec:
    text_align: str | None = None
    vertical_align: str | None = None
    line_height: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    padding: PaddingSpec | None = None
    borders: dict[str, BorderSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class RowStyleSpec:
    line_height: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    cells: list[CellStyleSpec] = field(default_factory=list)


@dataclass(frozen=True)
class TableStyleSpec:
    line_height: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    width: str | None = None
    table_layout: str | None = None
    borders: dict[str, BorderSpec] = field(default_factory=dict)
    rows: list[RowStyleSpec] = field(default_factory=list)


@dataclass(frozen=True)
class ParagraphStyleSpec:
    text_align: str | None = None
    line_height: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    style_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockSpec:
    kind: str
    paragraph: ParagraphStyleSpec | None = None
    table: TableStyleSpec | None = None


def apply_html_table_styles_to_docx(html: str, docx_path: Path) -> bool:
    # 总入口：先从 HTML 抽取块样式，再把对应样式写回 `word/document.xml`。
    block_specs = _extract_block_specs(html)
    if not block_specs:
        return False

    with ZipFile(docx_path, "r") as docx_file:
        document_xml = docx_file.read("word/document.xml")
        try:
            styles_xml = docx_file.read("word/styles.xml")
            paragraph_styles = _extract_paragraph_style_ids(styles_xml)
        except KeyError:
            paragraph_styles = {}
        try:
            heading_numbering_num_id = _extract_heading_numbering_num_id(docx_file.read("word/numbering.xml"))
        except KeyError:
            heading_numbering_num_id = None
        updated_xml = _apply_block_specs_to_document_xml(
            document_xml,
            block_specs,
            paragraph_styles,
            heading_numbering_num_id=heading_numbering_num_id,
        )
        if updated_xml == document_xml:
            return False

        with BytesIO() as buffer:
            with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as updated_docx:
                for item in docx_file.infolist():
                    data = updated_xml if item.filename == "word/document.xml" else docx_file.read(item.filename)
                    updated_docx.writestr(item, data)
            docx_path.write_bytes(buffer.getvalue())
    return True


def _extract_block_specs(html: str) -> list[BlockSpec]:
    # 给 HTML 包一层根节点，便于用 XML 方式递归解析。
    wrapped = f"<root>{html}</root>"
    root = ET.fromstring(wrapped)
    blocks: list[BlockSpec] = []
    _collect_block_specs(root, blocks)
    return blocks


def _collect_block_specs(node: ET.Element, blocks: list[BlockSpec]) -> None:
    # 这里只收集与 Word 样式映射直接相关的 block：表格和段落类标签。
    for child in list(node):
        if child.tag == "table":
            blocks.append(BlockSpec(kind="table", table=_extract_table_spec(child)))
            continue
        if child.tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p"} or _is_paragraph_like_div(child):
            style_candidates = {
                "h1": ("heading 1",),
                "h2": ("heading 2",),
                "h3": ("heading 3",),
                "h4": ("heading 4",),
                "h5": ("heading 5",),
                "h6": ("heading 6",),
                "p": ("正文标准", "Normal"),
                "div": ("正文标准", "Normal"),
            }.get(child.tag, ())
            style_map = _parse_style_map(child.get("style", ""))
            blocks.append(
                BlockSpec(
                    kind="paragraph",
                    paragraph=ParagraphStyleSpec(
                        text_align=style_map.get("text-align"),
                        line_height=style_map.get("line-height"),
                        font_family=style_map.get("font-family"),
                        font_size=style_map.get("font-size"),
                        font_weight=style_map.get("font-weight"),
                        style_candidates=style_candidates,
                    ),
                ),
            )
            continue
        _collect_block_specs(child, blocks)


def _is_paragraph_like_div(node: ET.Element) -> bool:
    # design_doc 这类脚本会把正文行渲染成 div；只有“没有 block 子节点的叶子 div”才当作段落处理，
    # 避免把外层布局容器误算成一个 Word 段落。
    if node.tag != "div":
        return False
    child_tags = {child.tag for child in list(node)}
    block_tags = {"div", "p", "table", "h1", "h2", "h3", "h4", "h5", "h6"}
    if child_tags & block_tags:
        return False
    has_text = bool((node.text or "").strip())
    has_style = bool(node.get("style"))
    return has_text or has_style


def _extract_table_spec(table: ET.Element) -> TableStyleSpec:
    # 表格样式既有 table 级默认值，也可能被 tr / td 再覆盖。
    table_style = _parse_style_map(table.get("style", ""))
    rows: list[RowStyleSpec] = []
    for row in _iter_rows(table):
        row_style = _parse_style_map(row.get("style", ""))
        cells: list[CellStyleSpec] = []
        for cell in row:
            if cell.tag not in {"td", "th"}:
                continue
            cell_style = _parse_style_map(cell.get("style", ""))
            cells.append(
                CellStyleSpec(
                    text_align=cell_style.get("text-align"),
                    vertical_align=cell_style.get("vertical-align"),
                    line_height=cell_style.get("line-height") or row_style.get("line-height") or table_style.get("line-height"),
                    font_family=cell_style.get("font-family") or row_style.get("font-family") or table_style.get("font-family"),
                    font_size=cell_style.get("font-size") or row_style.get("font-size") or table_style.get("font-size"),
                    font_weight=cell_style.get("font-weight") or row_style.get("font-weight") or table_style.get("font-weight"),
                    padding=_parse_padding(cell_style.get("padding")),
                    borders=_parse_borders(cell_style),
                ),
            )
        rows.append(
            RowStyleSpec(
                line_height=row_style.get("line-height") or table_style.get("line-height"),
                font_family=row_style.get("font-family") or table_style.get("font-family"),
                font_size=row_style.get("font-size") or table_style.get("font-size"),
                font_weight=row_style.get("font-weight") or table_style.get("font-weight"),
                cells=cells,
            ),
        )
    return TableStyleSpec(
        line_height=table_style.get("line-height"),
        font_family=table_style.get("font-family"),
        font_size=table_style.get("font-size"),
        font_weight=table_style.get("font-weight"),
        width=table_style.get("width"),
        table_layout=table_style.get("table-layout"),
        borders=_parse_borders(table_style, include_inside=True),
        rows=rows,
    )


def _iter_rows(table: ET.Element) -> list[ET.Element]:
    rows: list[ET.Element] = []
    for child in table:
        if child.tag == "tr":
            rows.append(child)
            continue
        if child.tag in {"thead", "tbody", "tfoot"}:
            rows.extend(grandchild for grandchild in child if grandchild.tag == "tr")
    return rows


def _apply_block_specs_to_document_xml(
    document_xml: bytes,
    block_specs: list[BlockSpec],
    paragraph_styles: dict[str, str],
    *,
    heading_numbering_num_id: int | None = None,
) -> bytes:
    # HTML 块和 Word XML 块按顺序对齐，只在类型匹配时写入样式。
    _register_namespaces(document_xml)
    root = ET.fromstring(document_xml)
    body = root.find(f"{W}body")
    if body is None:
        return document_xml
    xml_blocks = [child for child in list(body) if child.tag in {f"{W}p", f"{W}tbl"}]
    changed = False
    block_index = 0
    xml_index = 0
    while block_index < len(block_specs) and xml_index < len(xml_blocks):
        block_spec = block_specs[block_index]
        xml_block = xml_blocks[xml_index]
        xml_kind = "table" if xml_block.tag == f"{W}tbl" else "paragraph"
        if block_spec.kind != xml_kind:
            xml_index += 1
            continue
        if block_spec.kind == "table" and block_spec.table is not None:
            if _apply_table_spec(xml_block, block_spec.table, paragraph_styles):
                changed = True
        if block_spec.kind == "paragraph" and block_spec.paragraph is not None:
            if _apply_paragraph_spec(
                xml_block,
                block_spec.paragraph,
                paragraph_styles,
                heading_numbering_num_id=heading_numbering_num_id,
            ):
                changed = True
        block_index += 1
        xml_index += 1
    if not changed:
        return document_xml
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _apply_table_spec(table: ET.Element, spec: TableStyleSpec, paragraph_styles: dict[str, str]) -> bool:
    # 先处理表格级属性，再把样式分发到每一行和每个单元格。
    changed = False
    table_pr = _ensure_child(table, "tblPr")
    changed |= _remove_child(table_pr, "tblStyle")
    changed |= _remove_child(table_pr, "tblLook")
    if spec.width is not None:
        changed |= _set_table_width(table_pr, spec.width)
    if spec.table_layout is not None:
        changed |= _set_table_layout(table_pr, spec.table_layout)
    if spec.borders:
        changed |= _set_borders(table_pr, "tblBorders", spec.borders)

    rows = table.findall(f"{W}tr")
    for row_element, row_spec in zip(rows, spec.rows):
        if _apply_row_spec(row_element, row_spec, spec, paragraph_styles):
            changed = True
    return changed


def _apply_row_spec(
    row: ET.Element,
    row_spec: RowStyleSpec,
    table_spec: TableStyleSpec,
    paragraph_styles: dict[str, str],
) -> bool:
    changed = False
    line_height = row_spec.line_height or table_spec.line_height
    font_size = row_spec.font_size or table_spec.font_size
    height = _line_height_to_twips(line_height, font_size)
    if height is not None:
        row_pr = _ensure_child(row, "trPr")
        changed |= _set_attr_child(row_pr, "trHeight", {"val": str(height), "hRule": "atLeast"})

    cells = row.findall(f"{W}tc")
    for cell_element, cell_spec in zip(cells, row_spec.cells):
        if _apply_cell_spec(cell_element, cell_spec, table_spec, paragraph_styles):
            changed = True
    return changed


def _apply_cell_spec(
    cell: ET.Element,
    cell_spec: CellStyleSpec,
    table_spec: TableStyleSpec,
    paragraph_styles: dict[str, str],
) -> bool:
    changed = False
    cell_pr = _ensure_child(cell, "tcPr")
    borders = cell_spec.borders or table_spec.borders
    if borders:
        changed |= _set_borders(cell_pr, "tcBorders", borders, include_inside=False)

    if cell_spec.vertical_align is not None:
        valign = _map_vertical_align(cell_spec.vertical_align)
        changed |= _set_attr_child(cell_pr, "vAlign", {"val": valign})

    if cell_spec.padding is not None:
        changed |= _set_padding(cell_pr, cell_spec.padding)

    line_height = cell_spec.line_height or table_spec.line_height
    font_family = cell_spec.font_family or table_spec.font_family
    font_size = cell_spec.font_size or table_spec.font_size
    font_weight = cell_spec.font_weight or table_spec.font_weight
    for paragraph in cell.findall(f"{W}p"):
        changed |= _apply_paragraph_spec(
            paragraph,
            ParagraphStyleSpec(
                text_align=cell_spec.text_align,
                line_height=line_height,
                font_family=font_family,
                font_size=font_size,
                font_weight=font_weight,
                style_candidates=("表格文字", "表正文格式", "Normal"),
            ),
            paragraph_styles,
        )
    return changed


def _apply_paragraph_spec(
    paragraph: ET.Element,
    spec: ParagraphStyleSpec,
    paragraph_styles: dict[str, str],
    *,
    heading_numbering_num_id: int | None = None,
) -> bool:
    # 段落层只处理对齐和行距，避免把字体/字号固化成 run 级直接格式，影响 WPS 样式编辑。
    changed = False
    paragraph_pr = _ensure_child(paragraph, "pPr")
    style_id = _resolve_paragraph_style_id(spec.style_candidates, paragraph_styles)
    if style_id is not None:
        changed |= _set_attr_child(paragraph_pr, "pStyle", {"val": style_id})
    heading_level = _extract_heading_level(spec.style_candidates)
    if heading_level is not None and heading_numbering_num_id is not None:
        changed |= _set_num_pr(paragraph_pr, num_id=heading_numbering_num_id, ilvl=heading_level - 1)
    if spec.text_align is not None:
        changed |= _set_attr_child(paragraph_pr, "jc", {"val": _map_text_align(spec.text_align)})
    spacing = _line_height_to_spacing(spec.line_height, spec.font_size)
    if spacing is not None:
        changed |= _set_attr_child(paragraph_pr, "spacing", spacing)
    return changed


def _set_table_width(table_pr: ET.Element, width: str) -> bool:
    width_value = width.strip()
    if width_value.endswith("%"):
        amount = float(width_value[:-1].strip())
        attrs = {"type": "pct", "w": str(int(round(amount * 50)))}
    else:
        twips = _length_to_twips(width_value)
        if twips is None:
            return False
        attrs = {"type": "dxa", "w": str(twips)}
    return _set_attr_child(table_pr, "tblW", attrs)


def _set_table_layout(table_pr: ET.Element, layout: str) -> bool:
    value = "fixed" if layout.strip().lower() == "fixed" else "autofit"
    return _set_attr_child(table_pr, "tblLayout", {"type": value})


def _set_padding(cell_pr: ET.Element, padding: PaddingSpec) -> bool:
    changed = False
    margin = _ensure_child(cell_pr, "tcMar")
    changed |= _set_attr_child(margin, "top", {"w": str(padding.top), "type": "dxa"})
    changed |= _set_attr_child(margin, "right", {"w": str(padding.right), "type": "dxa"})
    changed |= _set_attr_child(margin, "bottom", {"w": str(padding.bottom), "type": "dxa"})
    changed |= _set_attr_child(margin, "left", {"w": str(padding.left), "type": "dxa"})
    return changed


def _set_borders(
    parent: ET.Element,
    container_tag: str,
    borders: dict[str, BorderSpec],
    *,
    include_inside: bool = True,
) -> bool:
    # Word 边框节点不支持“局部更新”那么方便，这里直接重建边框容器最稳妥。
    container = _ensure_child(parent, container_tag)
    for child in list(container):
        container.remove(child)

    sides = ["top", "left", "bottom", "right"]
    if include_inside:
        sides.extend(["insideH", "insideV"])

    for side in sides:
        spec = borders.get(side)
        if spec is None:
            continue
        border = ET.SubElement(container, f"{W}{side}")
        border.set(f"{W}val", spec.value)
        border.set(f"{W}sz", str(spec.size))
        border.set(f"{W}space", "0")
        border.set(f"{W}color", spec.color)
    return True


def _set_attr_child(parent: ET.Element, tag: str, attrs: dict[str, str]) -> bool:
    child = _ensure_child(parent, tag)
    changed = False
    for key, value in attrs.items():
        attr_key = f"{W}{key}"
        if child.get(attr_key) != value:
            child.set(attr_key, value)
            changed = True
    return changed


def _extract_paragraph_style_ids(styles_xml: bytes) -> dict[str, str]:
    mapping: dict[str, str] = {}
    root = ET.fromstring(styles_xml)
    for style in root.findall(f"{W}style"):
        if style.get(f"{W}type") != "paragraph":
            continue
        style_id = style.get(f"{W}styleId")
        if not style_id:
            continue
        name_element = style.find(f"{W}name")
        if name_element is not None:
            name = name_element.get(f"{W}val")
            if name:
                mapping[name.strip().lower()] = style_id
        aliases_element = style.find(f"{W}aliases")
        if aliases_element is not None:
            aliases = aliases_element.get(f"{W}val", "")
            for alias in aliases.split(","):
                normalized = alias.strip().lower()
                if normalized:
                    mapping[normalized] = style_id
    return mapping


def _extract_heading_level(style_candidates: tuple[str, ...]) -> int | None:
    for candidate in style_candidates:
        normalized = candidate.strip().lower()
        if normalized.startswith("heading "):
            suffix = normalized.removeprefix("heading ").strip()
            if suffix.isdigit():
                return int(suffix)
    return None


def _extract_heading_numbering_num_id(numbering_xml: bytes) -> int | None:
    root = ET.fromstring(numbering_xml)
    abstract_num_id = None
    for abstract_num in root.findall(f"{W}abstractNum"):
        current_abstract_num_id = abstract_num.get(f"{W}abstractNumId")
        if current_abstract_num_id is None:
            continue
        level_zero = abstract_num.find(f"{W}lvl[@{W}ilvl='0']")
        if level_zero is None:
            continue
        level_text = level_zero.find(f"{W}lvlText")
        if level_text is None:
            continue
        if level_text.get(f"{W}val") == "%1 ":
            abstract_num_id = current_abstract_num_id
            break
    if abstract_num_id is None:
        return None

    for num in root.findall(f"{W}num"):
        num_id = num.get(f"{W}numId")
        abstract_num_ref = num.find(f"{W}abstractNumId")
        if num_id is None or abstract_num_ref is None:
            continue
        if abstract_num_ref.get(f"{W}val") == abstract_num_id:
            try:
                return int(num_id)
            except ValueError:
                return None
    return None


def _resolve_paragraph_style_id(candidates: tuple[str, ...], paragraph_styles: dict[str, str]) -> str | None:
    for candidate in candidates:
        style_id = paragraph_styles.get(candidate.strip().lower())
        if style_id is not None:
            return style_id
    return None


def _set_empty_child(parent: ET.Element, tag: str) -> bool:
    child = parent.find(f"{W}{tag}")
    if child is not None:
        return False
    parent.append(ET.Element(f"{W}{tag}"))
    return True


def _ensure_child(parent: ET.Element, tag: str) -> ET.Element:
    existing = parent.find(f"{W}{tag}")
    if existing is not None:
        return existing
    child = ET.Element(f"{W}{tag}")
    parent.append(child)
    return child


def _remove_child(parent: ET.Element, tag: str) -> bool:
    child = parent.find(f"{W}{tag}")
    if child is None:
        return False
    parent.remove(child)
    return True


def _set_num_pr(parent: ET.Element, *, num_id: int, ilvl: int) -> bool:
    num_pr = _ensure_child(parent, "numPr")
    changed = False
    changed |= _set_attr_child(num_pr, "ilvl", {"val": str(ilvl)})
    changed |= _set_attr_child(num_pr, "numId", {"val": str(num_id)})
    return changed


def _parse_style_map(style: str) -> dict[str, str]:
    # 把 `a: b; c: d` 形式的 style 文本转成小写键值表。
    mapping: dict[str, str] = {}
    for item in style.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", maxsplit=1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            mapping[normalized_key] = normalized_value
    return mapping


def _parse_borders(style_map: dict[str, str], *, include_inside: bool = False) -> dict[str, BorderSpec]:
    # 先取通用 border，再让边级属性覆盖通用值。
    borders: dict[str, BorderSpec] = {}
    common = _parse_border(style_map.get("border"))
    for side in ("top", "right", "bottom", "left"):
        border = _parse_border(style_map.get(f"border-{side}")) or common
        if border is not None:
            borders[side] = border
    if include_inside and common is not None:
        borders["insideH"] = common
        borders["insideV"] = common
    return borders


def _parse_border(raw: str | None) -> BorderSpec | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value or value == "none":
        return None

    tokens = value.split()
    width_token = next((token for token in tokens if any(token.endswith(unit) for unit in ("px", "pt"))), "1px")
    style_token = next((token for token in tokens if token in {"solid", "dashed", "dotted", "double"}), "solid")
    color_token = next((token for token in tokens if token.startswith("#") or token in {"black", "white", "auto"}), "#000000")
    return BorderSpec(
        value=_map_border_style(style_token),
        size=max(_length_to_border_size(width_token), 4),
        color=_map_color(color_token),
    )


def _parse_padding(raw: str | None) -> PaddingSpec | None:
    if raw is None:
        return None
    parts = [part for part in raw.split() if part]
    if not parts:
        return None
    values = [_length_to_twips(part) for part in parts]
    if any(value is None for value in values):
        return None
    resolved = [int(value) for value in values if value is not None]
    if len(resolved) == 1:
        top = right = bottom = left = resolved[0]
    elif len(resolved) == 2:
        top = bottom = resolved[0]
        right = left = resolved[1]
    elif len(resolved) == 3:
        top = resolved[0]
        right = left = resolved[1]
        bottom = resolved[2]
    else:
        top, right, bottom, left = resolved[:4]
    return PaddingSpec(top=top, right=right, bottom=bottom, left=left)


def _line_height_to_spacing(line_height: str | None, font_size: str | None) -> dict[str, str] | None:
    # Word 行距既支持固定值，也支持倍数行距，这里统一做换算。
    if line_height is None:
        return None
    value = line_height.strip().lower()
    if value.endswith("pt"):
        points = _length_to_points(value)
        if points is None:
            return None
        return {"line": str(int(round(points * 20))), "lineRule": "exact"}
    if value.endswith("px"):
        twips = _length_to_twips(value)
        if twips is None:
            return None
        return {"line": str(twips), "lineRule": "exact"}

    try:
        multiplier = float(value)
    except ValueError:
        return None
    return {"line": str(int(round(multiplier * 240))), "lineRule": "auto"}


def _line_height_to_twips(line_height: str | None, font_size: str | None) -> int | None:
    if line_height is None:
        return None
    value = line_height.strip().lower()
    if value.endswith(("pt", "px")):
        return _length_to_twips(value)
    try:
        multiplier = float(value)
    except ValueError:
        return None
    font_size_points = _length_to_points(font_size or "12pt")
    if font_size_points is None:
        font_size_points = 12.0
    return int(round(multiplier * font_size_points * 20))


def _length_to_points(raw: str) -> float | None:
    value = raw.strip().lower()
    try:
        if value.endswith("pt"):
            return float(value[:-2].strip())
        if value.endswith("px"):
            return float(value[:-2].strip()) * 0.75
    except ValueError:
        return None
    return None


def _length_to_twips(raw: str) -> int | None:
    points = _length_to_points(raw)
    if points is None:
        return None
    return int(round(points * 20))


def _length_to_border_size(raw: str) -> int:
    points = _length_to_points(raw)
    if points is None:
        return 8
    return int(round(points * 8))


def _map_border_style(style: str) -> str:
    # CSS 边框样式与 Word 的枚举值并不完全一致，需要手工映射。
    return {
        "solid": "single",
        "dashed": "dashed",
        "dotted": "dotted",
        "double": "double",
    }.get(style, "single")


def _map_color(color: str) -> str:
    if color == "auto":
        return "auto"
    if color == "black":
        return "000000"
    if color == "white":
        return "FFFFFF"
    return color.lstrip("#").upper() or "000000"


def _map_vertical_align(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"middle", "center"}:
        return "center"
    if normalized == "bottom":
        return "bottom"
    return "top"


def _map_text_align(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"center", "left", "right", "both"}:
        return normalized
    if normalized == "justify":
        return "both"
    return "left"


def _register_namespaces(xml_bytes: bytes) -> None:
    # 保留原始命名空间前缀，避免回写 XML 后前缀风格被打乱。
    namespaces: list[tuple[str, str]] = []
    for _, namespace in ET.iterparse(BytesIO(xml_bytes), events=("start-ns",)):
        if namespace not in namespaces:
            namespaces.append(namespace)
    for prefix, uri in namespaces:
        ET.register_namespace(prefix, uri)
