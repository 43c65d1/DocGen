"""用**官方 OOXML schema** 校验产物（学习借鉴自 python-docx 的 vendored ``ref/xsd``）。

「XML 合法 + 元素都在」并不够：ECMA-376 的属性容器是 ``xsd:sequence``，
**顺序错了 Word 会静默忽略**。手写校验器（``ooxml_check``）只覆盖了少数几条规则，
这里用官方 ``wml.xsd`` 做全量校验，一次抓住过：

- ``w:pgNumType`` / ``w:vAlign`` 在 ``w:sectPr`` 里位置错
- ``w:tblLayout`` / ``w:tblBorders`` 在 ``w:tblPr`` 里位置错
- ``w:left`` 在 ``w:tblBorders`` 里排在 ``w:bottom`` 之后
- 根元素上未声明的 ``mc:Ignorable``
- ``w:firstLineChars`` 被误当成独立元素（它是 ``w:ind`` 的属性）
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from docgen.config import load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.math import find_xsl
from docgen.render.ooxml_check import SCHEMA_DIR, validate_parts, validate_with_schema

#: 无 ``MML2OMML.XSL`` 时公式按设计降级为纯文本，产物里不会有 ``m:`` 命名空间
#: （见 `render/math.py`）。依赖 OMML 的断言要在这种环境跳过。
HAS_XSL = find_xsl() is not None
requires_xsl = pytest.mark.skipif(
    not HAS_XSL, reason="本机没有 MML2OMML.XSL（Office），公式按设计降级为纯文本"
)

FIXTURES = Path(__file__).parent.parent / "examples" / "minimal"


def _document_xml(markdown: str, fixture: Path = FIXTURES) -> bytes:
    config = load_config(fixture / "config.toml")
    data = render_docx_bytes(parse_dfm(markdown), config, base_dir=fixture)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("word/document.xml")


def _assert_schema_clean(xml: bytes) -> None:
    problems = validate_with_schema(xml)
    assert problems == [], "schema 校验失败:\n" + "\n".join(problems[:5])


def test_schema_bundle_is_present() -> None:
    assert (SCHEMA_DIR / "wml.xsd").is_file()
    assert (SCHEMA_DIR / "shared-math.xsd").is_file()
    assert (SCHEMA_DIR / "xml.xsd").is_file()


def test_schema_rejects_wrong_ordering() -> None:
    """schema 必须真的会报错——否则「校验通过」没有意义。"""
    ns = (
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
    )
    # w:cols 在 w:pgNumType 之前 → 违反 CT_SectPr 的 sequence
    bad = (
        f"<w:document {ns}><w:body><w:p><w:pPr><w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1" w:right="1" w:bottom="1" w:left="1" w:header="1" w:footer="1"/>'
        '<w:cols/><w:pgNumType w:fmt="decimal"/>'
        "</w:sectPr></w:pPr></w:p></w:body></w:document>"
    )
    assert validate_with_schema(bad)


def test_minimal_document_is_schema_valid() -> None:
    _assert_schema_clean(_document_xml("正文段落\n\n# 标题\n"))


def test_example_document_is_schema_valid() -> None:
    """真实示例（覆盖 W0~W5 全部特性）必须完全符合 schema。"""
    markdown = (FIXTURES / "content.md").read_text(encoding="utf-8")
    _assert_schema_clean(_document_xml(markdown))


@pytest.mark.parametrize(
    "markdown",
    [
        "| a | b | c |\n| :-- | :-: | --: |\n| 1 | 2 | 3 |\n",
        "正文[[fn:脚注文本]]。\n",
        "\\begin{equation #eq:1 number=1}\n$$E=mc^2$$\n\\end{equation}\n",
        "[[toc]]\n\n# 标题\n",
        "[[img:pics/photo.png width=3cm align=center]]\n",
        "\\begin{caption #fig:1}\n图题\n\\end{caption}\n\n见图 [[ref:fig:1]]。\n",
        "- 无序\n  1. 嵌套\n\n> 引用\n\n```python\nprint(1)\n```\n",
        "$$\n\\int_0^1 x\\,dx\n$$\n\n[[pagebreak]]\n",
    ],
)
def test_feature_documents_are_schema_valid(markdown: str) -> None:
    _assert_schema_clean(_document_xml(markdown))


def test_two_section_document_is_schema_valid() -> None:
    """分节 + 页码 + 页眉页脚 + 封面（W5）走同一套 schema。"""
    _assert_schema_clean(_document_xml("# 封面\n\n封面正文\n\n# 正文\n\n内容\n"))


def test_root_has_no_stray_namespaces() -> None:
    """根元素不应留未使用的命名空间声明，也不该有 ``mc:Ignorable``。"""
    xml = _document_xml("正文\n").decode("utf-8")
    for prefix in ("xmlns:v=", "xmlns:o=", "xmlns:w10=", "xmlns:wps=", "mc:Ignorable"):
        assert prefix not in xml, f"根元素残留 {prefix}"


@requires_xsl
def test_root_keeps_namespaces_that_are_used() -> None:
    """用到的前缀必须保留（否则内容会带一堆局部声明或直接损坏）。

    这条依赖公式产出 OMML（才需要 ``xmlns:m``），所以无 XSL 时跳过；
    ``xmlns:m`` 的保留逻辑由 ``test_root_has_no_stray_namespaces`` 的反向断言兜住。
    """
    xml = _document_xml("正文 $x^2$\n\n[[img:pics/photo.png]]\n").decode("utf-8")
    for prefix in ("xmlns:w=", "xmlns:m=", "xmlns:wp=", "xmlns:a=", "xmlns:pic="):
        assert prefix in xml, f"缺少 {prefix}"


def test_fields_are_marked_dirty() -> None:
    """域起始标记带 ``w:dirty="true"``，Word 打开时强制重算（做法参考 pandoc）。"""
    xml = _document_xml(
        "\\begin{caption #fig:1}\n图题\n\\end{caption}\n\n见图 [[ref:fig:1]]。\n\n[[toc]]\n"
    ).decode("utf-8")
    assert 'w:fldCharType="begin" w:dirty="true"' in xml
    assert 'w:dirty="true"' in xml


def test_structural_check_also_passes() -> None:
    """两层校验都要过：手写结构检查 + 官方 schema。"""
    config = load_config(FIXTURES / "config.toml")
    markdown = (FIXTURES / "content.md").read_text(encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), config, base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    assert validate_parts(parts) == []
    _assert_schema_clean(parts["word/document.xml"])
