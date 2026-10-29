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
    "CHILD_ORDER",
    "FONT_ATTRS",
    "HYPERLINK_RELATIONSHIP",
    "allocate_list_num_id",
    "append_field",
    "append_omml",
    "append_text",
    "apply_font",
    "apply_three_line_borders",
    "clean_document_xml",
    "drop_empty_runs",
    "heading_style_id",
    "insert_child",
    "make_bookmark_end",
    "make_bookmark_start",
    "make_caption_field",
    "make_field",
    "make_footnote_reference",
    "make_indent",
    "make_math_paragraph",
    "make_page_break",
    "make_reference_field",
    "make_section_v_align",
    "make_toc_field",
    "make_update_fields",
    "merge_cell_horizontal",
    "merge_cell_vertical",
    "normalise_document_root",
    "page_content_width",
    "repeat_table_header",
    "set_cell_alignment",
    "set_cell_width",
    "set_list_numbering",
    "set_paragraph_alignment",
    "set_paragraph_border",
    "set_paragraph_indent",
    "set_paragraph_shading",
    "set_paragraph_spacing",
    "set_run_color",
    "set_run_shading",
    "set_run_size",
    "set_style_outline_level",
    "set_table_borders",
    "set_table_cell_width",
    "set_table_width",
    "set_vert_align",
    "wrap_external_hyperlink",
]

#: ``w:rFonts`` 的四个属性：少任何一个都会导致中英混排或西文回退
FONT_ATTRS = ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs")


def _element(tag: str, **attributes: str) -> Any:
    element = OxmlElement(tag)
    for name, value in attributes.items():
        element.set(qn(name), value)
    return element


#: 各容器的子元素**合法顺序**（OOXML 的属性容器是 ``xsd:sequence``：顺序错的位置会被忽略）。
#: 这张表由 ``tests/schemas/ecma-376/wml.xsd`` 反推，并由 ``test_ooxml_schema.py`` 兜住，
#: 不要凭记忆改。
def _qnames(names: str) -> tuple[str, ...]:
    """``"pStyle spacing ind"`` -> ``("w:pStyle", "w:spacing", "w:ind")``。"""
    return tuple(f"w:{name}" for name in names.split())


CHILD_ORDER: dict[str, tuple[str, ...]] = {
    "w:pPr": _qnames(
        "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr "
        "suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap "
        "overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd "
        "snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc "
        "textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr "
        "sectPr pPrChange"
    ),
    "w:rPr": _qnames(
        "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss "
        "imprint noProof snapToGrid vanish webHidden color spacing w kern position sz "
        "szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang "
        "eastAsianLayout specVanish oMath"
    ),
    "w:sectPr": _qnames(
        "footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType "
        "cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid "
        "printerSettings sectPrChange"
    ),
    "w:tblPr": _qnames(
        "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize "
        "tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook "
        "tblCaption tblDescription tblPrChange"
    ),
    "w:tcPr": _qnames(
        "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection "
        "tcFitText vAlign hideMark"
    ),
    # 框线：``top`` 在 ``left`` 之前、``insideH`` 在最后（schema 如此，别按“上下左右”写）
    "w:tblBorders": _qnames("top start left bottom end right insideH insideV"),
    "w:tcBorders": _qnames("top start left bottom end right insideH insideV"),
    "w:pBdr": _qnames("top left bottom right between bar"),
    # CT_NumPr：ilvl 必须在 numId 之前（顺序错了 Word 静默忽略编号）
    "w:numPr": _qnames("ilvl numId numberingChange ins del"),
}

#: ``w:ind`` 的**属性**顺序（属性顺序对 XML 不敏感，这里表驱动只为输出确定性）
IND_ATTRS: tuple[str, ...] = (
    "w:start",
    "w:startChars",
    "w:end",
    "w:endChars",
    "w:left",
    "w:leftChars",
    "w:right",
    "w:rightChars",
    "w:hanging",
    "w:hangingChars",
    "w:firstLine",
    "w:firstLineChars",
)


