"""母版构建（完整版手册 §14.1 / §14.3）。

剪枝版与 W0 用的是 python-docx 自带模板：已有 ``Heading 1``~``Heading 9``、
``Caption``、``Body Text``、``List Bullet/Number``，但**没有目录样式**
（``TOC 1``~``TOC 9``）也**没有多级标题编号**——W3（编号/题注）与 W5（目录）依赖它们。

本模块在默认母版上补齐 §14.1 清单里缺的槽位，产出的 ``.docx`` 可直接当母版入库
（``docgen/templates/default/word/`` 解包目录），CI 可重建：

- ``TOC 1``~``TOC 9`` 样式（目录域渲染时按级别套用）
- ``numbering.xml`` 里追加多级标题编号（``Heading1``~``Heading9`` 绑定 ``numId``）
- 样式 ``w:rFonts`` 四属性齐全、``HeadingN`` 带 ``outlineLvl``
- ``settings.xml`` 带 ``updateFields``

**母版只提供结构与槽位**：一切格式值仍由引擎从 config 写入。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from docx import Document as _Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..config import Config
from ..units import to_points
from .ooxml import make_update_fields, set_style_outline_level

__all__ = [
    "HEADING_NUMBER_ID",
    "TOC_LEVELS",
    "add_heading_numbering",
    "add_toc_styles",
    "build_template",
    "ensure_update_fields",
]

#: 标题多级编号使用的 numId（母版内固定，W3 的编号映射依赖它）
HEADING_NUMBER_ID = 100
#: 目录层级（TOC 1..9）
TOC_LEVELS = range(1, 10)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def build_template(config: Config | None = None, output: Path | None = None) -> Any:
    """构建规范母版：默认模板 + 补齐的目录样式与多级标题编号。

    返回 python-docx ``Document``；给了 ``output`` 就同时落盘为 ``.docx``。
    """
    from .template import apply_document_defaults, heading_indent, heading_numbering_enabled

    document = _Document()
    if config is not None:
        apply_document_defaults(document, config)
    add_toc_styles(document)
    add_heading_numbering(
        document,
        enabled=heading_numbering_enabled(config) if config else True,
        indent=heading_indent(config) if config else None,
    )
    ensure_update_fields(document)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output))
    return document


def add_toc_styles(document: Any) -> list[str]:
    """补 ``TOC 1``~``TOC 9`` 样式（目录必须显式定义这些样式，手册 §17.1）。"""
    created: list[str] = []
    for level in TOC_LEVELS:
        name = f"TOC {level}"
        if _has_style(document, name):
            continue
        style = document.styles.add_style(name, 1)  # 1 = paragraph style
        style.base_style = document.styles["Normal"]
        style.quick_style = True
        style.hidden = False
        # 目录条目通常带左缩进；具体数值由 config 在渲染期覆盖
        style.paragraph_format.left_indent = to_points(level * 0.5)
        _set_style_id(style, f"TOC{level}")
        created.append(name)
    return created


def _set_style_id(style: Any, style_id: str) -> None:
    """显式设置 ``w:styleId``：稳定、语义化（手册 §14.1 要求）。"""
    style.element.set(qn("w:styleId"), style_id)


def add_heading_numbering(
    document: Any,
    num_id: int = HEADING_NUMBER_ID,
    levels: int = 9,
    enabled: bool = True,
    indent: dict[str, Any] | None = None,
) -> int:
    """给标题加多级编号：``Heading1`` -> ``1``、``Heading2`` -> ``1.1``……

    返回新写入的 ``abstractNumId``；若已存在则直接返回现值（幂等）。
    ``enabled=False`` 时不建立编号、也不把 ``HeadingN`` 绑上去。
    ``indent`` 控制编号带来的缩进（``[document] heading_indent``）：

    - ``None``：默认 ``left=720*hanging=360``（每级递增，Word 常见观感）
    - ``{}`` 或显式 ``left=0``：**取消缩进**，标题齐头
    - ``{"left": "1cm"}`` / ``{"leftChars": 100}``：自定义距离（见 ``_indent_element``）

    注意：**``outlineLvl`` 与编号无关**，关闭编号后目录/导航窗格照常工作。
    """
    if not enabled:
        return num_id

    numbering = document.part.numbering_part.element
    if _has_abstract_num(numbering, num_id):
        return num_id

    abstract = _build_heading_abstract_num(num_id, levels, indent)
    numbering.insert(0, abstract)
    numbering.append(_build_num(num_id, num_id))
    _link_headings_to_numbering(document, num_id, levels)
    return num_id


def _has_abstract_num(numbering: Any, num_id: int) -> bool:
    for element in numbering.findall(f"{_W}abstractNum"):
        if element.get(qn("w:abstractNumId")) == str(num_id):
            return True
    return False


def _has_style(document: Any, name: str) -> bool:
    return any(style.name == name for style in document.styles)


def _build_heading_abstract_num(
    num_id: int, levels: int, indent: dict[str, Any] | None = None
) -> Any:
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(num_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "multilevel")
    abstract.append(multi)

    for level in range(levels):
        abstract.append(_level_element(level, indent))
    return abstract


def _level_element(level: int, indent: dict[str, Any] | None = None) -> Any:
    """一个编号层级。

    ``indent`` 的三态语义见 :func:`add_heading_numbering`；
    默认每级递增 720 twips（Word 多级编号的常见观感）。
    """
    element = OxmlElement("w:lvl")
    element.set(qn("w:ilvl"), str(level))

    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    element.append(start)

    fmt = OxmlElement("w:numFmt")
    fmt.set(qn("w:val"), "decimal")
    element.append(fmt)

    text = OxmlElement("w:lvlText")
    text.set(qn("w:val"), _level_text(level))
    element.append(text)

    justify = OxmlElement("w:lvlJc")
    justify.set(qn("w:val"), "left")
    element.append(justify)

    indent_element = _indent_element(indent)
    if indent_element is not None:
        ppr = OxmlElement("w:pPr")
        ppr.append(indent_element)
        element.append(ppr)

    style_link = OxmlElement("w:pStyle")
    style_link.set(qn("w:val"), f"Heading{level + 1}")
    element.append(style_link)
    return element


def _indent_element(indent: dict[str, Any] | None) -> Any:
    """把 ``[document] heading_indent`` 变成 ``w:ind``；返回 ``None`` 表示不加缩进。

    * ``None``（未配置）→ 默认 ``left=720 twips`` + ``hanging=360``
    * ``{}`` 或 ``left=0`` → 返回 ``None``（**取消缩进**）
    * ``{"left": "1cm"}`` / ``{"leftChars": 100}`` / ``{"firstLineChars": 200}``
      → 按给定值（带单位的长度或字符数）
    """
    from .ooxml import make_indent

    if indent is None:
        return make_indent(**{"w:left": "720", "w:hanging": "360"})
    if not indent:
        return None

    attributes: dict[str, str] = {}
    for key, value in indent.items():
        if key == "leftChars":
            attributes["w:leftChars"] = str(int(float(value)))
            continue
        if key == "firstLineChars":
            attributes["w:firstLineChars"] = str(int(float(value)))
            continue
        if not isinstance(value, (int, float, str)):
            continue
        twips = _to_twips(value)
        if key == "left":
            attributes["w:left"] = str(twips)
        elif key == "first_line":
            attributes["w:firstLine"] = str(twips)
        elif key == "hanging":
            attributes["w:hanging"] = str(twips)

    if attributes.get("w:left") == "0" and len(attributes) == 1:
        return None  # 显式 left=0 = 取消缩进
    return make_indent(**attributes) if attributes else None


def _to_twips(value: Any) -> int:
    """长度 -> twips：``1cm`` / ``10mm`` / ``0.5in`` / ``24pt`` / ``16px``；纯数字按 twips。

    单位换算用 ``docx.shared`` 的长度类（EMU），1 twip = 635 EMU；
    不认的单位抛 ``ValueError``（由调用方决定是否忽略）。
    """
    from docx.shared import Cm, Emu, Inches, Mm, Pt

    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return 0
    if text.isdigit():
        return int(text)

    length: Any
    if text.endswith("cm"):
        length = Cm(float(text[:-2]))
    elif text.endswith("mm"):
        length = Mm(float(text[:-2]))
    elif text.endswith("in"):
        length = Inches(float(text[:-2]))
    elif text.endswith("pt"):
        length = Pt(float(text[:-2]))
    elif text.endswith("px"):
        length = Emu(int(float(text[:-2]) * 9525))  # 96 DPI
    else:
        return int(float(text))
    # 长度类都是 int 子类（EMU），1 twip = 635 EMU
    return round(int(length) / 635)


def _level_text(level: int) -> str:
    """``%1``、``%1.%2``、``%1.%2.%3``……（Word 的多级编号占位符）。"""
    return ".".join(f"%{index}" for index in range(1, level + 2))


def _build_num(num_id: int, abstract_id: int) -> Any:
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract = OxmlElement("w:abstractNumId")
    abstract.set(qn("w:val"), str(abstract_id))
    num.append(abstract)
    return num


def _link_headings_to_numbering(document: Any, num_id: int, levels: int) -> None:
    """把 ``HeadingN`` 样式绑到该编号的对应层级。"""
    for level in range(1, min(levels, 9) + 1):
        style = _style_by_id(document, f"Heading{level}")
        ppr = style.element.get_or_add_pPr()
        num_pr = ppr.find(qn("w:numPr"))
        if num_pr is None:
            num_pr = OxmlElement("w:numPr")
            ppr.insert(0, num_pr)
        for tag, value in (("w:ilvl", str(level - 1)), ("w:numId", str(num_id))):
            element = num_pr.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                num_pr.append(element)
            element.set(qn("w:val"), value)
        set_style_outline_level(style, level - 1)


def _style_by_id(document: Any, style_id: str) -> Any:
    styles = document.styles
    for style in styles:
        if style.style_id == style_id:
            return styles[style.name]
    raise KeyError(f"母版缺少样式: {style_id}")


def ensure_update_fields(document: Any) -> None:
    """``settings.xml`` 补 ``updateFields``（幂等）。"""
    settings = document.settings.element
    if settings.find(f"{_W}updateFields") is None:
        settings.append(make_update_fields())


def template_bytes(config: Config | None = None) -> bytes:
    """把母版渲染成字节（测试与 CI 重建用）。"""
    document = build_template(config)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
