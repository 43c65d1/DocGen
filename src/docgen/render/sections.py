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

**内容怎么分到各节**：正文里写 ``[[sectionbreak]]`` 就切到下一节。没有分节标记时
沿用旧行为（开头一次性建好所有节，内容都在最后一节）——这时 ``cover = true``
只表示「这一节页面垂直居中」，不会凭空塞进内容。
"""

from __future__ import annotations

from typing import Any

from docx.enum.section import WD_SECTION_START
from docx.shared import Cm

__all__ = ["SectionController", "apply_sections", "page_sizes"]

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


def apply_sections(
    document: Any, sections: list[dict[str, Any]], *, lazy: bool = False
) -> SectionController:
    """按配置设置文档分节，返回控制器（``lazy`` 决定是否按需建节）。"""
    return SectionController(document, sections, lazy=lazy)


class SectionController:
    """按 ``[[sections]]`` 配置管理文档的节。

    **为什么要控制器**：早期实现一上来就把所有节建好，于是内容只能落进最后一节，
    前面几节都是空页——``cover = true`` 就变成「一页空白封面」（实测反馈）。

    现在的行为：

    - ``lazy=True``（内容里有 ``[[sectionbreak]]``）：只先套用第 1 节配置，
      遇到分节标记再建下一节，内容因此能分到正确的节里；
    - ``lazy=False``（旧行为）：一次性建好所有节，保持既有文档不被打乱；
    - 渲染结束时若还有没用到的配置，补成空节——配置不该被静默忽略。
    """

    def __init__(self, document: Any, specs: list[dict[str, Any]], *, lazy: bool = False) -> None:
        self.document = document
        self.specs = specs
        self.sections: list[Any] = []
        self._index = -1
        self._document_sections = list(document.sections)
        if not specs:
            return
        self._apply(0)
        if not lazy:
            for _ in range(1, len(specs)):
                self._append()

    def advance(self) -> bool:
        """``[[sectionbreak]]``：切到下一节配置。没有更多配置时返回 ``False``。"""
        if self._index + 1 >= len(self.specs):
            return False
        self._append()
        return True

    def finish(self) -> None:
        """渲染结束：把未用到的配置补成空节（保证节数 = 配置条数）。"""
        while self._index + 1 < len(self.specs):
            self._append()

    def _apply(self, index: int) -> Any:
        self._index = index
        if index == 0:
            section = self._document_sections[0]
        else:
            section = self.document.add_section(WD_SECTION_START.NEW_PAGE)
        spec = self.specs[index]
        _apply_page(section, spec)
        _apply_numbering(section, spec)
        _apply_cover(section, spec)
        _apply_header_footer(section, spec)
        _drop_rsids(section)
        self.sections.append(section)
        return section

    def _append(self) -> Any:
        return self._apply(self._index + 1)


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
    from docx.oxml.ns import qn

    from .ooxml import insert_child

    numbering = spec.get("numbering")
    numbering = numbering if isinstance(numbering, dict) else {}
    fmt = NUMBER_FORMATS.get(str(numbering.get("format", "")), "")
    start = numbering.get("start")
    if not fmt and start is None:
        return

    attributes: dict[str, str] = {}
    if fmt:
        attributes["w:fmt"] = fmt
    if start is not None:
        attributes["w:start"] = str(int(start))
    # 必须按 schema 顺序插入：``w:pgNumType`` 要排在 ``w:cols`` / ``w:docGrid`` 之前
    insert_child(section._sectPr, "w:pgNumType", **attributes)
    assert section._sectPr.find(qn("w:pgNumType")) is not None


def _apply_cover(section: Any, spec: dict[str, Any]) -> None:
    """页面垂直对齐：**每节显式设置**，不依赖「上一节留下的值」。

    ``cover = true`` → ``w:vAlign val="center"``；否则显式写 ``val="top"``。

    **为什么显式**：python-docx 的 ``add_section`` 会克隆上一节的 ``sectPr``，
    所以「非封面节只删除 vAlign」是隐含依赖——依赖克隆行为、也依赖删除时机，
    真正的意图是「这一节是否垂直居中」，直接写出来最清楚。
    ``w:vAlign`` 在 schema 里排在 ``w:docGrid`` **之前**，所以用 ``insert_child`` 而非 append。
    """
    from .ooxml import insert_child

    value = "center" if spec.get("cover") else "top"
    insert_child(section._sectPr, "w:vAlign", **{"w:val": value})


def _drop_rsids(section: Any) -> None:
    """清掉母版带来的 ``w:rsid*``：修订标记对生成文档没有意义，还会让产出不稳定。"""
    from docx.oxml.ns import qn

    sect_pr = section._sectPr
    for attribute in ("w:rsidR", "w:rsidRPr", "w:rsidSect", "w:rsidDel"):
        sect_pr.attrib.pop(qn(attribute), None)


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