def make_indent(**attributes: str) -> Any:
    """构造 ``w:ind``。

    ``firstLine`` 与 ``hanging`` 在 schema 里是 **choice（互斥）**：
    同时给出会被判非法，所以有 ``firstLine*`` 时自动丢弃 ``hanging*``。
    """
    element = OxmlElement("w:ind")
    has_first_line = "w:firstLine" in attributes or "w:firstLineChars" in attributes
    for name in IND_ATTRS:
        value = attributes.get(name)
        if value is None or value == "":
            continue
        if has_first_line and name in ("w:hanging", "w:hangingChars"):
            continue
        element.set(qn(name), str(value))
    return element


def insert_child(parent: Any, name: str, **attributes: str) -> Any:
    """按 schema 顺序把 ``name`` 插到 ``parent`` 里（已存在则返回并补属性）。

    所有「加一条属性」的操作都应走这里而不是 ``append``，
    否则元素落在 sequence 的错误位置、被 Word 静默忽略。
    """
    existing = parent.find(qn(name))
    if existing is not None:
        for attribute, value in attributes.items():
            existing.set(qn(attribute), value)
        return existing

    element = _element(name, **attributes)
    order = CHILD_ORDER.get(_local_name(parent))
    if order is None or name not in order:
        parent.append(element)
        return element

    rank = order.index(name)
    for index, child in enumerate(parent):
        child_name = _local_name(child)
        child_rank = order.index(child_name) if child_name in order else rank
        if child_rank > rank:
            parent.insert(index, element)
            return element
    parent.append(element)
    return element


def _local_name(element: Any) -> str:
    tag = str(element.tag)
    return "w:" + tag.split("}")[-1] if "}" in tag else tag


#: 根元素上``xmlns:`` 声明 -> 该前缀的命名空间 URI（用于清理未使用的声明）
_KNOWN_PREFIXES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "w10": "urn:schemas-microsoft-com:office:word",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "mo": "http://schemas.microsoft.com/office/mac/office/2008/main",
    "mv": "urn:schemas-microsoft-com:mac:vml",
}


def normalise_document_root(document: Any) -> list[str]:
    """去掉根元素上的 ``mc:Ignorable``（Markup Compatibility 机制）。

    默认模板会写 ``mc:Ignorable="w14 wp14"``——那要求消费者实现 mc 处理，
    严格 schema 校验会直接报「属性不允许」。未使用的**命名空间声明**由
    :func:`clean_document_xml` 在序列化后按字节清掉（lxml 的 ``nsmap`` 删除是空操作）。
    """
    root = document._element
    ignorable = "{" + _KNOWN_PREFIXES["mc"] + "}Ignorable"
    if root.get(ignorable) is None:
        return []
    del root.attrib[ignorable]
    return ["mc:Ignorable"]


