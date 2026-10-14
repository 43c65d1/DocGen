"""分节 / 页码 / 页眉页脚 / 封面（完整版手册 W5）。

``[[sections]]`` 是一组 TOML 表（数组），每个描述一节：

```toml
[[sections]]
page.size = "A4"              # A4 / Letter / A3
page.margin.top = 2.5         # 单位：cm
numbering.format = "upperRoman"  # decimal / upperRoman / lowerRoman / upperLetter
numbering.start = 1           # 可选，重启页码
header.text = "封面"           # 可选
footer.text = "第 PAGE 页"     # 可选，PAGE 会变成页码域
cover = true                  # 可选，页面垂直居中（封面）
```

约定：**每个节独立设置页眉页脚**（``is_linked_to_previous = False``），
否则 Word 会把上一节的内容继承过来——手册 §17.1 明确点名的坑。
"""

from __future__ import annotations

from typing import Any

from docx.enum.section import WD_SECTION_START
from docx.shared import Cm

__all__ = ["apply_sections", "page_sizes"]

#: 纸张尺寸（厘米）：Word 常用几种
page_sizes: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "A5": (14.8, 21.0),
    "Letter": (21.59, 27.94),
    "Legal": (21.59, 35.56),
}

#: 页码格式 -> OOXML ``w:fmt``
NUMBER_FORMATS = {
    "decimal": "decimal",
    "upperRoman": "upperRoman",
    "lowerRoman": "lowerRoman",
    "upperLetter": "upperLetter",
    "lowerLetter": "lowerLetter",
    "chineseCounting": "chineseCounting",
}

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def apply_sections(document: Any, sections: list[dict[str, Any]]) -> list[Any]:
    """按配置设置文档分节，返回处理过的 section 列表。

    第 1 条配置作用于文档**已有**的节；后续每条新建一节（``nextPage``）。
    """
    if not sections:
        return list(document.sections)

    handled: list[Any] = []
    existing = list(document.sections)

    for index, spec in enumerate(sections):
        if index == 0:
            section = existing[0]
        else:
            section = document.add_section(WD_SECTION_START.NEW_PAGE)
        _apply_page(section, spec)
        _apply_numbering(section, spec)
        _apply_cover(section, spec)
        _apply_header_footer(section, spec)
        handled.append(section)
    return handled


def _apply_page(section: Any, spec: dict[str, Any]) -> None:
    page = spec.get("page")
    page = page if isinstance(page, dict) else {}
    size = str(page.get("size", "A4"))
    width_cm, height_cm = page_sizes.get(size, page_sizes["A4"])
    if "width" in page:
        width_cm = float(page["width"])
    if "height" in page:
        height_cm = float(page["height"])
    section.page_width = Cm(width_cm)
    section.page_height = Cm(height_cm)

    margin = page.get("margin")
    margin = margin if isinstance(margin, dict) else {}
    if "top" in margin:
        section.top_margin = Cm(float(margin["top"]))
    if "bottom" in margin:
        section.bottom_margin = Cm(float(margin["bottom"]))
    if "left" in margin:
        section.left_margin = Cm(float(margin["left"]))
    if "right" in margin:
        section.right_margin = Cm(float(margin["right"]))


def _apply_numbering(section: Any, spec: dict[str, Any]) -> None:
    """页码：``w:pgNumType``（格式 + 可选重启）+ 页脚里的 PAGE 域。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    numbering = spec.get("numbering")
    numbering = numbering if isinstance(numbering, dict) else {}
    fmt = NUMBER_FORMATS.get(str(numbering.get("format", "")), "")
    start = numbering.get("start")
    if not fmt and start is None:
        return

    sect_pr = section._sectPr
    element = sect_pr.find(qn("w:pgNumType"))
    if element is None:
        element = OxmlElement("w:pgNumType")
        sect_pr.append(element)
    if fmt:
        element.set(qn("w:fmt"), fmt)
    if start is not None:
        element.set(qn("w:start"), str(int(start)))


def _apply_cover(section: Any, spec: dict[str, Any]) -> None:
    """封面：页面垂直居中（走 ``sectPr`` 的 ``w:vAlign``，不是段落 spacing）。"""
    from .ooxml import make_section_v_align

    if not spec.get("cover"):
        return
    sect_pr = section._sectPr
    from docx.oxml.ns import qn

    if sect_pr.find(qn("w:vAlign")) is not None:
        return
    sect_pr.append(make_section_v_align("center"))


def _apply_header_footer(section: Any, spec: dict[str, Any]) -> None:
    """页眉页脚：每节独立（``is_linked_to_previous = False``）。"""
    header_text = _text_setting(spec, "header")
    footer_text = _text_setting(spec, "footer")

    if header_text:
        section.header.is_linked_to_previous = False
        _write_paragraph(section.header.paragraphs[0], header_text, align="center")
    if footer_text:
        section.footer.is_linked_to_previous = False
        _write_paragraph(
            section.footer.paragraphs[0], footer_text, align="center", with_page_field=True
        )


def _text_setting(spec: dict[str, Any], key: str) -> str:
    """``header = {text = "..."}`` 与 ``header.text = "..."`` 两种写法都支持。"""
    value = spec.get(key)
    if isinstance(value, dict):
        return str(value.get("text", "") or "")
    nested = spec.get(f"{key}.text")
    return str(nested) if nested else ""


def _write_paragraph(
    paragraph: Any, text: str, *, align: str = "center", with_page_field: bool = False
) -> None:
    """写页眉页脚段落；文本里的 ``PAGE`` 会变成页码域。"""
    from .ooxml import append_field, append_text, set_paragraph_alignment

    set_paragraph_alignment(paragraph, align)
    if with_page_field and "PAGE" in text:
        before, _, after = text.partition("PAGE")
        if before:
            append_text(paragraph, before)
        append_field(paragraph, "PAGE", "1")
        if after:
            append_text(paragraph, after)
        return
    append_text(paragraph, text)
