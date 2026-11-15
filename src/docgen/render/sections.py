"""分节 / 页码 / 页眉页脚 / 封面。

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

from ..errors import E_SECTION_CONFIG, DocGenError
from ..units import to_points

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

#: 页眉底部线可用的 OOXML 边框线型（``double`` 映射到粗上细下）
_BORDER_STYLES = {
    "single",
    "double",
    "thickThinSmallGap",
    "thinThickSmallGap",
    "dotted",
    "dashed",
    "none",
}


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
        if any(_has_even_page(spec) for spec in specs):
            from .ooxml import set_even_and_odd_headers

            set_even_and_odd_headers(document)
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


def _has_even_page(spec: dict[str, Any]) -> bool:
    """该节是否配置了偶数页页眉/页脚（需要文档级 evenAndOddHeaders）。"""
    for key in ("header", "footer"):
        config = _header_config(spec, key)
        if config.get("even") is not None:
            return True
    return False


def _apply_header_footer(section: Any, spec: dict[str, Any]) -> None:
    """页眉页脚：每节独立；支持奇偶页/首页不同、字体、粗细双线、距边界。"""
    header = _header_config(spec, "header")
    footer = _header_config(spec, "footer")

    _write_header_footer(section, "header", header)
    _write_header_footer(section, "footer", footer)

    if "distance" in header:
        section.header_distance = Cm(_number(header["distance"], "header.distance"))
    if "distance" in footer:
        section.footer_distance = Cm(_number(footer["distance"], "footer.distance"))
    if header.get("first") or footer.get("first"):
        section.different_first_page_header_footer = True


def _header_config(spec: dict[str, Any], key: str) -> dict[str, Any]:
    """把 ``header`` / ``header.*`` 的两种写法（嵌套表 / 点号键）统一成嵌套表。"""
    raw = spec.get(key)
    config: dict[str, Any] = {}
    if isinstance(raw, dict):
        config.update(raw)
    prefix = f"{key}."
    for name, value in spec.items():
        if isinstance(name, str) and name.startswith(prefix):
            _set_dotted(config, name[len(prefix) :], value)
    return config


def _set_dotted(target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cursor = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def _write_header_footer(section: Any, kind: str, config: dict[str, Any]) -> None:
    """写 ``header`` 或 ``footer``：base(odd) / even / first 三种页。"""
    odd_variant = _variant(config.get("odd")) or {}
    variants: list[tuple[str, dict[str, Any] | None]] = [
        ("odd", {**config, **odd_variant}),
        ("even", _variant(config.get("even"))),
        ("first", _variant(config.get("first"))),
    ]
    for variant, variant_config in variants:
        if variant == "even" and variant_config is None:
            continue
        if variant == "first" and variant_config is None:
            continue
        payload = config if variant_config is None else {**config, **variant_config}
        if not payload:
            continue
        target = _part_for(section, kind, variant)
        if target is None:
            continue
        target.is_linked_to_previous = False
        paragraph = target.paragraphs[0]
        _write_paragraph(
            paragraph,
            payload,
            with_page_field=("PAGE" in str(payload.get("text", ""))),
        )


def _variant(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"text": value}
    return None


def _part_for(section: Any, kind: str, variant: str) -> Any:
    """``header``/``footer`` × ``odd``/``even``/``first`` → python-docx part。"""
    if variant == "odd":
        return section.header if kind == "header" else section.footer
    if variant == "even":
        return section.even_page_header if kind == "header" else section.even_page_footer
    return section.first_page_header if kind == "header" else section.first_page_footer


def _write_paragraph(paragraph: Any, config: dict[str, Any], *, with_page_field: bool) -> None:
    """写页眉页脚段落：文字 + ``PAGE`` 域 + 对齐 + 字体 + 底部边框线。"""
    from .ooxml import (
        append_field,
        append_text,
        set_paragraph_alignment,
    )

    text = str(config.get("text", "") or "")
    align = str(config.get("alignment", "center") or "center")
    if align not in ("left", "center", "right"):
        raise DocGenError(
            E_SECTION_CONFIG,
            f"页眉/页脚 alignment 不支持: {align!r}（可用 left / center / right）",
        )
    paragraph.text = ""
    set_paragraph_alignment(paragraph, align)
    if text:
        if with_page_field and "PAGE" in text:
            before, _, after = text.partition("PAGE")
            if before:
                append_text(paragraph, before)
            append_field(paragraph, "PAGE", "1")
            if after:
                append_text(paragraph, after)
        else:
            append_text(paragraph, text)

    _apply_border(paragraph, config)
    _apply_font(paragraph, config)


def _apply_border(paragraph: Any, config: dict[str, Any]) -> None:
    from .ooxml import set_paragraph_border

    line = config.get("line")
    style = ""
    size: Any = None
    color: Any = None
    if isinstance(line, str):
        style = line
    elif isinstance(line, dict):
        style = str(line.get("style", "double") or "double")
        size = line.get("size")
        color = line.get("color")
    elif line is not None and line is not False:
        raise DocGenError(E_SECTION_CONFIG, f"页眉/页脚 line 写法不支持: {line!r}")
    if not style:
        return
    if style.lower() in ("none", "false"):
        return
    # 中文规范「粗、细双线（粗线在上）」= thickThinSmallGap；double 作为别名
    if style.lower() == "double":
        style = "thickThinSmallGap"
    if style not in _BORDER_STYLES:
        raise DocGenError(
            E_SECTION_CONFIG,
            f"页眉/页脚 line 线型不支持: {style!r}（可用 {' / '.join(sorted(_BORDER_STYLES))}）",
        )
    size_value = size if size is not None else config.get("line_size", "1pt")
    color_value = str(color if color is not None else config.get("line_color", "000000"))
    points = float(to_points(size_value).pt)
    set_paragraph_border(
        paragraph,
        "bottom",
        style=style,
        size=str(max(2, round(points * 8))),
        color=color_value,
    )


def _apply_font(paragraph: Any, config: dict[str, Any]) -> None:
    from .ooxml import apply_font

    font = config.get("font")
    font = font if isinstance(font, dict) else {}
    name = font.get("name", config.get("font.name"))
    latin = font.get("latin", config.get("font.latin"))
    size = font.get("size", config.get("font.size"))
    color = font.get("color", config.get("font.color"))
    bold = font.get("bold", config.get("font.bold"))
    italic = font.get("italic", config.get("font.italic"))
    for run in paragraph.runs:
        apply_font(
            run,
            str(latin or name) if (latin or name) else None,
            east_asia=str(name) if name else None,
            size=to_points(size) if size is not None else None,
            bold=bool(bold) if bold is not None else None,
            italic=bool(italic) if italic is not None else None,
            color=str(color) if color else None,
        )


def _number(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise DocGenError(E_SECTION_CONFIG, f"{label} 需要数字（厘米）：{value!r}") from None