def clean_document_xml(data: bytes) -> bytes:
    """从 ``document.xml`` 里删掉**未被引用**的命名空间声明。

    lxml 会在根元素上原样保留模板带来的 ``v``/``o``/``w10``/``wps``/``wp14``… 声明
    （``nsmap`` 删除不生效），但它们对应的前缀在文档里根本没用到——
    对严格 schema 校验是无意义噪声，也会让产物不稳定。这里按字节清理。

    判据必须是**真正用到的前缀**，且要覆盖三种写法：
    元素名（``<w:p>``）、属性名（``r:id``，lxml 会把它变成完整 URI，必须从**原始文本**看）、
    属性值（``w:val`` 之类一般不需要，但一并兜住）。
    不能拿 URI 做子串计数——``xmlns:w14`` 的值里就含 ``w`` 的 URI（实测踩到）。
    """
    text = data.decode("utf-8")
    for prefix, uri in _KNOWN_PREFIXES.items():
        declaration = f'xmlns:{prefix}="{uri}"'
        if declaration not in text:
            continue
        if f"<{prefix}:" in text or f" {prefix}:" in text or f'"{prefix}:' in text:
            continue
        text = text.replace(f" {declaration}", "")
    return text.encode("utf-8")


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
    underline: bool | None = None,
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
    if underline is not None:
        insert_child(
            run._element.get_or_add_rPr(), "w:u", **{"w:val": "single" if underline else "none"}
        )
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
    """段前段后：优先用 ``beforeLines``/``afterLines``（行单位），与钉住的排版细则一致。

    ``beforeLines`` / ``afterLines`` 都是 ``w:spacing`` 的**属性**（顺序也在 ``w:ind`` 之前）。
    """
    pf = paragraph.paragraph_format
    if before_points is not None:
        pf.space_before = _points(before_points)
    if after_points is not None:
        pf.space_after = _points(after_points)
    if before_lines is not None or after_lines is not None or line_spacing is not None:
        ppr = paragraph._p.get_or_add_pPr()
        spacing = insert_child(ppr, "w:spacing")
        if before_lines is not None:
            spacing.set(qn("w:beforeLines"), str(before_lines * 100))
        if after_lines is not None:
            spacing.set(qn("w:afterLines"), str(after_lines * 100))
    if line_spacing is not None:
        pf.line_spacing = line_spacing


def set_paragraph_indent(
    paragraph: Any,
    *,
    first_line_chars: int | None = None,
    left_chars: int | None = None,
) -> None:
    """首行缩进用 ``firstLineChars``（字符单位，200 = 2 字符），不用 ``firstLine``。

    两个属性都挂在 ``w:ind`` 上，**属性名不同**（``w:firstLineChars`` / ``w:leftChars``），
    别写成 ``w:val``。``w:ind`` 在 schema 里排在 ``w:spacing`` 之后、``w:jc`` 之前。
    """
    if first_line_chars is not None:
        _set_indent_child(paragraph, "w:firstLineChars", str(first_line_chars))
    if left_chars is not None:
        _set_indent_child(paragraph, "w:leftChars", str(left_chars * 100))


def _set_indent_child(paragraph: Any, attribute: str, value: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    indent = insert_child(ppr, "w:ind")
    indent.set(qn(attribute), value)


def _points(value: float) -> Any:
    from docx.shared import Pt

    return Pt(value)


def set_paragraph_shading(
    paragraph: Any, fill: str, *, color: str = "auto", pattern: str = "clear"
) -> None:
    """段落底纹（代码块背景）：``<w:shd w:val="clear" w:fill="F5F5F5"/>``。"""
    ppr = paragraph._p.get_or_add_pPr()
    shading = insert_child(ppr, "w:shd", **{"w:val": pattern, "w:color": color})
    shading.set(qn("w:fill"), fill.lstrip("#").upper())


def set_run_shading(run: Any, fill: str, *, color: str = "auto", pattern: str = "clear") -> None:
    """run 底纹（行内代码的灰底）：``w:rPr/w:shd``。

    必须画在 **run** 上而不是段落：段落底纹会把整行涂上，看起来像代码块。
    """
    rpr = run._element.get_or_add_rPr()
    shading = insert_child(rpr, "w:shd", **{"w:val": pattern, "w:color": color})
    shading.set(qn("w:fill"), fill.lstrip("#").upper())


def _border_color(color: str) -> str:
    """框线颜色：``auto`` 必须保持**小写**，其余转大写十六进制。

    ``w:ST_HexColor`` 是「``auto`` 或 ``RRGGBB``」的联合类型——
    写成 ``AUTO`` 会被 schema 判为非法值（实测被 ``test_ooxml_schema`` 抓到）。
    """
    text = color.lstrip("#")
    return "auto" if text.lower() == "auto" else text.upper()


def set_paragraph_border(
    paragraph: Any, edge: str, *, style: str = "single", size: str = "4", color: str = "CCCCCC"
) -> None:
    """段落边框（代码块外框 / 分隔线）：``edge`` 取 ``top``/``left``/``bottom``/``right``。"""
    ppr = paragraph._p.get_or_add_pPr()
    borders = insert_child(ppr, "w:pBdr")
    element = insert_child(borders, f"w:{edge}")
    element.set(qn("w:val"), style)
    element.set(qn("w:sz"), size)
    element.set(qn("w:space"), "4")
    element.set(qn("w:color"), _border_color(color))


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
    insert_child(ppr, "w:jc", **{"w:val": align})
    return True


def set_style_outline_level(style: Any, level: int) -> None:
    """标题样式必须带 ``w:outlineLvl``，否则导航窗格与 TOC 不认。"""
    ppr = style.element.get_or_add_pPr()
    insert_child(ppr, "w:outlineLvl", **{"w:val": str(level)})


def make_update_fields() -> Any:
    """``settings.xml`` 里的 ``<w:updateFields w:val="true"/>``：打开时自动更新域。"""
    return _element("w:updateFields", **{"w:val": "true"})


#: 办公文档的超链接关系类型（Office 全系列用同一个 URI）
HYPERLINK_RELATIONSHIP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)


