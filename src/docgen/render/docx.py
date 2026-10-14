"""IR -> Word（.docx）（完整版手册 §5 / §7 / W0~W1）。

渲染层只认 IR + config：

- 块级节点用 Word 样式承载（``Heading1``…``Heading6``、``Normal``、``Quote``）；
- 行内样式（``Styled``）的**最终值来自 config**，逐 run 写入字体/加粗/斜体/颜色，
  于是「输出中的样式属性 == config 声明值」这条不变量可以直接在 XML 上断言；
- 所有 OOXML 片段走 :mod:`docgen.render.ooxml`，本模块不直接拼 XML。

W0 覆盖：标题、段落、行内样式、代码块、列表、引用、分隔线、分页、表格。
后续阶段补：数学（OMML）、编号/题注/交叉引用、脚注、分节/页眉页脚、目录。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ..config import Config, build_style_table
from ..ir import (
    BlockNode,
    BlockQuote,
    Break,
    Code,
    CodeBlock,
    Footnote,
    Formula,
    Heading,
    Image,
    ImageBlock,
    InlineNode,
    Link,
    ListBlock,
    ListItem,
    Math,
    NamedBlock,
    PageBreak,
    Paragraph,
    Ref,
    Styled,
    Table,
    TableCell,
    Text,
    ThematicBreak,
    Toc,
)
from ..numbering import CAPTION_KINDS, caption_kind
from .math import latex_to_omml, math_settings
from .ooxml import (
    append_field,
    append_omml,
    append_text,
    apply_font,
    apply_three_line_borders,
    drop_empty_runs,
    length_from_text,
    make_bookmark_end,
    make_bookmark_start,
    make_caption_field,
    make_math_paragraph,
    make_page_break,
    make_reference_field,
    merge_cell_horizontal,
    merge_cell_vertical,
    page_content_width,
    repeat_table_header,
    set_cell_alignment,
    set_cell_width,
    set_paragraph_alignment,
    set_paragraph_border,
    set_paragraph_indent,
    set_paragraph_shading,
    set_paragraph_spacing,
    set_table_borders,
)
from .template import create_document

__all__ = ["render_docx", "render_docx_bytes"]

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: 代码块缺省等宽字体（config 没声明 font.name 时兜底）
DEFAULT_MONO_FONT = "Consolas"


def render_docx(
    blocks: list[BlockNode],
    config: Config,
    output: Path,
    template: Path | None = None,
    base_dir: Path | None = None,
) -> Path:
    """渲染为 ``.docx`` 文件，返回写入路径（有脚注时注入 ``word/footnotes.xml``）。"""
    document, footnotes = _build_document(blocks, config, template, base_dir)
    from .footnotes import save_with_footnotes

    return save_with_footnotes(document, output, footnotes)


def render_docx_bytes(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None = None,
    base_dir: Path | None = None,
) -> bytes:
    """渲染到内存（测试用，避免落盘）。"""
    from .footnotes import inject_footnotes

    document, footnotes = _build_document(blocks, config, template, base_dir)
    buffer = io.BytesIO()
    document.save(buffer)
    data = buffer.getvalue()
    return inject_footnotes(data, footnotes) if footnotes else data


def _build_document(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None,
    base_dir: Path | None,
) -> tuple[Any, list[str]]:
    document = create_document(config, template)
    _apply_sections(document, config)
    state = _RenderState(
        document=document,
        config=config,
        styles=build_style_table(config),
        base_dir=base_dir,
    )
    _render_blocks(state, blocks)
    _ensure_update_fields(document)
    return document, state.footnotes


def _apply_sections(document: Any, config: Config) -> list[Any]:
    """``[[sections]]``：设置纸张/页边距/页码/页眉页脚（无配置时保持默认）。"""
    from .sections import apply_sections

    raw = config.extra.get("sections")
    specs = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return apply_sections(document, specs)


class _RenderState:
    __slots__ = (
        "_bookmark_id",
        "base_dir",
        "config",
        "default_east_asia",
        "doc_settings",
        "document",
        "footnote_reference_maker",
        "footnotes",
        "math_engine",
        "math_on_fail",
        "math_xsl",
        "styles",
    )

    def __init__(
        self,
        document: Any,
        config: Config,
        styles: dict[str, dict[str, Any]],
        base_dir: Path | None,
    ) -> None:
        self.document = document
        self.config = config
        self.styles = styles
        self.base_dir = base_dir
        self.doc_settings = dict(config.document)
        self.math_engine, self.math_on_fail, self.math_xsl = math_settings(config)
        self._bookmark_id = 1000
        self.footnotes: list[str] = []
        self.footnote_reference_maker: Any = None
        # 可选的配置键：代码块等场景要显式指定中文字体时用
        self.default_east_asia = str(config.document.get("font.east_asia", "")) or None

    def next_bookmark_id(self) -> int:
        self._bookmark_id += 1
        return self._bookmark_id


# --------------------------------------------------------------------------
# 块级
# --------------------------------------------------------------------------
def _render_blocks(state: _RenderState, blocks: list[BlockNode]) -> None:
    for block in blocks:
        _render_block(state, block)


def _render_block(state: _RenderState, block: BlockNode) -> None:
    if isinstance(block, Heading):
        _render_heading(state, block)
    elif isinstance(block, Paragraph):
        paragraph = state.document.add_paragraph()
        _apply_body_paragraph(state, paragraph)
        _render_inlines(state, paragraph, block.content, None)
    elif isinstance(block, ListBlock):
        _render_list(state, block)
    elif isinstance(block, CodeBlock):
        _render_code_block(state, block)
    elif isinstance(block, Formula):
        _render_formula(state, block)
    elif isinstance(block, ImageBlock):
        _render_image_block(state, block)
    elif isinstance(block, ThematicBreak):
        _render_thematic_break(state)
    elif isinstance(block, PageBreak):
        _render_page_break(state)
    elif isinstance(block, BlockQuote):
        _render_block_quote(state, block)
    elif isinstance(block, Table):
        _render_table(state, block)
    elif isinstance(block, NamedBlock):
        _render_named_block(state, block)
    elif isinstance(block, Toc):
        _render_toc(state)


def _render_heading(state: _RenderState, block: Heading) -> None:
    level = max(1, min(9, block.level))
    # 用样式「名」（Heading 1）而不是 style_id：python-docx 1.2 起后者会告警
    paragraph = state.document.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = True
    _render_inlines(state, paragraph, block.content, f"heading{level}")


def _apply_body_paragraph(state: _RenderState, paragraph: Any) -> None:
    """正文段落：把 body 样式与 ``[document]`` 的段落级属性写进去。

    document 的值作为兜底，body 样式覆盖它（config 只有一个真源，但层级不同）。
    """
    properties = {**state.doc_settings, **state.styles.get("body", {})}
    spacing = properties.get("line_spacing")
    if spacing is not None:
        set_paragraph_spacing(paragraph, line_spacing=float(spacing))
    indent = properties.get("first_line_chars")
    if indent is not None:
        set_paragraph_indent(paragraph, first_line_chars=int(indent))


def _render_list(state: _RenderState, block: ListBlock) -> None:
    for item in block.items:
        _render_list_item(state, item, ordered=block.ordered, level=0)


def _render_list_item(state: _RenderState, item: ListItem, *, ordered: bool, level: int) -> None:
    base = "List Number" if ordered else "List Bullet"
    style = base if level == 0 else f"{base} {min(level + 1, 3)}"

    first = item.content[0] if item.content else None
    paragraph = state.document.add_paragraph(style=style)
    if isinstance(first, Paragraph):
        _render_inlines(state, paragraph, first.content, None)
    elif first is not None:
        _render_block(state, first)

    for block in item.content[1:]:
        if isinstance(block, ListBlock):
            for nested in block.items:
                _render_list_item(state, nested, ordered=block.ordered, level=level + 1)
        else:
            _render_block(state, block)


def _render_code_block(state: _RenderState, block: CodeBlock) -> None:
    properties = _code_properties(state, block.language)
    paragraph = state.document.add_paragraph()
    set_paragraph_spacing(paragraph, line_spacing=1.0)
    run = paragraph.add_run(block.content.rstrip("\n"))
    _apply_run_style(state, run, properties)
    if "font.name" not in properties and "font" not in properties:
        # 只设西文字体：把 eastAsia 留给样式链，否则代码块里的中文会掉字体
        apply_font(run, DEFAULT_MONO_FONT, east_asia=state.default_east_asia)

    # 背景与边框：config 里可以写 ``background = "F5F5F5"``、``border = "CCCCCC"``
    fill = properties.get("background") or properties.get("shading.fill")
    if isinstance(fill, str) and fill:
        set_paragraph_shading(paragraph, fill)
    border = properties.get("border")
    if isinstance(border, str) and border:
        for edge in ("top", "left", "bottom", "right"):
            set_paragraph_border(paragraph, edge, color=border)


def _render_formula(state: _RenderState, block: Formula) -> None:
    """块级公式：LaTeX → OMML 插进居中段落；引擎不可用时降级成 LaTeX 文本。"""
    paragraph = state.document.add_paragraph()
    result = latex_to_omml(
        block.latex.strip(),
        engine=state.math_engine,
        on_fail=state.math_on_fail,
        xsl_path=state.math_xsl,
    )
    if result.ok and make_math_paragraph(paragraph, result.omml or ""):
        return
    set_paragraph_indent(paragraph, first_line_chars=0)
    paragraph.add_run(block.latex.strip()).font.italic = True


def _render_image_block(state: _RenderState, block: ImageBlock) -> None:
    paragraph = state.document.add_paragraph()
    width = block.width or _image_setting(state, "width")
    align = block.align or _image_setting(state, "align")
    if align:
        set_paragraph_alignment(paragraph, align)
    _add_picture(state, paragraph, block.src, width=width)


def _image_setting(state: _RenderState, key: str) -> str:
    """``[image]`` 配置：尺寸/对齐的默认值。"""
    settings = state.config.extra.get("image")
    if isinstance(settings, dict):
        value = settings.get(key)
        if value:
            return str(value)
    return ""


def _add_picture(state: _RenderState, paragraph: Any, src: str, width: str = "") -> None:
    """图片：相对路径按源文件所在目录解析；``width`` 支持 ``2cm`` / ``1in`` / ``120px``。"""
    candidate = Path(src)
    if not candidate.is_absolute() and state.base_dir is not None:
        candidate = state.base_dir / src
    if not candidate.is_file():
        paragraph.add_run(f"[图片缺失: {src}]")
        return
    run = paragraph.add_run()
    if width:
        length = length_from_text(width)
        if length is not None:
            run.add_picture(str(candidate), width=length)
            return
    run.add_picture(str(candidate))
    paragraph = state.document.add_paragraph()
    paragraph.add_run("\u2014" * 20)


def _render_thematic_break(state: _RenderState) -> None:
    """分隔线：用一串破折号表示（Word 的 ``w:pBdr`` 也行，但这样更稳）。"""
    state.document.add_paragraph("———" * 8)


def _render_page_break(state: _RenderState) -> None:
    paragraph = state.document.add_paragraph()
    paragraph.add_run()._element.append(make_page_break())


def _render_block_quote(state: _RenderState, block: BlockQuote) -> None:
    for child in block.content:
        if isinstance(child, Paragraph):
            paragraph = state.document.add_paragraph(style="Quote")
            _render_inlines(state, paragraph, child.content, None)
        else:
            _render_block(state, child)


def _render_named_block(state: _RenderState, block: NamedBlock) -> None:
    """命名块容器。

    - ``equation`` 带 ``number`` 属性 → 无边框三列表格（公式编号，W3）
    - ``caption``/``table``/``equation`` 带 ``#id`` → 题注（书签 + SEQ 域）
    - 其余情况：内容照常渲染
    """
    kind = caption_kind(block)
    if kind == "equation":
        # 方程：带 number 走三列表格，否则就是普通块级公式（不套题注语义）
        if block.attributes.get("number"):
            _render_numbered_formula(state, block)
            return
    elif block.label and kind in CAPTION_KINDS:
        _render_caption(state, block)
        return
    for child in block.content:
        _render_block(state, child)


def _render_numbered_formula(state: _RenderState, block: NamedBlock) -> None:
    """公式编号：无边框三列表格（左空 / 中公式 / 右编号），编号带书签。

    用表格是为了让编号贴右边界——段落制表位在不同 Word 版本里表现不一致。
    """
    formula = next((child for child in block.content if isinstance(child, Formula)), None)
    if formula is None:
        for child in block.content:
            _render_block(state, child)
        return

    table = state.document.add_table(rows=1, cols=3)
    set_table_borders(
        table,
        top="none",
        left="none",
        bottom="none",
        right="none",
        insideH="none",
        insideV="none",
    )
    for cell in table.rows[0].cells:
        drop_empty_runs(cell.paragraphs[0])

    middle = table.cell(0, 1)
    _fill_formula_cell(state, middle, formula)

    number_cell = table.cell(0, 2)
    number = str(block.attributes.get("number", ""))
    paragraph = number_cell.paragraphs[0]
    # 先放文本，再整体包书签：反过来会得到「空书签」，REF 域取不到东西
    append_text(paragraph, f"({number})")
    if block.label:
        set_paragraph_bookmark(paragraph, block.label, state.next_bookmark_id())


def _fill_formula_cell(state: _RenderState, cell: Any, formula: Formula) -> None:
    from .math import latex_to_omml as _convert

    paragraph = cell.paragraphs[0]
    result = _convert(
        formula.latex.strip(),
        engine=state.math_engine,
        on_fail=state.math_on_fail,
        xsl_path=state.math_xsl,
    )
    if result.ok and make_math_paragraph(paragraph, result.omml or "", align="center"):
        return
    paragraph.add_run(formula.latex.strip()).font.italic = True


def _render_caption(state: _RenderState, block: NamedBlock) -> None:
    from ..numbering import CAPTION_KINDS, caption_kind

    label = CAPTION_KINDS[caption_kind(block)]
    paragraph = state.document.add_paragraph(style="Caption")
    append_text(paragraph, f"{label} ")
    append_field(
        paragraph,
        make_caption_field(label),
        "1",
        bookmark=block.label,
        bookmark_id=state.next_bookmark_id(),
    )
    text = _caption_text(block)
    if text:
        append_text(paragraph, f" {text}")


def set_paragraph_bookmark(paragraph: Any, name: str, bookmark_id: int) -> None:
    """把段落**已有内容**包进一个书签（start 放最前、end 放最后，同 id）。

    必须在内容写入之后调用——先插空书签会让 REF 域取不到任何东西。
    """
    target = paragraph._p
    target.insert(0, make_bookmark_start(name, bookmark_id))
    target.append(make_bookmark_end(bookmark_id))


def _caption_text(block: NamedBlock) -> str:
    """题注文本：命名块内第一个段落的纯文本。"""
    for child in block.content:
        if isinstance(child, Paragraph):
            return "".join(_plain_text(node) for node in child.content)
    return ""


def _plain_text(node: InlineNode) -> str:
    if isinstance(node, Text):
        return node.content
    if isinstance(node, Code):
        return node.content
    if isinstance(node, Math):
        return node.latex
    if isinstance(node, Ref):
        return node.target
    nested = getattr(node, "content", None)
    if isinstance(nested, list):
        return "".join(_plain_text(child) for child in nested)
    return ""


def _render_toc(state: _RenderState) -> None:
    """``[[toc]]`` → Word 的 TOC 域；``updateFields`` 已就位，打开时自动填充。"""
    paragraph = state.document.add_paragraph()
    append_field(paragraph, 'TOC \\o "1-9" \\h \\z \\u', "按 F9 更新目录")


def _render_ref(state: _RenderState, paragraph: Any, target: str) -> None:
    """``[[ref:目标]]`` → ``REF 目标 \\h`` 域（域结果是题注编号）。"""
    append_field(paragraph, make_reference_field(target), "1")


def _render_footnote(state: _RenderState, paragraph: Any, text: str) -> None:
    """``[[fn:文字]]`` → 正文里的脚注引用 run（脚注条目在存盘时注入部件）。"""
    state.footnotes.append(text)
    if state.footnote_reference_maker is None:
        from .ooxml import make_footnote_reference

        state.footnote_reference_maker = make_footnote_reference
    run = paragraph.add_run()
    run._element.append(state.footnote_reference_maker(len(state.footnotes)))
    run.font.superscript = True


def _render_table(state: _RenderState, block: Table) -> None:
    """表格：config 驱动三线表/网格/无框 + 重复表头 + 固定列宽 + 列对齐 + 合并。"""
    if block.cells:
        _render_cell_table(state, block)
        return
    if not block.rows:
        return

    properties = _table_properties(state)
    columns = max(len(row) for row in block.rows)
    table = state.document.add_table(rows=len(block.rows), cols=columns)
    if properties.get("borders", "grid") == "grid":
        table.style = "Table Grid"

    widths = _column_widths(properties, columns, state)
    for row_index, row in enumerate(block.rows):
        for column_index in range(columns):
            text = row[column_index] if column_index < len(row) else ""
            cell = table.cell(row_index, column_index)
            drop_empty_runs(cell.paragraphs[0])
            run = cell.paragraphs[0].add_run(text)
            if row_index == 0:
                run.bold = True
            _apply_cell_format(cell, widths[column_index], _column_alignment(block, column_index))
        if row_index == 0 and bool(properties.get("header_repeat", True)):
            repeat_table_header(table.rows[0])

    _apply_table_borders(table, properties, header_rows=1)


def _render_cell_table(state: _RenderState, block: Table) -> None:
    """结构化单元格（支持合并）。"""
    properties = _table_properties(state)
    rows = block.cells
    columns = sum(cell.colspan for cell in rows[0]) if rows else 0
    if not columns:
        return
    table = state.document.add_table(rows=len(rows), cols=columns)
    if properties.get("borders", "grid") == "grid":
        table.style = "Table Grid"

    for row_index, row in enumerate(rows):
        column_index = 0
        for cell_spec in row:
            cell = table.cell(row_index, column_index)
            drop_empty_runs(cell.paragraphs[0])
            if cell_spec.is_merge_continuation:
                merge_cell_horizontal(table, row_index, column_index)
            else:
                span = max(1, cell_spec.colspan)
                if span > 1:
                    merge_cell_horizontal(table, row_index, column_index, span)
                if cell_spec.rowspan > 1:
                    for offset in range(1, cell_spec.rowspan):
                        merge_cell_vertical(table, row_index, column_index, offset)
                _write_cell_content(state, cell, cell_spec)
            column_index += max(1, cell_spec.colspan)
        if row_index == 0 and bool(properties.get("header_repeat", True)):
            repeat_table_header(table.rows[0])

    _apply_table_borders(table, properties, header_rows=1)


def _write_cell_content(state: _RenderState, cell: Any, spec: TableCell) -> None:
    """单元格内容：优先渲染块序列；没有块时留空段落。"""
    if not spec.blocks:
        return
    cell.text = ""
    drop_empty_runs(cell.paragraphs[0])
    first = cell.paragraphs[0]
    for index, child in enumerate(spec.blocks):
        if isinstance(child, Paragraph):
            target = first if index == 0 else cell.add_paragraph()
            _render_inlines(state, target, child.content, None)
        else:
            _render_block(state, child)


def _table_properties(state: _RenderState) -> dict[str, Any]:
    """``[table]`` 配置（缺省：三线表 + 重复表头）。"""
    raw = state.config.extra.get("table")
    table = dict(raw) if isinstance(raw, dict) else {}
    style = str(table.get("style", "three_line"))
    table["style"] = style
    table["borders"] = {"three_line": "three_line", "grid": "grid", "none": "none"}.get(
        style, "three_line"
    )
    if "header_repeat" not in table:
        table["header_repeat"] = True
    return table


def _column_widths(properties: dict[str, Any], columns: int, state: _RenderState) -> list[int]:
    """列宽：``[table] col_widths`` 给出相对比例；否则按内容平均分配。"""
    total = page_content_width(state.document)
    ratios = properties.get("col_widths")
    if (
        isinstance(ratios, list)
        and len(ratios) == columns
        and all(isinstance(item, (int, float)) and item > 0 for item in ratios)
    ):
        weight_sum = float(sum(ratios))
        return [int(total * float(item) / weight_sum) for item in ratios]
    return [total // columns] * columns


def _column_alignment(block: Table, index: int) -> str:
    if index < len(block.alignments):
        return block.alignments[index]
    return ""


def _apply_cell_format(cell: Any, width: int, alignment: str) -> None:
    set_cell_width(cell, width)
    if alignment:
        set_cell_alignment(cell, alignment)


def _apply_table_borders(table: Any, properties: dict[str, Any], header_rows: int) -> None:
    style = properties.get("borders", "three_line")
    if style == "grid":
        set_table_borders(
            table,
            top="single",
            left="single",
            bottom="single",
            right="single",
            insideH="single",
            insideV="single",
        )
    elif style == "none":
        set_table_borders(
            table,
            top="none",
            left="none",
            bottom="none",
            right="none",
            insideH="none",
            insideV="none",
        )
    else:
        apply_three_line_borders(table, header_rows=header_rows)


# --------------------------------------------------------------------------
# 行内
# --------------------------------------------------------------------------
def _render_inlines(
    state: _RenderState,
    paragraph: Any,
    nodes: list[InlineNode],
    context_style: str | None,
) -> None:
    for node in nodes:
        _render_inline(state, paragraph, node, context_style)


def _render_inline(
    state: _RenderState,
    paragraph: Any,
    node: InlineNode,
    context_style: str | None,
) -> None:
    if isinstance(node, Text):
        _add_text_run(state, paragraph, node.content, context_style)
    elif isinstance(node, Code):
        run = paragraph.add_run(node.content)
        _apply_run_style(state, run, _code_properties(state, ""))
    elif isinstance(node, Break):
        paragraph.add_run().add_break()
    elif isinstance(node, Math):
        _render_math_inline(state, paragraph, node.latex)
    elif isinstance(node, Ref):
        _render_ref(state, paragraph, node.target)
    elif isinstance(node, Footnote):
        _render_footnote(state, paragraph, node.text)
    elif isinstance(node, Styled):
        _render_styled(state, paragraph, node, context_style)
    elif isinstance(node, Link):
        start = len(paragraph.runs)
        _render_inlines(state, paragraph, node.content, context_style)
        for run in paragraph.runs[start:]:
            run.font.underline = True
    elif isinstance(node, Image):
        _add_picture(state, paragraph, node.src)


def _render_styled(
    state: _RenderState,
    paragraph: Any,
    node: Styled,
    context_style: str | None,
) -> None:
    """``Styled``：先渲染内容，再把样式属性写到这一段新建的 run 上。

    ``sup`` / ``sub`` 是语义样式名：即使 config 没声明，也走上下标
    （手册 §6.2.3 的 ``[上标]{.sup}`` 与 ``H~2~O``）。
    """
    properties = state.styles.get(node.style_name, {})
    start = len(paragraph.runs)
    _render_inlines(state, paragraph, node.content, context_style or None)

    if node.style_name in ("sup", "sub"):
        for run in paragraph.runs[start:]:
            run.font.superscript = node.style_name == "sup"
            run.font.subscript = node.style_name == "sub"
        return
    if properties:
        for run in paragraph.runs[start:]:
            _apply_run_style(state, run, properties)


def _add_text_run(
    state: _RenderState,
    paragraph: Any,
    content: str,
    context_style: str | None,
) -> None:
    run = paragraph.add_run(content)
    properties = state.styles.get(context_style, {}) if context_style else {}
    if properties:
        _apply_run_style(state, run, properties)


def _apply_run_style(state: _RenderState, run: Any, properties: dict[str, Any]) -> None:
    """把 config 的样式属性写进 run（只认已知字段，保证「config 驱动」）。

    支持两种取值写法：点号键展开成的嵌套表（``font.name``）与扁平键。
    """
    from ..units import to_points

    font = properties.get("font")
    font = font if isinstance(font, dict) else {}

    name = font.get("name", properties.get("font.name"))
    size = font.get("size", properties.get("font.size"))
    color = font.get("color", properties.get("font.color"))
    bold = font.get("bold", properties.get("font.bold"))
    italic = font.get("italic", properties.get("font.italic"))
    strike = properties.get("strike", font.get("strike"))

    apply_font(
        run,
        str(name) if name else None,
        size=to_points(size) if size is not None else None,
        bold=bool(bold) if bold is not None else None,
        italic=bool(italic) if italic is not None else None,
        strike=bool(strike) if strike is not None else None,
        color=str(color) if color else None,
    )


def _render_math_inline(state: _RenderState, paragraph: Any, latex: str) -> None:
    """行内公式：OMML 直接挂在段落里（与文字同一行）；失败则降级成 LaTeX 文本。"""
    result = latex_to_omml(
        latex,
        engine=state.math_engine,
        on_fail=state.math_on_fail,
        xsl_path=state.math_xsl,
    )
    if result.ok and append_omml(paragraph, result.omml or ""):
        return
    paragraph.add_run(latex).font.italic = True


def _code_properties(state: _RenderState, language: str) -> dict[str, Any]:
    properties = dict(state.styles.get("code_block", {}))
    language = language.strip()
    if language:
        variant = state.styles.get(f"code_block.{language}")
        if variant:
            properties.update(variant)
    return properties


def _points(value: Any) -> float:
    """已由 :mod:`docgen.units` 统一，这里只保留给旧调用点的薄包装。"""
    from ..units import to_points

    return float(to_points(value).pt)


def _ensure_update_fields(document: Any) -> None:
    """settings.xml 补 ``updateFields``：Word 打开时自动更新目录/编号域。"""
    from .ooxml import make_update_fields

    settings = document.settings.element
    if settings.find(f"{_W_NS}updateFields") is None:
        settings.append(make_update_fields())
