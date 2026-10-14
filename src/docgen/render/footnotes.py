"""脚注（完整版手册 W4）：手写 ``word/footnotes.xml``。

python-docx 不支持脚注，所以这里直接改包：

1. 渲染时收集脚注文本，在正文里写 ``w:footnoteReference`` 引用 run；
2. 存盘后往 docx 里补 ``word/footnotes.xml``、内容类型与关系项；
3. 部件里带 Word 要求的分隔符条目（``separator`` 与 ``continuationSeparator``）。

正文里的引用 run 用 ``FootnoteReference`` 字符样式，条目用 ``FootnoteText``。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

__all__ = ["build_footnotes_xml", "inject_footnotes", "save_with_footnotes"]

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XML = "http://www.w3.org/XML/1998/namespace"

NSMAP = {"w": _W, "r": _R, "w14": _W14}

_FOOTNOTES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
)
_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"


def build_footnotes_xml(footnotes: list[str], *, style: dict[str, Any] | None = None) -> bytes:
    """生成 ``word/footnotes.xml``：分隔符条目 + 每条脚注（id 从 1 开始）。

    ``style`` 是可选样式属性（``[styles.footnote]``），目前用于行距。
    """
    root = etree.Element(f"{{{_W}}}footnotes", nsmap=NSMAP)
    for footnote_id, kind in ((-1, "separator"), (0, "continuationSeparator")):
        root.append(_separator_entry(footnote_id, kind))
    for index, text in enumerate(footnotes, start=1):
        root.append(_footnote_entry(index, text, style))
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))


def _separator_entry(footnote_id: int, kind: str) -> etree._Element:
    """分隔符条目：Word 要求脚注部件里有这两条（id -1 / 0）。

    元素名就是 ``w:separator`` / ``w:continuationSeparator``（**不是**
    ``w:br w:type="separator"``——那不在 ``ST_BrType`` 的取值集合里，
    会被 schema 判非法，实测抓到过）。
    """
    footnote = etree.Element(f"{{{_W}}}footnote")
    footnote.set(f"{{{_W}}}id", str(footnote_id))
    footnote.set(f"{{{_W}}}type", kind)
    paragraph = etree.SubElement(footnote, f"{{{_W}}}p")
    run = etree.SubElement(paragraph, f"{{{_W}}}r")
    etree.SubElement(run, f"{{{_W}}}{kind}")
    return footnote


def _footnote_entry(footnote_id: int, text: str, style: dict[str, Any] | None = None) -> Any:
    """一条脚注：``w:footnoteRef``（编号占位）+ 正文文本。

    两个坑（都是实测踩到的）：

    1. **必须有 ``w:footnoteRef``**，那是 Word 自动编号的占位元素。
       只写 ``w:footnoteReference``（正文里的引用）而没有条目内的 ``w:footnoteRef``，
       页脚处就**不会自动编号**。
    2. ``vertAlign=superscript`` 只加在**编号 run** 上；以前把它加在整条文本上，
       导致脚注正文整体变成上标（用户实测报的正是这个）。
    """
    footnote = etree.Element(f"{{{_W}}}footnote")
    footnote.set(f"{{{_W}}}id", str(footnote_id))
    paragraph = etree.SubElement(footnote, f"{{{_W}}}p")

    ppr = etree.SubElement(paragraph, f"{{{_W}}}pPr")
    p_style = etree.SubElement(ppr, f"{{{_W}}}pStyle")
    p_style.set(f"{{{_W}}}val", "FootnoteText")
    spacing = _footnote_spacing(style)
    if spacing is not None:
        spacing_element = etree.SubElement(ppr, f"{{{_W}}}spacing")
        spacing_element.set(f"{{{_W}}}line", str(spacing))
        spacing_element.set(f"{{{_W}}}lineRule", "auto")

    # 编号 run：w:footnoteRef 由 Word 替换成自动编号，并作为上标显示
    reference_run = etree.SubElement(paragraph, f"{{{_W}}}r")
    reference_rpr = etree.SubElement(reference_run, f"{{{_W}}}rPr")
    reference_style = etree.SubElement(reference_rpr, f"{{{_W}}}rStyle")
    reference_style.set(f"{{{_W}}}val", "FootnoteReference")
    reference_align = etree.SubElement(reference_rpr, f"{{{_W}}}vertAlign")
    reference_align.set(f"{{{_W}}}val", "superscript")
    etree.SubElement(reference_run, f"{{{_W}}}footnoteRef")

    # 文本 run：不加 vertAlign
    text_run = etree.SubElement(paragraph, f"{{{_W}}}r")
    text_element = etree.SubElement(text_run, f"{{{_W}}}t")
    text_element.set(f"{{{_XML}}}space", "preserve")
    text_element.text = f" {text}"
    return footnote


def _footnote_spacing(style: dict[str, Any] | None) -> int | None:
    """FootnoteText 的行距（twentieths of a point）；默认单倍行距。

    不设行距时 Word 会跟随正文的行距设置，脚注区看起来就会「行间距偏大」。
    """
    settings = style if isinstance(style, dict) else {}
    spacing = settings.get("line_spacing")
    if spacing is None:
        return 240  # 单倍行距
    try:
        return max(1, round(float(spacing) * 240))
    except (TypeError, ValueError):
        return 240


def save_with_footnotes(document: object, output: Path, footnotes: list[str]) -> Path:
    """存盘：先保存 python-docx 文档，再把脚注部件注入 zip。"""
    buffer = io.BytesIO()
    document.save(buffer)  # type: ignore[attr-defined]
    data = inject_footnotes(buffer.getvalue(), footnotes) if footnotes else buffer.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def inject_footnotes(
    data: bytes, footnotes: list[str], *, style: dict[str, Any] | None = None
) -> bytes:
    """往 docx 字节里注入 ``word/footnotes.xml``、内容类型与关系项（幂等）。"""
    if not footnotes:
        return data
    source = zipfile.ZipFile(io.BytesIO(data))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "[Content_Types].xml":
                payload = _with_content_type(payload)
            elif item.filename == "word/_rels/document.xml.rels":
                payload = _with_relationship(payload)
            target.writestr(item, payload)
        target.writestr("word/footnotes.xml", build_footnotes_xml(footnotes, style=style))
    source.close()
    return output.getvalue()


def _with_content_type(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    if any(
        override.get("PartName") == "/word/footnotes.xml"
        for override in root.findall(
            "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
        )
    ):
        return payload
    override = etree.SubElement(
        root, "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
    )
    override.set("PartName", "/word/footnotes.xml")
    override.set("ContentType", _FOOTNOTES_CONTENT_TYPE)
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))


def _with_relationship(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    if any(
        relation.get("Type") == _RELATIONSHIP_TYPE
        for relation in root.findall(f"{{{ns}}}Relationship")
    ):
        return payload
    existing = [relation.get("Id", "") for relation in root.findall(f"{{{ns}}}Relationship")]
    next_id = 1
    while f"rId{next_id}" in existing:
        next_id += 1
    relation = etree.SubElement(root, f"{{{ns}}}Relationship")
    relation.set("Id", f"rId{next_id}")
    relation.set("Type", _RELATIONSHIP_TYPE)
    relation.set("Target", "footnotes.xml")
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
