"""OOXML 片段构造（完整版手册 §7 / §17.1）。

**所有** ``OxmlElement`` 构造都集中在这里：渲染层不直接拼 XML，这样 Word 的
命名空间、属性拼写和「陷阱」只有一处需要维护。

已知陷阱（手册 §17.1）都在这层处理：

- 中英混排必须四个 ``w:rFonts`` 属性齐全（``ascii`` / ``hAnsi`` / ``eastAsia`` / ``cs``）
- 首行缩进用 ``firstLineChars``（字符单位），不用 ``firstLine``
- 段前段后用 ``beforeLines`` / ``afterLines``
- 标题必须写 ``w:outlineLvl``，否则导航窗格与目录不认
- ``<w:updateFields w:val="true"/>`` 让 Word 打开时自动更新域
"""

from __future__ import annotations

from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Length

__all__ = [
    "FONT_ATTRS",
    "append_field",
    "append_omml",
    "append_text",
    "apply_font",
    "heading_style_id",
    "make_bookmark_end",
    "make_bookmark_start",
    "make_caption_field",
    "make_field",
    "make_math_paragraph",
    "make_page_break",
    "make_reference_field",
    "make_section_v_align",
    "make_toc_field",
    "make_update_fields",
    "set_paragraph_border",
    "set_paragraph_indent",
    "set_paragraph_shading",
    "set_paragraph_spacing",
    "set_run_color",
    "set_run_size",
    "set_style_outline_level",
    "set_table_borders",
    "set_table_cell_width",
    "set_vert_align",
]

#: ``w:rFonts`` 的四个属性：少任何一个都会导致中英混排或西文回退
FONT_ATTRS = ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs")


def _element(tag: str, **attributes: str) -> Any:
    element = OxmlElement(tag)
    for name, value in attributes.items():
        element.set(qn(name), value)
    return element


def apply_font(
    run: Any,
    name: str | None = None,
    *,
    size: Length | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    strike: bool | None = None,
    color: str | None = None,
    superscript: bool | None = None,
    subscript: bool | None = None,
) -> None:
    """统一的字体入口：四个 ``rFonts`` 属性一起写，避免 eastAsia 遗漏。

    ``color`` 接受 ``RRGGBB`` 或 ``#RRGGBB``（OOXML 不带 ``#``）。
    """
    if name is not None:
        _set_run_fonts(run, name)
    if size is not None:
        run.font.size = size
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if strike is not None:
        run.font.strike = strike
    if color is not None:
        set_run_color(run, color)
    if superscript is not None:
        run.font.superscript = superscript
    if subscript is not None:
        run.font.subscript = subscript


def _set_run_fonts(run: Any, name: str) -> None:
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attribute in FONT_ATTRS:
        fonts.set(qn(attribute), name)


def set_run_color(run: Any, color: str) -> None:
    run.font.color.rgb = _rgb(color)


def set_run_size(run: Any, size: Length) -> None:
    run.font.size = size


def _rgb(value: str) -> Any:
    from docx.shared import RGBColor

    return RGBColor.from_string(value.lstrip("#").upper())


def set_paragraph_spacing(
    paragraph: Any,
    *,
    before_points: float | None = None,
    after_points: float | None = None,
    line_spacing: float | None = None,
    before_lines: int | None = None,
    after_lines: int | None = None,
) -> None:
    """段前段后：优先用 ``beforeLines``/``afterLines``（行单位），与钉住的排版细则一致。"""
    pf = paragraph.paragraph_format
    if before_points is not None:
        pf.space_before = _points(before_points)
    if after_points is not None:
        pf.space_after = _points(after_points)
    if before_lines is not None:
        _set_pf_child(paragraph, "w:beforeLines", str(before_lines * 100))
    if after_lines is not None:
        _set_pf_child(paragraph, "w:afterLines", str(after_lines * 100))
    if line_spacing is not None:
        pf.line_spacing = line_spacing


def set_paragraph_indent(
    paragraph: Any,
    *,
    first_line_chars: int | None = None,
    left_chars: int | None = None,
) -> None:
    """首行缩进用 ``firstLineChars``（字符单位，200 = 2 字符），不用 ``firstLine``。"""
    if first_line_chars is not None:
        _set_pf_child(paragraph, "w:firstLineChars", str(first_line_chars))
    if left_chars is not None:
        _set_pf_child(paragraph, "w:leftChars", str(left_chars * 100))


