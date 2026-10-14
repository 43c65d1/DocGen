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
    make_bookmark_end,
    make_bookmark_start,
    make_caption_field,
    make_math_paragraph,
    make_page_break,
    make_reference_field,
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
    """渲染为 ``.docx`` 文件，返回写入路径。"""
    document = _build_document(blocks, config, template, base_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output))
    return output


def render_docx_bytes(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None = None,
    base_dir: Path | None = None,
) -> bytes:
    """渲染到内存（测试用，避免落盘）。"""
    document = _build_document(blocks, config, template, base_dir)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_document(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None,
    base_dir: Path | None,
) -> Any:
    document = create_document(config, template)
    state = _RenderState(
        document=document,
        config=config,
        styles=build_style_table(config),
        base_dir=base_dir,
    )
    _render_blocks(state, blocks)
    _ensure_update_fields(document)
    return document


class _RenderState:
    __slots__ = (
        "_bookmark_id",
        "base_dir",
        "config",
        "doc_settings",
        "document",
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
        self._bookmark_id = 0

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
        apply_font(run, DEFAULT_MONO_FONT)

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
    _add_picture(state, paragraph, block.src)


def _render_thematic_break(state: _RenderState) -> None:
    paragraph = state.document.add_paragraph()
    paragraph.add_run("\u2014" * 20)


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
        cell.text = ""

    middle = table.cell(0, 1)
    _fill_formula_cell(state, middle, formula)

    number_cell = table.cell(0, 2)
    number = str(block.attributes.get("number", ""))
    if block.label:
        number_cell.paragraphs[0]._p.append(
            make_bookmark_start(block.label, state.next_bookmark_id())
        )
    append_text(number_cell.paragraphs[0], f"({number})")
    if block.label:
        number_cell.paragraphs[0]._p.append(make_bookmark_end(state.next_bookmark_id()))


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
    bookmark_id = state.next_bookmark_id()
    paragraph._p.append(make_bookmark_start(block.label, bookmark_id))
    append_text(paragraph, f"{label} ")
    append_field(paragraph, make_caption_field(label), "1")
    text = _caption_text(block)
    if text:
        append_text(paragraph, f" {text}")
    paragraph._p.append(make_bookmark_end(bookmark_id))


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


def _render_table(state: _RenderState, block: Table) -> None:
    if not block.rows:
        return
    columns = max(len(row) for row in block.rows)
    table = state.document.add_table(rows=len(block.rows), cols=columns)
    table.style = "Table Grid"
    for row_index, row in enumerate(block.rows):
        for column_index in range(columns):
            text = row[column_index] if column_index < len(row) else ""
            cell = table.cell(row_index, column_index)
            cell.text = ""
            run = cell.paragraphs[0].add_run(text)
            if row_index == 0:
                run.bold = True
    set_table_borders(table, top="single", bottom="single", insideH="single")


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


def _add_picture(state: _RenderState, paragraph: Any, src: str) -> None:
    """图片：相对路径按源文件所在目录解析（与校验口径一致）。"""
    candidate = Path(src)
    if not candidate.is_absolute() and state.base_dir is not None:
        candidate = state.base_dir / src
    if candidate.is_file():
        paragraph.add_run().add_picture(str(candidate))
    else:
        paragraph.add_run(f"[图片缺失: {src}]")


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
