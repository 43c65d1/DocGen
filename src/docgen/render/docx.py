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
import re
from pathlib import Path
from typing import Any

from docx.oxml import OxmlElement

from ..config import INLINE_STYLE_NAMES, Config, build_style_table
from ..errors import E_CONFIG, DocGenError
from ..ir import (
    BlockNode,
    BlockQuote,
    Break,
    Code,
    CodeBlock,
    DiagonalHeader,
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
    SectionBreak,
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
    allocate_list_num_id,
    append_field,
    append_omml,
    append_text,
    apply_font,
    apply_three_line_borders,
    clean_document_xml,
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
    set_cell_border,
    set_cell_width,
    set_list_numbering,
    set_paragraph_alignment,
    set_paragraph_border,
    set_paragraph_indent,
    set_paragraph_shading,
    set_paragraph_spacing,
    set_run_shading,
    set_table_borders,
    set_table_width,
)
from .template import create_document

__all__ = ["render_docx", "render_docx_bytes"]

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: 代码块缺省等宽字体（config 没声明 font.name 时兜底）
DEFAULT_MONO_FONT = "Consolas"

#: 行内代码的默认底纹（与代码块的 F5F5F5 略区分；config 可覆盖或置空关闭）
DEFAULT_INLINE_CODE_FILL = "F2F2F2"


def render_docx(
    blocks: list[BlockNode],
    config: Config,
    output: Path,
    template: Path | None = None,
    base_dir: Path | None = None,
) -> Path:
    """渲染为 ``.docx`` 文件，返回写入路径。"""
    data = render_docx_bytes(blocks, config, template, base_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def render_docx_bytes(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None = None,
    base_dir: Path | None = None,
) -> bytes:
    """渲染到内存（测试用，避免落盘）。

    收尾顺序：存盘 → 删 ``stylesWithEffects`` 部件 → 清理多余的命名空间声明
    → 注入脚注部件。
    """
    from .footnotes import inject_footnotes
    from .template import _strip_effects_part

    document, footnotes, state = _build_document(blocks, config, template, base_dir)
    buffer = io.BytesIO()
    document.save(buffer)
    data = buffer.getvalue()
    drop_part = getattr(document, "_docgen_drop_part", "")
    if drop_part:
        data = _strip_effects_part(data, drop_part)
    data = _rewrite_zips_part(data, "word/document.xml", clean_document_xml)
    if not footnotes:
        return data
    footnote_style = state.styles.get("footnote")
    return inject_footnotes(
        data, footnotes, style=footnote_style if isinstance(footnote_style, dict) else None
    )


def _rewrite_zips_part(data: bytes, name: str, transform: Any) -> bytes:
    """把 zip 里某个部件的字节替换成 ``transform(旧字节)``。"""
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(data))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == name:
                payload = transform(payload)
            target.writestr(item, payload)
    source.close()
    return buffer.getvalue()


def _build_document(
    blocks: list[BlockNode],
    config: Config,
    template: Path | None,
    base_dir: Path | None,
) -> tuple[Any, list[str], _RenderState]:
    document = create_document(config, template)
    # 内容里有 [[sectionbreak]] 时按需建节，内容才能分进前面的节；
    # 否则沿用旧行为（一次建好所有节）。
    lazy = _has_section_break(blocks)
    sections = _apply_sections(document, config, lazy=lazy)
    state = _RenderState(
        document=document,
        config=config,
        styles=build_style_table(config),
        base_dir=base_dir,
    )
    state.sections = sections
    # 域缓存值：渲染时把真实编号写进产物，别指望查看器去更新域
    from ..numbering import baked_fields

    state.caption_fields = baked_fields(blocks)
    _render_blocks(state, blocks)
    sections.finish()
    _ensure_update_fields(document)
    _normalise_root(document)
    return document, state.footnotes, state


def _apply_sections(document: Any, config: Config, *, lazy: bool = False) -> Any:
    """``[[sections]]``：设置纸张/页边距/页码/页眉页脚（无配置时保持默认）。"""
    from .sections import apply_sections

    raw = config.extra.get("sections")
    specs = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return apply_sections(document, specs, lazy=lazy)


def _has_section_break(blocks: list[BlockNode]) -> bool:
    """内容里有没有 ``[[sectionbreak]]``（含嵌套在命名块/引用里的）。"""
    for block in blocks:
        if isinstance(block, SectionBreak):
            return True
        children = getattr(block, "content", None)
        if isinstance(children, list) and _has_section_break(children):
            return True
        items = getattr(block, "items", None)
        if isinstance(items, list):
            for item in items:
                if _has_section_break(item.content):
                    return True
    return False


def _normalise_root(document: Any) -> list[str]:
    """渲染完成后整理根元素的命名空间声明（见 ``normalise_document_root``）。"""
    from .ooxml import normalise_document_root

    return normalise_document_root(document)


