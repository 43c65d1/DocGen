"""OOXML 结构校验（防「Word 打不开」这类缺陷）。

只做「XML 合法但结构非法」的检查——那是普通 XML 解析器发现不了、而 Word 会直接拒收的一类问题：

- ``w:p`` 的直接子元素必须是段落级元素（``w:r`` / ``w:hyperlink`` / ``w:bookmarkStart`` …）。
  **``w:fldChar`` / ``w:instrText`` / ``w:t`` 必须包在 ``w:r`` 里**——直接挂在段落上
  会让 Word 报「无法打开文件」，这是实测踩到的坑。
- ``w:tbl`` 的直接子元素必须是表格级元素（``w:tr`` 等）。
- ``w:tr`` 的直接子元素必须是 ``w:tc``（或 ``w:tblPrEx`` / ``w:trPr``）。
- ``w:pPr`` / ``w:rPr`` 必须排在其它子元素之前。
- 空的 ``<w:r/>`` 是浪费（内容为空），也一并报出来。

用法：``assert_valid_document(document_xml, styles_xml=...)`` 或 CLI 式
``validate_ooxml(parts) -> list[str]``。
"""

from __future__ import annotations

import functools
from pathlib import Path

from lxml import etree

__all__ = [
    "SCHEMA_DIR",
    "validate_document_xml",
    "validate_parts",
    "validate_with_schema",
    "wml_schema",
]

#: 随仓库提供的 ECMA-376 schema（见 ``tests/schemas/README.md``）
SCHEMA_DIR = Path(__file__).resolve().parents[3] / "tests" / "schemas" / "ecma-376"

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: ``w:p`` 允许的直接子元素
PARAGRAPH_CHILDREN = frozenset(
    {
        "pPr",
        "r",
        "hyperlink",
        "bookmarkStart",
        "bookmarkEnd",
        "commentRangeStart",
        "commentRangeEnd",
        "moveFromRangeStart",
        "moveFromRangeEnd",
        "moveToRangeStart",
        "moveToRangeEnd",
        "customXmlInsRangeStart",
        "customXmlInsRangeEnd",
        "customXmlDelRangeStart",
        "customXmlDelRangeEnd",
        "customXmlMoveFromRangeStart",
        "customXmlMoveFromRangeEnd",
        "customXmlMoveToRangeStart",
        "customXmlMoveToRangeEnd",
        "ins",
        "del",
        "moveFrom",
        "moveTo",
        "oMath",
        "oMathPara",
        "subDoc",
        "sdt",
        "proofErr",
        "permStart",
        "permEnd",
        "fldSimple",
    }
)

#: ``w:tbl`` 允许的直接子元素
TABLE_CHILDREN = frozenset(
    {"tblPr", "tblGrid", "tr", "sdt", "bookmarkStart", "bookmarkEnd", "customXml"}
)

#: ``w:tr`` 允许的直接子元素
ROW_CHILDREN = frozenset({"tblPrEx", "trPr", "tc", "sdt", "bookmarkStart", "bookmarkEnd"})

#: 只能出现在 ``w:r`` 里的元素（直接挂段落 = Word 拒收）
RUN_ONLY = frozenset({"fldChar", "instrText", "t", "br", "tab", "drawing", "pict", "rPr"})


def validate_parts(parts: dict[str, bytes]) -> list[str]:
    """校验 docx 各部件，返回问题列表（空列表表示通过）。"""
    problems: list[str] = []
    document = parts.get("word/document.xml")
    if document is not None:
        problems.extend(validate_document_xml(document))
    for name in ("word/styles.xml", "word/numbering.xml", "word/settings.xml"):
        data = parts.get(name)
        if data is None:
            continue
        try:
            etree.fromstring(data)
        except etree.XMLSyntaxError as exc:
            problems.append(f"{name}: XML 不合法: {exc}")
    return problems


def validate_document_xml(document_xml: bytes | str) -> list[str]:
    """检查 ``document.xml`` 的结构合法性。"""
    data = document_xml.encode("utf-8") if isinstance(document_xml, str) else document_xml
    root = etree.fromstring(data)
    problems: list[str] = []

    for index, element in enumerate(root.iter(f"{_W}p")):
        problems.extend(_check_children(element, PARAGRAPH_CHILDREN, f"w:p[{index}]", RUN_ONLY))
    for index, element in enumerate(root.iter(f"{_W}tbl")):
        problems.extend(_check_children(element, TABLE_CHILDREN, f"w:tbl[{index}]"))
    for index, element in enumerate(root.iter(f"{_W}tr")):
        problems.extend(_check_children(element, ROW_CHILDREN, f"w:tr[{index}]"))
    for element in root.iter(f"{_W}pPr", f"{_W}rPr"):
        problems.extend(_check_properties_order(element))
    for index, element in enumerate(root.iter(f"{_W}r")):
        if len(element) == 0:
            problems.append(f"w:r[{index}]: 空 run（没有内容）")
    return problems


def _check_children(
    element: etree._Element,
    allowed: frozenset[str],
    where: str,
    run_only: frozenset[str] | None = None,
) -> list[str]:
    problems: list[str] = []
    for child in element:
        tag = _local(child)
        if tag in allowed:
            continue
        if run_only is not None and tag in run_only:
            problems.append(f"{where}: <w:{tag}> 必须包在 <w:r> 里（直接挂段落会被 Word 拒收）")
        else:
            problems.append(f"{where}: 不允许的子元素 <w:{tag}>")
    return problems


def _check_properties_order(element: etree._Element) -> list[str]:
    """``w:pPr`` / ``w:rPr`` 必须是同级里的第一个元素。"""
    parent = element.getparent()
    if parent is None:
        return []
    if parent.index(element) != 0:
        return [f"<w:{_local(element)}> 必须是父元素 <w:{_local(parent)}> 的第一个子元素"]
    return []


def _local(element: etree._Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return "?"
    return tag.split("}")[-1] if "}" in tag else tag


@functools.lru_cache(maxsize=1)
def wml_schema() -> etree.XMLSchema:
    """官方 **WML** schema（``wml.xsd``，含 drawingml / math 依赖）。

    编译约 0.1s，缓存复用；校验一份真实文档约几十毫秒。
    """
    return etree.XMLSchema(etree.parse(str(SCHEMA_DIR / "wml.xsd")))


def validate_with_schema(xml: bytes | str) -> list[str]:
    """用官方 WML schema 校验 ``document.xml``，返回问题列表（空 = 合法）。

    比 :func:`validate_document_xml` 强得多：schema 是 ``xsd:sequence``，
    **子元素顺序**、属性拼写、必需属性缺漏都会被指出来——
    这些正是 Word 会静默忽略、肉眼看不出的问题
    （实测抓到过 ``w:pgNumType``/``w:vAlign``/``w:tblLayout``/``w:left`` 顺序错）。
    """
    data = xml.encode("utf-8") if isinstance(xml, str) else xml
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        return [f"XML 不合法: {exc}"]

    schema = wml_schema()
    if schema.validate(root):
        return []

    problems: list[str] = []
    for error in schema.error_log:
        message = str(error)
        message = message.replace(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}", "w:"
        )
        message = message.replace(
            "{http://schemas.openxmlformats.org/markup-compatibility/2006}", "mc:"
        )
        problems.append(message)
    return problems