def wrap_external_hyperlink(part: Any, paragraph: Any, url: str, start: int) -> Any:
    """把段落里从 ``start`` 起新增的 run 包进 ``<w:hyperlink>``，返回该元素。

    超链接必须**同时**写两处，只加下划线只是视觉假象、点不动：

    1. 关系项 ``word/_rels/document.xml.rels`` 登记 Target（外链带 ``TargetMode="External"``）
    2. 正文里 ``<w:hyperlink r:id="rIdN">`` 引用它

    ``start`` 是包裹前的 ``len(paragraph.runs)``。这些 run 成为 ``w:hyperlink`` 的
    **子元素**后，``paragraph.runs`` 就不再把它们算进来（python-docx 只认直接子级）。
    """
    relation_id = part.relate_to(url, HYPERLINK_RELATIONSHIP, is_external=True)
    hyperlink = _element("w:hyperlink", **{"r:id": relation_id})
    for child in list(paragraph._p)[start:]:
        if _local_name(child) in ("w:r", "w:ins"):
            hyperlink.append(child)
    paragraph._p.append(hyperlink)
    return hyperlink


def make_footnote_reference(footnote_id: int) -> Any:
    """正文里的脚注引用：``<w:footnoteReference w:id="N"/>``（要放在 ``w:r`` 里）。"""
    return _element("w:footnoteReference", **{"w:id": str(footnote_id)})


def set_paragraph_alignment(paragraph: Any, alignment: str) -> None:
    """段落对齐（图片常用）：``left`` / ``center`` / ``right``。"""
    ppr = paragraph._p.get_or_add_pPr()
    insert_child(ppr, "w:jc", **{"w:val": alignment})


def set_list_numbering(paragraph: Any, *, num_id: int, level: int = 0) -> None:
    """给列表段落绑定**具体的**编号实例：``w:numPr``（``ilvl`` + ``numId``）。

    为什么要显式绑定：段落只挂 ``List Number`` 样式时，编号来自样式自带的
    ``numId``，于是**全文所有有序列表共用一个计数**（第二个列表接着第一个数下去）。
    每个列表各配一个 ``w:num``，才能各自从 1 开始。
    """
    ppr = paragraph._p.get_or_add_pPr()
    num_pr = insert_child(ppr, "w:numPr")
    insert_child(num_pr, "w:ilvl", **{"w:val": str(level)})
    insert_child(num_pr, "w:numId", **{"w:val": str(num_id)})