class _RenderState:
    __slots__ = (
        "_bookmark_id",
        "base_dir",
        "caption_fields",
        "config",
        "default_east_asia",
        "doc_settings",
        "document",
        "footnote_reference_maker",
        "footnotes",
        "math_engine",
        "math_on_fail",
        "math_xsl",
        "sections",
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
        self.sections: Any = None
        self.caption_fields: dict[str, str] = {}
        self._bookmark_id = 1000
        self.footnotes: list[str] = []
        self.footnote_reference_maker: Any = None
        # 可选的配置键：代码块等场景要显式指定中文字体时用
        self.default_east_asia = str(config.document.get("font.east_asia", "")) or None

    def next_bookmark_id(self) -> int:
        self._bookmark_id += 1
        return self._bookmark_id

    def new_list_num_id(self) -> int | None:
        """给一个有序列表分配**独立的**编号实例，让它从 1 开始。

        逻辑在 :func:`ooxml.allocate_list_num_id`（要点：复用 ``List Number``
        样式指向的 ``abstractNum`` 保住外观，只追加一个新的 ``w:num``）。
        返回 ``None`` 时调用方退回“只挂样式”的老行为，构建不会失败。
        """
        return allocate_list_num_id(self.document)


# --------------------------------------------------------------------------
# 块级
# --------------------------------------------------------------------------
def _render_blocks(state: _RenderState, blocks: list[BlockNode]) -> None:
    for index, block in enumerate(blocks):
        previous = blocks[index - 1] if index else None
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        _render_block(state, block, previous=previous, following=following)


def _render_block(
    state: _RenderState,
    block: BlockNode,
    *,
    previous: BlockNode | None = None,
    following: BlockNode | None = None,
) -> None:
    """渲染一个块级节点。

    ``previous`` / ``following``：紧邻的前后块，用于两类排版约束：

    - 图片后面的图题：图片段落要 ``keepNext``（见 :func:`_renders_as_caption`）；
    - 表格前后的段落：Word 表格没有段距属性，间距要写到相邻段落上
      （见 :func:`_apply_table_gap`）。
    """
    if isinstance(block, Heading):
        _render_heading(state, block, previous=previous, following=following)
    elif isinstance(block, Paragraph):
        paragraph = state.document.add_paragraph()
        _apply_body_paragraph(state, paragraph, previous=previous, following=following)
        _render_inlines(state, paragraph, block.content, None)
    elif isinstance(block, ListBlock):
        _render_list(state, block)
    elif isinstance(block, CodeBlock):
        _render_code_block(state, block)
    elif isinstance(block, Formula):
        _render_formula(state, block)
    elif isinstance(block, ImageBlock):
        _render_image_block(state, block, following=following)
    elif isinstance(block, ThematicBreak):
        _render_thematic_break(state)
    elif isinstance(block, PageBreak):
        _render_page_break(state)
    elif isinstance(block, SectionBreak):
        _render_section_break(state)
    elif isinstance(block, BlockQuote):
        _render_block_quote(state, block)
    elif isinstance(block, Table):
        _render_table(state, block)
    elif isinstance(block, NamedBlock):
        _render_named_block(state, block, previous=previous, following=following)
    elif isinstance(block, Toc):
        _render_toc(state)


def _renders_as_caption(block: BlockNode | None) -> bool:
    """这个块会不会渲染成**题注段落**（与 :func:`_render_named_block` 的分支一致）。

    用来判断图片后面是否紧跟图题：是的话图片段落要 ``keepNext``。
    """
    if not isinstance(block, NamedBlock) or not block.label:
        return False
    from ..numbering import CAPTION_KINDS, caption_kind

    kind = caption_kind(block)
    # equation 走公式/编号分支，不会渲染成 Caption 段落
    return kind != "equation" and kind in CAPTION_KINDS


def _render_heading(
    state: _RenderState,
    block: Heading,
    *,
    previous: BlockNode | None = None,
    following: BlockNode | None = None,
) -> None:
    level = max(1, min(9, block.level))
    # 用样式「名」（Heading 1）而不是 style_id：python-docx 1.2 起后者会告警
    paragraph = state.document.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.keep_with_next = True
    # 标题只吃「对齐 + 段距」：不该继承正文的行距与首行缩进
    properties = {**state.doc_settings, **state.styles.get(f"heading{level}", {})}
    _apply_paragraph_properties(paragraph, properties, keys=("alignment", "space"))
    _apply_table_gap(state, paragraph, previous=previous, following=following)
    _render_inlines(state, paragraph, block.content, f"heading{level}")


def _apply_body_paragraph(
    state: _RenderState,
    paragraph: Any,
    *,
    previous: BlockNode | None = None,
    following: BlockNode | None = None,
) -> None:
    """正文段落：把 body 样式与 ``[document]`` 的段落级属性写进去。

    document 的值作为兜底，body 样式覆盖它（config 只有一个真源，但层级不同）。
    字体类属性不在这里写——它们进 ``Normal`` 样式（见
    :func:`template.apply_document_defaults`），否则每个 run 都要重复一遍。

    ``previous`` / ``following`` 用来实现「表格与相邻段落的间距」：Word 的表格
    没有段距属性，只能由表格前后的段落各写一条。
    """
    properties = {**state.doc_settings, **state.styles.get("body", {})}
    _apply_paragraph_properties(paragraph, properties)
    _apply_table_gap(state, paragraph, previous=previous, following=following)


def _apply_paragraph_properties(
    paragraph: Any,
    properties: dict[str, Any],
    *,
    keys: tuple[str, ...] = ("space", "line_spacing", "first_line_chars", "alignment"),
) -> None:
    """写段落级键：段前段后 / ``line_spacing`` / ``first_line_chars`` / ``alignment``。

    ``keys`` 用来限制哪些键生效：标题只取对齐与段距（不该继承正文的行距/首行缩进）。

    正文段落、题注段落共用——两处如果各写一套，很容易只在一处生效
    （「config 写了但不生效」的老毛病）。
    """
    if "space" in keys:
        before = properties.get("space_before")
        if before is not None:
            _apply_space(paragraph, "before", before)
        after = properties.get("space_after")
        if after is not None:
            _apply_space(paragraph, "after", after)
    if "line_spacing" in keys:
        spacing = properties.get("line_spacing")
        if spacing is not None:
            set_paragraph_spacing(paragraph, line_spacing=float(spacing))
    if "first_line_chars" in keys:
        indent = properties.get("first_line_chars")
        if indent is not None:
            set_paragraph_indent(paragraph, first_line_chars=int(indent))
    if "alignment" in keys:
        alignment = properties.get("alignment")
        if alignment:
            set_paragraph_alignment(paragraph, _normalise_alignment(str(alignment)))


#: 段前段后的行单位写法：``0.5 line`` / ``1行``（也接受 ``lines``）
_LINE_UNIT = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:lines?|行)\s*$", re.IGNORECASE)


