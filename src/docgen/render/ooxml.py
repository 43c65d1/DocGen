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
    "apply_three_line_borders",
    "drop_empty_runs",
    "heading_style_id",
    "make_bookmark_end",
    "make_bookmark_start",
    "make_caption_field",
    "make_field",
    "make_footnote_reference",
    "make_math_paragraph",
    "make_page_break",
    "make_reference_field",
    "make_section_v_align",
    "make_toc_field",
    "make_update_fields",
    "merge_cell_horizontal",
    "merge_cell_vertical",
    "page_content_width",
    "repeat_table_header",
    "set_cell_alignment",
    "set_cell_width",
    "set_paragraph_alignment",
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
    east_asia: str | None = None,
    size: Length | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    strike: bool | None = None,
    color: str | None = None,
    superscript: bool | None = None,
    subscript: bool | None = None,
) -> None:
    """统一的字体入口。

    ``name`` 写西文（``ascii``/``hAnsi``/``cs``）；``east_asia`` 单独给中文。
    代码块这类场景应只设西文字体、把 eastAsia 留给样式链——否则中文会掉字体
    （把 ``eastAsia`` 也设成 Consolas 是错的）。

    ``color`` 接受 ``RRGGBB`` 或 ``#RRGGBB``（OOXML 不带 ``#``）。
    """
    if name is not None or east_asia is not None:
        _set_run_fonts(run, name, east_asia)
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


def _set_run_fonts(run: Any, name: str | None, east_asia: str | None = None) -> None:
    """写 ``rFonts``：西文三个属性 + 可选的中文（``eastAsia``）。"""
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    if name is not None:
        for attribute in ("w:ascii", "w:hAnsi", "w:cs"):
            fonts.set(qn(attribute), name)
    if east_asia is not None:
        fonts.set(qn("w:eastAsia"), east_asia)


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


def make_footnote_reference(footnote_id: int) -> Any:
    """正文里的脚注引用：``<w:footnoteReference w:id="N"/>``（要放在 ``w:r`` 里）。"""
    return _element("w:footnoteReference", **{"w:id": str(footnote_id)})


def set_paragraph_alignment(paragraph: Any, alignment: str) -> None:
    """段落对齐（图片常用）：``left`` / ``center`` / ``right``。"""
    ppr = paragraph._p.get_or_add_pPr()
    jc = ppr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        ppr.append(jc)
    jc.set(qn("w:val"), alignment)


def length_from_text(value: str) -> Any:
    """``2cm`` / ``1in`` / ``120px`` / ``10mm`` -> ``docx.shared`` 长度；无法识别返回 None。"""
    from docx.shared import Cm, Emu, Inches, Mm, Pt

    text = value.strip().lower()
    try:
        if text.endswith("cm"):
            return Cm(float(text[:-2]))
        if text.endswith("mm"):
            return Mm(float(text[:-2]))
        if text.endswith("in"):
            return Inches(float(text[:-2]))
        if text.endswith("px"):
            return Emu(int(float(text[:-2]) * 9525))  # 96 DPI：1px = 9525 EMU
        if text.endswith("pt"):
            return Pt(float(text[:-2]))
    except ValueError:
        return None
    return None


def make_field(instruction: str, placeholder: str = "") -> list[Any]:
    """构造一个简单域（``fldChar`` 三段式），如 ``SEQ``、``REF``、``PAGE``、``TOC``。

    **返回的是 ``w:r`` 列表**：``w:fldChar`` / ``w:instrText`` / ``w:t`` 必须包在 run 里，
    直接挂在 ``w:p`` 下会让 Word 判定文档损坏（这是实测踩到的坑）。
    """
    begin = _run_with(_element("w:fldChar", **{"w:fldCharType": "begin"}))

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    instr_run = _run_with(instr)

    separate = _run_with(_element("w:fldChar", **{"w:fldCharType": "separate"}))

    runs: list[Any] = [begin, instr_run, separate]
    if placeholder:
        text = OxmlElement("w:t")
        text.text = placeholder
        runs.append(_run_with(text))
    runs.append(_run_with(_element("w:fldChar", **{"w:fldCharType": "end"})))
    return runs


def _run_with(child: Any) -> Any:
    """把子元素包进 ``w:r``（run 是段落里唯一合法的容器）。"""
    run = OxmlElement("w:r")
    run.append(child)
    return run


def make_toc_field(levels: str = "1-9", placeholder: str = "按 F9 更新目录") -> list[Any]:
    """目录域：``TOC \\o "1-9" \\h \\z \\u``。"""
    return make_field(f'TOC \\o "{levels}" \\h \\z \\u', placeholder)


def make_page_break() -> Any:
    return _element("w:br", **{"w:type": "page"})


def make_bookmark_start(name: str, bookmark_id: int) -> Any:
    return _element("w:bookmarkStart", **{"w:id": str(bookmark_id), "w:name": name})


def make_bookmark_end(bookmark_id: int) -> Any:
    return _element("w:bookmarkEnd", **{"w:id": str(bookmark_id)})