def _set_pf_child(paragraph: Any, tag: str, value: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    element = ppr.find(qn(tag))
    if element is None:
        element = OxmlElement(tag)
        ppr.append(element)
    element.set(qn("w:val"), value)


def _points(value: float) -> Any:
    from docx.shared import Pt

    return Pt(value)


def set_paragraph_shading(
    paragraph: Any, fill: str, *, color: str = "auto", pattern: str = "clear"
) -> None:
    """段落底纹（代码块背景）：``<w:shd w:val="clear" w:fill="F5F5F5"/>``。"""
    ppr = paragraph._p.get_or_add_pPr()
    shading = ppr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        ppr.append(shading)
    shading.set(qn("w:val"), pattern)
    shading.set(qn("w:color"), color)
    shading.set(qn("w:fill"), fill.lstrip("#").upper())


def set_paragraph_border(
    paragraph: Any, edge: str, *, style: str = "single", size: str = "4", color: str = "CCCCCC"
) -> None:
    """段落边框（代码块外框）：``edge`` 取 ``top``/``left``/``bottom``/``right``。"""
    ppr = paragraph._p.get_or_add_pPr()
    borders = ppr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        ppr.append(borders)
    element = borders.find(qn(f"w:{edge}"))
    if element is None:
        element = OxmlElement(f"w:{edge}")
        borders.append(element)
    element.set(qn("w:val"), style)
    element.set(qn("w:sz"), size)
    element.set(qn("w:space"), "4")
    element.set(qn("w:color"), color.lstrip("#").upper())


def append_omml(parent: Any, omml: str) -> bool:
    """把 OMML 片段解析成元素并挂到 ``parent``（段落或其 ``w:p``）。

    返回是否成功。OMML 命名空间声明缺失时会补上——否则 Word 打不开文档。
    """
    if not omml.strip():
        return False
    from lxml import etree

    from .math import omml_fragment

    try:
        element = etree.fromstring(omml_fragment(omml).encode("utf-8"))
    except etree.XMLSyntaxError:
        return False
    target = getattr(parent, "_p", parent)
    target.append(element)
    return True


def make_math_paragraph(paragraph: Any, omml: str, *, align: str = "center") -> bool:
    """块级公式：把 OMML 放进段落并居中（公式段落不应带首行缩进）。"""
    if not append_omml(paragraph, omml):
        return False
    ppr = paragraph._p.get_or_add_pPr()
    jc = ppr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        ppr.append(jc)
    jc.set(qn("w:val"), align)
    return True


def set_style_outline_level(style: Any, level: int) -> None:
    """标题样式必须带 ``w:outlineLvl``，否则导航窗格与 TOC 不认。"""
    ppr = style.element.get_or_add_pPr()
    outline = ppr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = OxmlElement("w:outlineLvl")
        ppr.append(outline)
    outline.set(qn("w:val"), str(level))


def make_update_fields() -> Any:
    """``settings.xml`` 里的 ``<w:updateFields w:val="true"/>``：打开时自动更新域。"""
    return _element("w:updateFields", **{"w:val": "true"})


def make_field(instruction: str, placeholder: str = "") -> list[Any]:
    """构造一个简单域（``fldChar`` 三段式），如 ``SEQ``、``REF``、``PAGE``、``TOC``。"""
    begin = _element("w:fldChar", **{"w:fldCharType": "begin"})
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    separate = _element("w:fldChar", **{"w:fldCharType": "separate"})
    end = _element("w:fldChar", **{"w:fldCharType": "end"})

    elements: list[Any] = [begin, instr, separate]
    if placeholder:
        text = OxmlElement("w:t")
        text.text = placeholder
        elements.append(text)
    elements.append(end)
    return elements


def make_toc_field(levels: str = "1-9", placeholder: str = "按 F9 更新目录") -> list[Any]:
    """目录域：``TOC \\o "1-9" \\h \\z \\u``。"""
    return make_field(f'TOC \\o "{levels}" \\h \\z \\u', placeholder)


def make_page_break() -> Any:
    return _element("w:br", **{"w:type": "page"})


def make_bookmark_start(name: str, bookmark_id: int) -> Any:
    return _element("w:bookmarkStart", **{"w:id": str(bookmark_id), "w:name": name})


def make_bookmark_end(bookmark_id: int) -> Any:
    return _element("w:bookmarkEnd", **{"w:id": str(bookmark_id)})


def append_field(parent: Any, instruction: str, placeholder: str = "") -> None:
    """把域（``fldChar`` 三段式）直接挂到段落的 XML 上。

    与 :func:`make_field` 的区别：那个返回元素列表给 run 用，这个负责挂载，
    是渲染层的便捷入口（题注 ``SEQ``、引用 ``REF``、目录 ``TOC`` 都走它）。
    """
    target = getattr(parent, "_p", parent)
    for element in make_field(instruction, placeholder):
        target.append(element)


def append_text(parent: Any, text: str) -> None:
    """往段落里塞一段裸文本（域之间夹的文字，如「图」「：」）。"""
    target = getattr(parent, "_p", parent)
    run = OxmlElement("w:r")
    element = OxmlElement("w:t")
    element.set(qn("xml:space"), "preserve")
    element.text = text
    run.append(element)
    target.append(run)


def make_caption_field(kind_label: str) -> str:
    """题注编号域：``SEQ 图 \\* ARABIC``（Word 打开时自动递增）。"""
    return f"SEQ {kind_label} \\* ARABIC"


def make_reference_field(bookmark: str) -> str:
    """交叉引用域：``REF 书签名 \\h``（``\\h`` = 超链接）。"""
    return f"REF {bookmark} \\h"


def make_section_v_align(align: str = "center") -> Any:
    """封面垂直居中：走 ``sectPr`` 的 ``w:vAlign``，不是段落 spacing。"""
    return _element("w:vAlign", **{"w:val": align})


def set_vert_align(cell: Any, align: str = "center") -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    element = tcpr.find(qn("w:vAlign"))
    if element is None:
        element = OxmlElement("w:vAlign")
        tcpr.append(element)
    element.set(qn("w:val"), align)


def set_table_borders(table: Any, **edges: str) -> None:
    """设置表格边框：``edges`` 形如 ``top="single"``、``insideH="none"``。"""
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge, value in edges.items():
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), value)


def set_table_cell_width(cell: Any, width: Length) -> None:
    cell.width = width


def heading_style_id(level: int) -> str:
    """标题层级 -> Word 样式 id（``Heading1`` ~ ``Heading6``）。"""
    return f"Heading{max(1, min(6, level))}"