def allocate_list_num_id(document: Any) -> int | None:
    """为**一个**有序列表分配独立的编号实例，返回新的 ``numId``。

    复用 ``List Number`` 样式指向的 ``abstractNum``（外观不变），只追加一个新的
    ``<w:num>``。**必须同时写 ``lvlOverride/startOverride``**：实测 Word 对
    「多个 ``w:num`` 共用一个 ``abstractNum``」默认**接着数**（第 2 个列表从 3.
    继续），只有显式 ``startOverride=1`` 才真正各自从 1 开始。

    找不到样式/编号部件时返回 ``None``，调用方退回“只挂样式”的老行为。
    """
    try:
        numbering = document.part.numbering_part.element
    except (AttributeError, NotImplementedError):  # pragma: no cover - 无编号部件
        return None

    style_num_id: int | None = None
    for style in document.styles:
        if style.style_id != "ListNumber":
            continue
        for element in style.element.findall(".//" + qn("w:numId")):
            raw = element.get(qn("w:val"))
            if raw and raw.isdigit():
                style_num_id = int(raw)
                break
        if style_num_id is not None:
            break
    if style_num_id is None:  # pragma: no cover - 默认模板一定有
        return None

    abstract_id: int | None = None
    for num in numbering.findall(qn("w:num")):
        if num.get(qn("w:numId")) != str(style_num_id):
            continue
        ref = num.find(qn("w:abstractNumId"))
        raw = ref.get(qn("w:val")) if ref is not None else None
        if raw and raw.isdigit():
            abstract_id = int(raw)
        break
    if abstract_id is None:  # pragma: no cover - 默认模板一定有
        return None

    existing = [
        int(num.get(qn("w:numId"), "0"))
        for num in numbering.findall(qn("w:num"))
        if (num.get(qn("w:numId")) or "").isdigit()
    ]
    new_id = max(existing, default=0) + 1
    num = _element("w:num", **{"w:numId": str(new_id)})
    num.append(_element("w:abstractNumId", **{"w:val": str(abstract_id)}))
    for level in _abstract_num_levels(numbering, abstract_id):
        override = _element("w:lvlOverride", **{"w:ilvl": str(level)})
        override.append(_element("w:startOverride", **{"w:val": "1"}))
        num.append(override)
    numbering.append(num)
    return new_id