def drop_empty_runs(paragraph: Any) -> int:
    """删掉段落里的空 ``<w:r/>``（python-docx 清空单元格时会留下），返回删除数量。"""
    target = getattr(paragraph, "_p", paragraph)
    removed = 0
    for run in list(target.findall(qn("w:r"))):
        if len(run) == 0:
            target.remove(run)
            removed += 1
    return removed


def append_field(
    parent: Any,
    instruction: str,
    placeholder: str = "",
    bookmark: str = "",
    bookmark_id: int = 0,
) -> None:
    """把域（``fldChar`` 三段式）挂到段落上；每个片段都是独立的 ``w:r``。

    给了 ``bookmark`` 就把**书签只包住域结果**（编号），这样 ``REF`` 域取到的是
    ``1`` 而不是整条题注文字。``bookmark_id`` 由调用方提供，保证：
    start/end 同 id、且**整篇文档内不重复**（重复会让 REF 取错书签）。
    """
    target = getattr(parent, "_p", parent)
    if bookmark:
        target.append(make_bookmark_start(bookmark, bookmark_id))
    for run in make_field(instruction, placeholder):
        target.append(run)
    if bookmark:
        target.append(make_bookmark_end(bookmark_id))


def append_text(parent: Any, text: str) -> None:
    """往段落里塞一段裸文本（域之间夹的文字，如「图」「：」），同样包在 run 里。"""
    target = getattr(parent, "_p", parent)
    element = OxmlElement("w:t")
    element.set(qn("xml:space"), "preserve")
    element.text = text
    target.append(_run_with(element))


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


def page_content_width(document: Any) -> int:
    """正文可用宽度（twips）：页面宽 - 左右页边距（1 twip = 635 EMU）。"""
    section = document.sections[-1]
    usable = int(section.page_width) - int(section.left_margin) - int(section.right_margin)
    return max(1, usable // 635)


def set_cell_width(cell: Any, width_twips: int) -> None:
    """固定列宽：写 ``w:tcW``（``dxa`` = twips）。"""
    tcpr = cell._tc.get_or_add_tcPr()
    element = tcpr.find(qn("w:tcW"))
    if element is None:
        element = OxmlElement("w:tcW")
        tcpr.insert(0, element)
    element.set(qn("w:w"), str(width_twips))
    element.set(qn("w:type"), "dxa")


def set_cell_alignment(cell: Any, alignment: str) -> None:
    """列对齐（GFM 分隔行）：给单元格里所有段落写 ``w:jc``。"""
    for paragraph in cell.paragraphs:
        ppr = paragraph._p.get_or_add_pPr()
        jc = ppr.find(qn("w:jc"))
        if jc is None:
            jc = OxmlElement("w:jc")
            ppr.append(jc)
        jc.set(qn("w:val"), alignment)


def repeat_table_header(row: Any) -> None:
    """重复表头：``w:trPr/w:tblHeader``，跨页时表头自动重复。"""
    trpr = row._tr.get_or_add_trPr()
    if trpr.find(qn("w:tblHeader")) is None:
        trpr.append(OxmlElement("w:tblHeader"))


def merge_cell_horizontal(table: Any, row: int, column: int, span: int = 1) -> None:
    """横向合并：给起始单元格写 ``w:gridSpan``。"""
    cell = table.cell(row, column)
    tcpr = cell._tc.get_or_add_tcPr()
    element = tcpr.find(qn("w:gridSpan"))
    if element is None:
        element = OxmlElement("w:gridSpan")
        tcpr.append(element)
    element.set(qn("w:val"), str(max(2, span)))


def merge_cell_vertical(table: Any, row: int, column: int, offset: int) -> None:
    """纵向合并：起始格 ``w:vMerge val="restart"``，被并格 ``w:vMerge``（continue）。"""
    target_row = row + offset
    cell = table.cell(target_row, column)
    tcpr = cell._tc.get_or_add_tcPr()
    element = tcpr.find(qn("w:vMerge"))
    if element is None:
        element = OxmlElement("w:vMerge")
        tcpr.append(element)
    if offset == 0:
        element.set(qn("w:val"), "restart")
    else:
        element.attrib.pop(qn("w:val"), None)


def apply_three_line_borders(table: Any, header_rows: int = 1) -> None:
    """三线表：顶线 + 底线 + 表头下横线；其余框线为 none。"""
    set_table_borders(
        table,
        top="single",
        bottom="single",
        left="none",
        right="none",
        insideH="none",
        insideV="none",
    )
    for index in range(header_rows):
        if index < len(table.rows):
            _set_row_bottom_border(table.rows[index], "single")


def _set_row_bottom_border(row: Any, style: str) -> None:
    for cell in row.cells:
        tcpr = cell._tc.get_or_add_tcPr()
        borders = tcpr.find(qn("w:tcBorders"))
        if borders is None:
            borders = OxmlElement("w:tcBorders")
            tcpr.append(borders)
        bottom = borders.find(qn("w:bottom"))
        if bottom is None:
            bottom = OxmlElement("w:bottom")
            borders.append(bottom)
        bottom.set(qn("w:val"), style)
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "0")
        bottom.set(qn("w:color"), "auto")


def heading_style_id(level: int) -> str:
    """标题层级 -> Word 样式 id（``Heading1`` ~ ``Heading6``）。"""
    return f"Heading{max(1, min(6, level))}"