def _apply_space(paragraph: Any, edge: str, value: Any) -> None:
    """按 config 值写段前/段后；单位决定走 ``w:before`` 还是 ``w:beforeLines``。

    - ``"6pt"`` / ``"12px"`` / ``"0.2cm"`` / 裸数字（按磅）→ ``w:before`` / ``w:after``；
    - ``"0.5 line"`` / ``"1行"`` → ``w:beforeLines`` / ``w:afterLines``（百分之一行）。

    解析失败时**报错**而不是静默丢弃——「写了不生效」正是这次要消灭的问题。
    """
    match = _LINE_UNIT.match(str(value))
    if match:
        lines = float(match.group(1))
        if edge == "before":
            set_paragraph_spacing(paragraph, before_lines=lines)
        else:
            set_paragraph_spacing(paragraph, after_lines=lines)
        return

    text = str(value).strip()
    length = length_from_text(text)
    if length is None:
        try:
            length = length_from_text(f"{float(text)}pt")
        except ValueError:
            length = None
    if length is None:
        raise DocGenError(
            E_CONFIG,
            f"无法解析段前/段后数值: {value!r}（支持 6pt / 12px / 0.2cm / 0.5 line）",
        )
    if edge == "before":
        set_paragraph_spacing(paragraph, before_points=length.pt)
    else:
        set_paragraph_spacing(paragraph, after_points=length.pt)


def _apply_table_gap(
    state: _RenderState,
    paragraph: Any,
    *,
    previous: BlockNode | None,
    following: BlockNode | None,
) -> None:
    """表格与相邻段落的间距（``[table] space_before`` / ``space_after``）。

    Word 的表格**没有**「表格前/后间距」属性，标准做法是：表格**前**的段落写段后距、
    表格**后**的段落写段前距。这里就按这个约定映射，于是「表格底线与正文紧贴」
    可以用一行 config 解决。
    """
    if not isinstance(previous, Table) and not isinstance(following, Table):
        return
    properties = _table_properties(state)
    if isinstance(previous, Table):
        value = properties.get("space_after")
        if value is not None:
            _apply_space(paragraph, "before", value)
    if isinstance(following, Table):
        value = properties.get("space_before")
        if value is not None:
            _apply_space(paragraph, "after", value)


#: config 里常见的对齐写法 → OOXML ``w:jc`` 的取值
ALIGNMENT_VALUES = {
    "left": "left",
    "start": "left",
    "right": "right",
    "end": "right",
    "center": "center",
    "centre": "center",
    "justify": "both",
    "both": "both",
    "distribute": "distribute",
}


def _normalise_alignment(value: str) -> str:
    """对齐值归一化：接受 ``justify`` 这类习惯写法，非法值退回 ``left``。

    不抛错是有意的：对齐是纯外观，写错不该让整篇文档构建失败；
    但也不静默丢弃——非法值按左对齐处理，并可通过 ``dump-styles`` 看到原值。
    """
    return ALIGNMENT_VALUES.get(value.strip().lower(), "left")


