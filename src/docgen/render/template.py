"""母版处理（完整版手册 §7 / §14）。

母版（Word 模板）只提供**结构与槽位**：样式 id、``outlineLvl``、多级编号骨架、
页眉页脚占位。**一切格式值由引擎从 config 无条件写入**（手册 §5 铁律 2），
所以母版里的值只是「默认值」，会被 config 覆盖。

配置口径（手册 §6.1）：点号键，如 ``font.name``、``font.size``、``font.bold``、
``line_spacing``；引擎按此读取，不再兼容下划线扁平键。

W0 阶段用 python-docx 自带的默认模板作为最小母版，先跑通链路；
真实 ``.dotx`` 解包入库（含 ``numbering.xml`` 多级编号、``TOC 1..9``）在后续阶段替换。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document as _Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..config import Config
from ..units import to_points
from .ooxml import set_style_outline_level

__all__ = [
    "MONO_EAST_ASIA",
    "MONO_FONT",
    "TEMPLATE_VERSION",
    "create_document",
    "ensure_font_table",
    "iter_styles",
]

#: 母版版本：随解包入库的模板一起提交，CI 可校验
TEMPLATE_VERSION = "0.1"

#: 必须存在的样式槽位（手册 §14.1）：母版缺任何一个都算不完整
REQUIRED_STYLES = (
    "Normal",
    "Heading1",
    "Heading2",
    "Heading3",
    "BodyText",
    "Caption",
    "TOC1",
    "TOC9",
)

#: 标题样式名 -> python-docx 样式键
HEADING_STYLE_NAMES = tuple(f"Heading{level}" for level in range(1, 10))


def create_document(config: Config, template: Path | None = None) -> Any:
    """创建 docx 文档：加载母版（或引擎默认母版）+ 补齐槽位 + 写入 ``[document]``。

    **构建路径与母版构建路径共用同一套槽位补齐**：否则用引擎默认母版构建出来的
    文档会缺少 ``TOC 1..9`` 样式与多级标题编号（题注样式同理），
    而这两样正是 W3/W5 依赖的。
    """
    if template is not None:
        document = _Document(str(template))
    else:
        document = _Document()
        _extend_default_template(document)
    apply_document_defaults(document, config)
    return document


def _extend_default_template(document: Any) -> None:
    """补齐 §14.1 槽位（幂等）：目录样式、题注样式、字体表、多级编号、updateFields。"""
    from .template_build import add_heading_numbering, add_toc_styles, ensure_update_fields

    add_toc_styles(document)
    _ensure_caption_styles(document)
    ensure_font_table(document)
    add_heading_numbering(document)
    ensure_update_fields(document)


def _ensure_caption_styles(document: Any) -> None:
    """题注/脚注样式必须存在（``SEQ`` 域与脚注引用都依赖它们）。"""
    for name in ("Caption", "FootnoteText", "FootnoteReference"):
        if any(style.name == name for style in document.styles):
            continue
        style = document.styles.add_style(name, 1)  # 1 = paragraph style
        style.base_style = document.styles["Normal"]
        style.quick_style = True
        style.hidden = False


#: 代码块等场景的等宽字体（与 docx.py 的 DEFAULT_MONO_FONT 一致）
MONO_FONT = "Consolas"
#: 代码块里中文的回退字体
MONO_EAST_ASIA = "等线"

#: 名称需要替代字体时给出的别名
FONT_ALIASES: dict[str, str] = {"Courier": "Courier New"}


def ensure_font_table(document: Any, extra_fonts: list[str] | None = None) -> list[str]:
    """把用到的字体登记进 ``word/fontTable.xml``，返回本次新增的字体名。

    Word 只认 fontTable / theme 里声明过的字体：缺登记会提示「缺少字体」并替换字形
    （DSH 预览侧的 "Missing fonts" 就是这里来的）。python-docx 没有 fontTable 的
    专用 API，所以直接改这个部件的 XML。
    """
    part = _font_table_part(document)
    if part is None:
        return []

    from lxml import etree

    root = etree.fromstring(part.blob)
    existing = {
        font.get(qn("w:name")) for font in root.findall(qn("w:font")) if font.get(qn("w:name"))
    }

    wanted = [MONO_FONT, MONO_EAST_ASIA, *FONT_ALIASES, *(extra_fonts or [])]
    added: list[str] = []
    for name in wanted:
        if not name or name in existing:
            continue
        root.append(_font_element(name, FONT_ALIASES.get(name)))
        existing.add(name)
        added.append(name)

    if added:
        part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return added


def _font_table_part(document: Any) -> Any:
    """在包部件里找 ``/word/fontTable.xml``。"""
    for part in document.part.package.parts:
        if str(part.partname).endswith("fontTable.xml"):
            return part
    return None


def _font_element(name: str, substitute: str | None = None) -> Any:
    """构造 ``<w:font w:name="X">``；中文额外写 ``w:charset="86"``（GB2312）。"""
    font = OxmlElement("w:font")
    font.set(qn("w:name"), name)
    if substitute:
        alternative = OxmlElement("w:altName")
        alternative.set(qn("w:val"), substitute)
        font.append(alternative)
    if _is_cjk(name):
        charset = OxmlElement("w:charset")
        charset.set(qn("w:val"), "86")
        font.append(charset)
    family = OxmlElement("w:family")
    family.set(qn("w:val"), "auto")
    font.append(family)
    pitch = OxmlElement("w:pitch")
    pitch.set(qn("w:val"), "variable")
    font.append(pitch)
    return font


def _is_cjk(name: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in name)


def apply_document_defaults(document: Any, config: Config) -> None:
    """把 ``[document]`` 的字体/字号/行距写进 Normal 样式（正文继承它）。"""
    settings = config.document
    font = settings.get("font")
    font = font if isinstance(font, dict) else {}
    normal = _style_by_id(document, "Normal")

    name = font.get("name", settings.get("font.name"))
    size = font.get("size", settings.get("font.size"))
    line_spacing = settings.get("line_spacing")
    if name:
        _set_style_fonts(normal, str(name))
    if size is not None:
        normal.font.size = to_points(size)
    if line_spacing is not None:
        normal.paragraph_format.line_spacing = float(line_spacing)

    for level in range(1, 10):
        style = _style_by_id(document, f"Heading{level}")
        set_style_outline_level(style, level - 1)


def _style_by_id(document: Any, style_id: str) -> Any:
    """按 ``style_id`` 取样式。

    python-docx 1.2 起「按 style_id 查找」已弃用，要按**样式名**查找；
    这里通过 ``style_id -> style.name`` 反查一次，既明确又避免弃用警告。
    """
    styles = document.styles
    for style in styles:
        if style.style_id == style_id:
            return styles[style.name]
    raise KeyError(f"母版缺少样式: {style_id}")


def _set_style_fonts(style: Any, name: str) -> None:
    """样式级字体：四个 ``rFonts`` 属性一起写（缺 eastAsia 中文会回退）。"""
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attribute), name)


def iter_styles(document: Any) -> list[tuple[str, str]]:
    """列出文档里的样式 ``(style_id, name)``，供母版校准与探针使用。"""
    return [(style.style_id, style.name) for style in document.styles]