def _abstract_num_levels(numbering: Any, abstract_id: int) -> list[int]:
    """``abstractNum`` 定义了哪几级（``w:lvl/@w:ilvl``）；找不到就退回 0..8。"""
    for abstract in numbering.findall(qn("w:abstractNum")):
        if abstract.get(qn("w:abstractNumId")) != str(abstract_id):
            continue
        levels = [
            int(raw)
            for lvl in abstract.findall(qn("w:lvl"))
            if (raw := lvl.get(qn("w:ilvl"))) and raw.isdigit()
        ]
        return sorted(levels) if levels else list(range(9))
    return list(range(9))  # pragma: no cover - 编号定义缺失时兜底


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

    ``begin`` 带 ``w:dirty="true"``（做法参考 pandoc）：强制 Word 打开时重算该域，
    比只依赖 ``settings.xml`` 的 ``updateFields`` 更可靠——后者在部分版本/另存后不生效。
    """
    begin = _run_with(_element("w:fldChar", **{"w:fldCharType": "begin", "w:dirty": "true"}))

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
    """设置表格边框：``edges`` 形如 ``top="single"``、``insideH="none"``。

    按 ``CHILD_ORDER`` 的顺序写入——参数书写顺序（如先 bottom 后 left）与 schema 不一致时，
    直接 append 会产出非法顺序，Word 会丢掉后面的边。
    """
    tbl_pr = table._tbl.tblPr
    borders = insert_child(tbl_pr, "w:tblBorders")
    _write_borders(borders, edges)


def _write_borders(borders: Any, edges: dict[str, str]) -> None:
    ordered = CHILD_ORDER.get(_local_name(borders), ())
    names = [name for name in ordered if name.split(":")[-1] in edges]
    names += [f"w:{key}" for key in edges if f"w:{key}" not in names]
    for name in names:
        edge = name.split(":")[-1]
        element = borders.find(qn(name))
        if element is None:
            element = OxmlElement(name)
            borders.append(element)
        element.set(qn("w:val"), edges[edge])


def set_table_cell_width(cell: Any, width: Length) -> None:
    cell.width = width


def page_content_width(document: Any) -> int:
    """正文可用宽度（twips）：页面宽 - 左右页边距（1 twip = 635 EMU）。

    注意不要在表格宽度里额外扣 ``w:tblCellMar``：已用「纯 python-docx 手写对照文档」
    验证过，页边距口径就是这一条；多扣会让表格明显偏窄。
    """
    section = document.sections[-1]
    usable = int(section.page_width) - int(section.left_margin) - int(section.right_margin)
    return max(1, usable // 635)


def set_cell_width(cell: Any, width_twips: int) -> None:
    """固定列宽：写 ``w:tcW``（``dxa`` = twips）。"""
    tcpr = cell._tc.get_or_add_tcPr()
    insert_child(tcpr, "w:tcW", **{"w:w": str(width_twips), "w:type": "dxa"})


def set_cell_alignment(cell: Any, alignment: str) -> None:
    """列对齐（GFM 分隔行）：给单元格里所有段落写 ``w:jc``。"""
    for paragraph in cell.paragraphs:
        insert_child(paragraph._p.get_or_add_pPr(), "w:jc", **{"w:val": alignment})


def set_table_width(table: Any, widths: list[int]) -> None:
    """固定表格总宽与每列宽（``w:tblW`` + ``w:tblLayout fixed`` + ``w:gridCol``）。

    不设总宽时 Word 用 ``auto``，会按内容重算列宽，把表格撑出页面。
    """
    tbl_pr = table._tbl.tblPr
    insert_child(tbl_pr, "w:tblW", **{"w:w": str(sum(widths)), "w:type": "dxa"})
    insert_child(tbl_pr, "w:tblLayout", **{"w:type": "fixed"})

    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is None:
        return
    for column, width in zip(grid.findall(qn("w:gridCol")), widths, strict=False):
        column.set(qn("w:w"), str(width))


def repeat_table_header(row: Any) -> None:
    """重复表头：``w:trPr/w:tblHeader``，跨页时表头自动重复。"""
    trpr = row._tr.get_or_add_trPr()
    if trpr.find(qn("w:tblHeader")) is None:
        trpr.append(OxmlElement("w:tblHeader"))


def merge_cell_horizontal(table: Any, row: int, column: int, span: int = 1) -> None:
    """横向合并：给起始单元格写 ``w:gridSpan``。"""
    cell = table.cell(row, column)
    tcpr = cell._tc.get_or_add_tcPr()
    insert_child(tcpr, "w:gridSpan", **{"w:val": str(max(2, span))})


def merge_cell_vertical(table: Any, row: int, column: int, offset: int) -> None:
    """纵向合并：起始格 ``w:vMerge val="restart"``，被并格 ``w:vMerge``（continue）。"""
    target_row = row + offset
    cell = table.cell(target_row, column)
    tcpr = cell._tc.get_or_add_tcPr()
    if offset == 0:
        insert_child(tcpr, "w:vMerge", **{"w:val": "restart"})
    else:
        insert_child(tcpr, "w:vMerge")


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
        borders = insert_child(tcpr, "w:tcBorders")
        bottom = insert_child(borders, "w:bottom")
        bottom.set(qn("w:val"), style)
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "0")
        bottom.set(qn("w:color"), "auto")


def heading_style_id(level: int) -> str:
    """标题层级 -> Word 样式 id（``Heading1`` ~ ``Heading6``）。"""
    return f"Heading{max(1, min(6, level))}"