def _render_list(state: _RenderState, block: ListBlock) -> None:
    """渲染列表。

    有序列表**每个列表一个独立编号实例**（``w:num``）：Markdown 里两个列表是两段
    独立的列表，Word 里也应各自从 1 开始。原先所有段落共用 ``List Number`` 样式自带
    的 ``numId``，于是全文连续编号（第 2 段列表接着第 1 段往下数）——这是缺陷，
    不是设计。详见 ``_allocate_list_num_id``。
    """
    num_id = state.new_list_num_id() if block.ordered else None
    for item in block.items:
        _render_list_item(state, item, ordered=block.ordered, level=0, num_id=num_id)


def _render_list_item(
    state: _RenderState,
    item: ListItem,
    *,
    ordered: bool,
    level: int,
    num_id: int | None = None,
) -> None:
    base = "List Number" if ordered else "List Bullet"
    style = base if level == 0 else f"{base} {min(level + 1, 3)}"

    first = item.content[0] if item.content else None
    paragraph = state.document.add_paragraph(style=style)
    if ordered and num_id is not None:
        set_list_numbering(paragraph, num_id=num_id, level=level)
    if isinstance(first, Paragraph):
        _render_inlines(state, paragraph, first.content, None)
    elif first is not None:
        _render_block(state, first)

    for block in item.content[1:]:
        if isinstance(block, ListBlock):
            # 嵌套列表是**另一个**列表：有序时它也该从 1 开始
            nested_num_id = state.new_list_num_id() if block.ordered else None
            for nested in block.items:
                _render_list_item(
                    state,
                    nested,
                    ordered=block.ordered,
                    level=level + 1,
                    num_id=nested_num_id,
                )
        else:
            _render_block(state, block)


def _render_code_block(state: _RenderState, block: CodeBlock) -> None:
    properties = _code_properties(state, block.language)
    paragraph = state.document.add_paragraph()
    set_paragraph_spacing(paragraph, line_spacing=1.0)
    run = paragraph.add_run(block.content.rstrip("\n"))
    # eastAsia 留给样式链：等宽字体没有中文字形
    _apply_run_style(state, run, properties, east_asia=False)
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


def _render_image_block(
    state: _RenderState, block: ImageBlock, *, following: BlockNode | None = None
) -> None:
    """块级图片。紧跟图题时把两者绑成**不可跨页**的整体。

    学术排版的基本要求：图片与它的图题必须同页、图题紧贴图片下方。
    Word 里靠 ``w:keepNext``（段落与下一段同页）实现——原先只有标题设了它，
    图片没有，于是分页时会出现「图片在上一页、图题在下一页」。
    """
    paragraph = state.document.add_paragraph()
    width = block.width or _image_setting(state, "width")
    align = block.align or _image_setting(state, "align")
    if align:
        set_paragraph_alignment(paragraph, align)
    # 图片与正文的间距：``[image] space_before`` / ``space_after``
    for key, edge in (("space_before", "before"), ("space_after", "after")):
        value = _image_setting(state, key)
        if value:
            _apply_space(paragraph, edge, value)
    _add_picture(state, paragraph, block.src, width=width)
    if _renders_as_caption(following):
        paragraph.paragraph_format.keep_with_next = True


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
    """``---`` 分隔线：写**段落底边框**，不要输出一长串破折号。

    以前输出 ``"———" * 8``，产物里就是一行字面破折号——复制、检索、换字号都成问题。
    正确做法是空段落 + ``w:pBdr/w:bottom``（Word 会把边框画满正文宽度）。
    线段样式取 ``[document] hr.style`` / ``hr.color`` / ``hr.size``，缺省单实线。
    """
    paragraph = state.document.add_paragraph()
    set_paragraph_spacing(paragraph, before_points=6, after_points=6)
    style = str(state.config.setting("hr.style", "single")) or "single"
    color = str(state.config.setting("hr.color", "auto")) or "auto"
    size = str(state.config.setting("hr.size", "6")) or "6"
    set_paragraph_border(paragraph, "bottom", style=style, size=size, color=color)


def _render_page_break(state: _RenderState) -> None:
    paragraph = state.document.add_paragraph()
    paragraph.add_run()._element.append(make_page_break())


def _render_section_break(state: _RenderState) -> None:
    """``[[sectionbreak]]``：切到 ``[[sections]]`` 的下一条配置。

    分节标记比配置条数多时忽略多余标记（不报错——作者多写一个标记不该让构建失败）。
    """
    state.sections.advance()


def _render_block_quote(state: _RenderState, block: BlockQuote) -> None:
    for child in block.content:
        if isinstance(child, Paragraph):
            paragraph = state.document.add_paragraph(style="Quote")
            _render_inlines(state, paragraph, child.content, None)
        else:
            _render_block(state, child)


def _render_named_block(
    state: _RenderState,
    block: NamedBlock,
    *,
    previous: BlockNode | None = None,
    following: BlockNode | None = None,
) -> None:
    """命名块容器。

    - ``equation`` 带 ``number`` 属性 → 无边框三列表格（公式编号，W3）
    - ``caption``/``table``/``equation`` 带 ``#id`` → 题注（书签 + SEQ 域）
    - 其余情况：内容照常渲染

    ``previous`` / ``following`` 只对题注有用：表格题注也要吃
    ``[table] space_before/space_after``（表格间距写在相邻段落上）。
    """
    kind = caption_kind(block)
    if kind == "equation":
        # 方程：带 number 走三列表格，否则就是普通块级公式（不套题注语义）
        if block.attributes.get("number"):
            _render_numbered_formula(state, block)
            return
    elif block.label and kind in CAPTION_KINDS:
        _render_caption(state, block, previous=previous, following=following)
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


def _render_caption(
    state: _RenderState,
    block: NamedBlock,
    *,
    previous: BlockNode | None = None,
    following: BlockNode | None = None,
) -> None:
    from ..numbering import CAPTION_KINDS, caption_kind

    label = CAPTION_KINDS[caption_kind(block)]
    paragraph = state.document.add_paragraph(style="Caption")
    # 题注本身不能被分页拆开（两行的图题跨页读起来就是断的）
    paragraph.paragraph_format.keep_together = True
    # 段落级样式键（对齐/缩进/段距）也要吃 config，与正文段落同一套语义
    _apply_paragraph_properties(paragraph, state.styles.get("caption", {}))
    _apply_table_gap(state, paragraph, previous=previous, following=following)
    append_text(paragraph, f"{label} ")
    append_field(
        paragraph,
        make_caption_field(label),
        # 缓存值写**真实序号**：Word 会自动重算，但 WPS/预览/解包 XML 只认这个值
        state.caption_fields.get(block.label, "1"),
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
    """``[[ref:目标]]`` → ``REF 目标 \\h`` 域（域结果是题注编号）。

    缓存值取目标题注的真实编号（含前向引用：渲染前就算好了）。
    算不出来时留**空**而不是 ``"1"``——写死 1 会让读者看到错误编号，
    空结果至少不会撒谎，Word 打开时仍会按域指令重算。
    """
    append_field(
        paragraph,
        make_reference_field(target),
        state.caption_fields.get(target, ""),
    )


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
    # 先按正确列数建表：python-docx 的 ``add_table(rows, cols)`` 会为每行建 cols 个 ``w:tc``
    # （``cols`` 影响的是行内单元格，不是 ``tblGrid``），再确保 ``tblGrid`` 列数与之一致
    table = state.document.add_table(rows=len(block.rows), cols=columns)
    _fit_grid(table, columns)
    if properties.get("borders", "grid") == "grid":
        table.style = "Table Grid"

    widths = _column_widths(properties, columns, state)
    set_table_width(table, widths)
    for row_index, row in enumerate(block.rows):
        for column_index in range(columns):
            cell = table.cell(row_index, column_index)
            drop_empty_runs(cell.paragraphs[0])
            nodes = _cell_nodes(block, row_index, column_index)
            diagonal = next((node for node in nodes if isinstance(node, DiagonalHeader)), None)
            if diagonal is not None:
                # 斜线表头：线 + 两段文字（右上/左下），不能按普通 run 渲染
                _render_diagonal_cell(state, cell, diagonal, properties)
            elif nodes:
                # 有行内 IR 就渲染它：单元格里的粗体/代码/公式/链接都要保留
                _render_inlines(state, cell.paragraphs[0], nodes, None)
            else:
                text = row[column_index] if column_index < len(row) else ""
                run = cell.paragraphs[0].add_run(text)
                if row_index == 0:
                    run.bold = True
            if row_index == 0 and diagonal is None:
                for run in cell.paragraphs[0].runs:
                    run.bold = True
            _apply_cell_format(cell, widths[column_index], _column_alignment(block, column_index))
        if row_index == 0 and bool(properties.get("header_repeat", True)):
            repeat_table_header(table.rows[0])

    _apply_table_borders(table, properties, header_rows=1)


def _render_diagonal_cell(
    state: _RenderState, cell: Any, node: DiagonalHeader, properties: dict[str, Any]
) -> None:
    """斜线表头单元格：``w:tcBorders/tl2br``（左上→右下）+ 右上/左下两段文字。

    Word 的斜线是**单元格级**边框（``CT_TblBorders`` 没有斜线元素），所以只能逐格写。
    文字分两段：右上那段右对齐、左下那段左对齐——这是「项目\\年份」式表头的常规排法。
    """
    spec = _border_spec(properties)
    set_cell_border(cell, "tl2br", val="single", space="0", **spec)

    first = cell.paragraphs[0]
    set_paragraph_alignment(first, "right")
    if node.upper:
        first.add_run(node.upper)

    second = cell.add_paragraph()
    set_paragraph_alignment(second, "left")
    if node.lower:
        second.add_run(node.lower)


def _cell_nodes(block: Table, row: int, column: int) -> list[InlineNode]:
    """取单元格的行内 IR；没有则返回空列表（调用方回退纯文本）。"""
    if row < len(block.cell_nodes) and column < len(block.cell_nodes[row]):
        return block.cell_nodes[row][column]
    return []


def _fit_grid(table: Any, columns: int) -> int:
    """把 ``w:tblGrid`` 的列数对齐到 ``columns``，返回实际列数。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is None:
        grid = OxmlElement("w:tblGrid")
        table._tbl.insert(1, grid)
    while len(grid.findall(qn("w:gridCol"))) < columns:
        grid.append(OxmlElement("w:gridCol"))
    for extra in grid.findall(qn("w:gridCol"))[columns:]:
        grid.remove(extra)
    return columns


def _render_cell_table(state: _RenderState, block: Table) -> None:
    """结构化单元格（支持合并）。"""
    properties = _table_properties(state)
    rows = block.cells
    columns = sum(cell.colspan for cell in rows[0]) if rows else 0
    if not columns:
        return
    table = state.document.add_table(rows=len(rows), cols=columns)
    _fit_grid(table, columns)
    if properties.get("borders", "grid") == "grid":
        table.style = "Table Grid"

    widths = _column_widths(properties, columns, state)
    set_table_width(table, widths)
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
    if style not in TABLE_STYLES:
        raise DocGenError(
            E_CONFIG,
            f"[table] style 不支持: {style!r}（可用：{' / '.join(TABLE_STYLES)}）",
        )
    table["style"] = style
    # 边框行为直接由 style 决定；不再经过一层「未知就退回三线表」的映射，
    # 否则 custom 会被静默吞掉（实测踩到）
    table["borders"] = style
    if "header_repeat" not in table:
        table["header_repeat"] = True
    return table


#: 表格边框预设 + ``custom``（逐边配置）
TABLE_STYLES = ("three_line", "grid", "none", "custom")


def _column_widths(properties: dict[str, Any], columns: int, state: _RenderState) -> list[int]:
    """列宽（twips）：``[table] col_widths`` 给出相对比例；否则平均分。

    总和**必须**落在正文可用宽度内（页面宽 - 左右页边距），否则表格会超出页面——
    Word 与 LibreOffice 的表现不同，容易在渲染核对时才发现。
    """
    total = page_content_width(state.document)
    ratios = properties.get("col_widths")
    if (
        isinstance(ratios, list)
        and len(ratios) == columns
        and all(isinstance(item, (int, float)) and item > 0 for item in ratios)
    ):
        weight_sum = float(sum(ratios))
        widths = [int(total * float(item) / weight_sum) for item in ratios]
        # 取整误差可能让总和略超，最后一列吸收掉
        widths[-1] = max(1, widths[-1] - (sum(widths) - total))
        return widths
    return [total // columns] * columns


def _column_alignment(block: Table, index: int) -> str:
    if index < len(block.alignments):
        return block.alignments[index]
    return ""


def _apply_cell_format(cell: Any, width: int, alignment: str) -> None:
    set_cell_width(cell, width)
    if alignment:
        set_cell_alignment(cell, alignment)


def _border_spec(properties: dict[str, Any]) -> dict[str, str]:
    """``[table] line_size`` / ``line_color`` → CT_Border 属性（``sz`` 用 1/8 磅）。

    只在用户显式配置时返回；不配置就保持 Word 默认线（避免悄悄改变既有观感）。
    """
    spec: dict[str, str] = {}
    size = properties.get("line_size")
    if size is not None:
        length = length_from_text(str(size))
        if length is None and str(size).strip():
            try:
                length = length_from_text(f"{float(str(size).strip())}pt")
            except ValueError:
                length = None
        if length is None:
            raise DocGenError(
                E_CONFIG,
                f"无法解析 [table] line_size: {size!r}（支持 1pt / 0.5pt / 8px）",
            )
        spec["sz"] = str(max(2, min(96, round(length.pt * 8))))
    color = properties.get("line_color")
    if color is not None:
        spec["color"] = str(color).lstrip("#").upper() if str(color) != "auto" else "auto"
    return spec


#: 表格可用到的边（与 CT_TblBorders 的元素名一致）
TABLE_EDGES = ("top", "left", "bottom", "right", "insideH", "insideV")


def _table_edges(properties: dict[str, Any], spec: dict[str, str]) -> dict[str, str]:
    """按 ``[table] style`` + ``[table.edges]`` 算出每条边的线型。"""
    style = properties.get("borders", "three_line")
    line_style = str(properties.get("line_style", "single"))

    if style == "grid":
        values: dict[str, str] = {edge: line_style for edge in TABLE_EDGES}
    elif style == "custom":
        # custom：默认无框线，逐边由 [table.edges] 打开
        values = {edge: "none" for edge in TABLE_EDGES}
    else:  # none
        values = {edge: "none" for edge in TABLE_EDGES}

    overrides = properties.get("edges")
    if isinstance(overrides, dict):
        for edge, value in overrides.items():
            if edge not in TABLE_EDGES:
                raise DocGenError(
                    E_CONFIG,
                    f"[table.edges] 不认识的边: {edge!r}（可用：{', '.join(TABLE_EDGES)}）",
                )
            values[edge] = str(value)
    return values


def _apply_table_borders(table: Any, properties: dict[str, Any], header_rows: int) -> None:
    spec = _border_spec(properties)
    style = properties.get("borders", "three_line")
    if style == "three_line":
        apply_three_line_borders(table, header_rows=header_rows, spec=spec)
    else:
        edges = _table_edges(properties, spec)
        borders: dict[str, Any] = {}
        for edge, value in edges.items():
            borders[edge] = {"val": value, **spec} if value != "none" else {"val": "none"}
        set_table_borders(table, **borders)

    # 行间横线：每行（除最后一行）底部加一条线——Word 没有「行分隔线」概念，
    # 只能逐单元格写 tcBorders/bottom
    row_lines = properties.get("row_lines")
    if row_lines:
        line = (
            row_lines if isinstance(row_lines, str) else str(properties.get("line_style", "single"))
        )
        for row in list(table.rows)[:-1]:
            for cell in row.cells:
                set_cell_border(cell, "bottom", val=line, space="0", **spec)


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
        _render_inline_code(state, paragraph, node.content)
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
        _render_link(state, paragraph, node, context_style)
    elif isinstance(node, Image):
        _add_picture(state, paragraph, node.src)
    elif isinstance(node, DiagonalHeader):
        # 表格之外没有斜线的载体：两段文字拼起来当普通文本（不静默丢内容）
        text = " ".join(part for part in (node.upper, node.lower) if part)
        paragraph.add_run(text)


def _render_link(
    state: _RenderState,
    paragraph: Any,
    node: Link,
    context_style: str | None,
) -> None:
    """``[文字](url)`` → 真正的 Word 超链接（关系项 + ``w:hyperlink``），不是只加下划线。"""
    from .ooxml import wrap_external_hyperlink

    start = len(paragraph._p)
    _render_inlines(state, paragraph, node.content, context_style)
    if not node.url:
        for run in paragraph.runs:
            run.font.underline = True
        return
    hyperlink = wrap_external_hyperlink(state.document.part, paragraph, node.url, start)
    for run in hyperlink.findall(f"{_W_NS}r"):
        rpr = run.find(f"{_W_NS}rPr")
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            run.insert(0, rpr)
        color = rpr.find(f"{_W_NS}color")
        if color is None:
            color = OxmlElement("w:color")
            rpr.append(color)
        color.set(f"{_W_NS}val", "0563C1")  # Word 默认超链接蓝
        underline = rpr.find(f"{_W_NS}u")
        if underline is None:
            underline = OxmlElement("w:u")
            rpr.append(underline)
        underline.set(f"{_W_NS}val", "single")


def _render_inline_code(state: _RenderState, paragraph: Any, text: str) -> Any:
    """行内代码：等宽字体 + **run 级灰底**。

    段落里与表格单元格里都走这里，保证两处外观一致。
    底纹必须画在 run 上（``w:rPr/w:shd``）——段落底纹会涂满整行、看起来像代码块。
    """
    run = paragraph.add_run(text)
    properties = _code_properties(state, "")
    # 行内代码同理：等宽字体不写 eastAsia，中文仍走正文字体
    _apply_run_style(state, run, properties, east_asia=False)
    # 底纹优先级：config 的 inline_background > shading.fill > 引擎默认浅灰。
    # 默认值是为了「开了就有、且和代码块的 F5F5F5 略有区分」。
    # 想彻底关掉：config 写 inline_background = ""（空串不画底纹）。
    fill = properties.get(
        "inline_background", properties.get("shading.fill", DEFAULT_INLINE_CODE_FILL)
    )
    if isinstance(fill, str) and fill:
        set_run_shading(run, fill)
    return run


def _render_styled(
    state: _RenderState,
    paragraph: Any,
    node: Styled,
    context_style: str | None,
) -> None:
    """``Styled``：先渲染内容，再把样式属性写到这一段新建的 run 上。

    ``sup`` / ``sub`` 是**语义名**：即便 config 未声明 ``[styles.sup]``，仍走上下标
    （手册 §6.2.3 的 ``[上标]{.sup}`` 与 ``H~2~O``）。

    ``node.style_name`` 先经 ``[inline]`` 映射解析成**实际样式名**：
    ``[inline] sup = "sup_caret"`` 时 ``^x^`` 会去找 ``[styles.sup_caret]``。
    """
    semantic = node.style_name
    if semantic in INLINE_STYLE_NAMES:
        semantic = state.config.inline_style_name(semantic)
    properties = state.styles.get(semantic, {})
    start = len(paragraph.runs)
    _render_inlines(state, paragraph, node.content, context_style or None)

    if properties:
        for run in paragraph.runs[start:]:
            _apply_run_style(state, run, properties)
        # 段落级键也能通过行内样式表达：「署名行要居中且不缩进」这类需求，
        # 逐段开关会让 DFM 语法变复杂，而 `[署名]{.signature}` 已经能指到样式名。
        # 只认 alignment / first_line_chars —— 其余段落属性（间距等）仍归正文段落管。
        _apply_inline_paragraph_style(paragraph, properties)
    if node.style_name in ("sup", "sub"):
        # 上下标与 config 样式**都要生效**：以前这里提前 return，config 里的
        # [styles.sup] / [styles.sub]（如字号）会被整段丢掉（实测踩到）
        for run in paragraph.runs[start:]:
            _set_vertical_align(run, "superscript" if node.style_name == "sup" else "subscript")


def _apply_inline_paragraph_style(paragraph: Any, properties: dict[str, Any]) -> None:
    """把行内样式里的**段落级**键写到所在段落。

    支持 ``alignment`` / ``first_line_chars`` / ``space_before`` / ``space_after``。

    为什么允许：正文段落统一套 ``first_line_chars``（中文首行缩进 2 字符），
    但封面署名、图表标题这类段落需要 0 缩进或居中，而 DFM 没有块级样式语法。
    ``[文字]{.样式名}`` 是唯一能「就近指到某个样式」的写法，所以让它承载这些键。
    """
    before = properties.get("space_before")
    if before is not None:
        _apply_space(paragraph, "before", before)
    after = properties.get("space_after")
    if after is not None:
        _apply_space(paragraph, "after", after)
    alignment = properties.get("alignment")
    if alignment:
        set_paragraph_alignment(paragraph, _normalise_alignment(str(alignment)))
    indent = properties.get("first_line_chars")
    if indent is not None:
        set_paragraph_indent(paragraph, first_line_chars=int(indent))


def _set_vertical_align(run: Any, value: str) -> None:
    """写 ``w:vertAlign``（上下标）；``w:sz`` 的缩放由 Word 自己处理。"""
    from docx.oxml.ns import qn

    from .ooxml import insert_child

    insert_child(run._element.get_or_add_rPr(), "w:vertAlign", **{"w:val": value})
    assert run._element.find(qn("w:rPr")) is not None


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


def _apply_run_style(
    state: _RenderState,
    run: Any,
    properties: dict[str, Any],
    *,
    east_asia: bool = True,
) -> None:
    """把 config 的样式属性写进 run（只认已知字段，保证「config 驱动」）。

    支持两种取值写法：点号键展开成的嵌套表（``font.name``）与扁平键。

    ``east_asia``：`font.name` 是否同时写 ``w:eastAsia``。
    中文文档里**必须**写——Word 对 CJK 字符取的是 ``w:eastAsia``，
    只写 ascii/hAnsi/cs 时 `font.name = "黑体"` 对中文是空操作（实测反馈）。
    代码块/行内代码传 ``False``：等宽字体没有中文字形，eastAsia 要留给样式链，
    否则代码块里的中文会掉字体。
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
    underline = font.get("underline", properties.get("font.underline"))

    apply_font(
        run,
        str(name) if name else None,
        size=to_points(size) if size is not None else None,
        bold=bool(bold) if bold is not None else None,
        italic=bool(italic) if italic is not None else None,
        strike=bool(strike) if strike is not None else None,
        color=str(color) if color else None,
        underline=bool(underline) if underline is not None else None,
        east_asia=str(name) if name and east_asia else None,
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
    """代码块样式：base ``[code_block]`` 与语言变体 ``[code_block.<lang>]`` **深合并**。

    必须深合并：两者都可能带嵌套表（``font.color`` / ``font.name``），
    浅合并会让变体的 ``font.color`` 被 base 的 ``font`` 整个覆盖掉。
    """
    from ..config import deep_merge

    properties = dict(state.styles.get("code_block", {}))
    language = language.strip()
    if language:
        variant = state.styles.get(f"code_block.{language}")
        if variant:
            properties = deep_merge(properties, variant)
    return properties


def _points(value: Any) -> float:
    """已由 :mod:`docgen.units` 统一，这里只保留给旧调用点的薄包装。"""
    from ..units import to_points

    return float(to_points(value).pt)


def _ensure_update_fields(document: Any) -> None:
    """settings.xml 补 ``updateFields``：Word 打开时自动更新目录/编号域。

    **必须按 schema 顺序插入**，不能 ``append`` 到末尾：``CT_Settings`` 的元素顺序
    固定，排在错误位置时严格按 schema 解析的实现会直接忽略它——那种情况下连 Word
    都不会自动更新域，读者看到的就全是缓存值（实测反馈点名的第二处问题）。
    """
    from .ooxml import insert_child

    settings = document.settings.element
    if settings.find(f"{_W_NS}updateFields") is None:
        insert_child(settings, "w:updateFields", **{"w:val": "true"})
