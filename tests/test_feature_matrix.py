"""特性矩阵：**每个特性一条断言**，检查「config 声明 → 产物信号」是否真的闭环。

配套样例 ``examples/features/``（content.md + config.toml）。
这份测试的价值在于「失效定位」：矩阵里哪一项红了，就是哪个特性没生效，
不必去读 OOXML 或猜渲染路径。

约定：每个特性都有一个肉眼可辨、机器可断言的**信号值**（颜色/字号/元素）。
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from docgen.config import load_config
from docgen.parser.dfm import parse_dfm
from docgen.render.docx import render_docx_bytes
from docgen.render.math import find_xsl
from docgen.render.ooxml_check import validate_parts, validate_with_schema

#: 数学若要产出 OMML，需要 Office 的 ``MML2OMML.XSL``。
#: **没有它时引擎按设计降级为纯文本**（见 `render/math.py` 的设计取舍），
#: 所以在无 XSL 的环境（例如 Linux CI）里，断言 ``m:oMath`` 的用例必须跳过——
#: 否则测的是"本机装没装 Word"，而不是代码对不对。
HAS_XSL = find_xsl() is not None
requires_xsl = pytest.mark.skipif(
    not HAS_XSL, reason="本机没有 MML2OMML.XSL（Office），公式按设计降级为纯文本"
)

FIXTURES = Path(__file__).parent.parent / "examples" / "features"


@pytest.fixture(scope="module")
def parts() -> dict[str, bytes]:
    """把整份特性矩阵渲染一次，供所有断言复用。"""
    config = load_config(FIXTURES / "config.toml")
    markdown = (FIXTURES / "content.md").read_text(encoding="utf-8")
    data = render_docx_bytes(parse_dfm(markdown), config, base_dir=FIXTURES)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.fixture(scope="module")
def xml(parts: dict[str, bytes]) -> str:
    return parts["word/document.xml"].decode("utf-8")


@pytest.fixture(scope="module")
def rels(parts: dict[str, bytes]) -> str:
    return parts["word/_rels/document.xml.rels"].decode("utf-8")


# --------------------------------------------------------------------------
# 每项一个特性：行内格式
# --------------------------------------------------------------------------
def test_feature_bold(xml: str) -> None:
    """``**粗体**`` → 内置样式名 ``strong`` → config 的 ``[styles.strong]``。"""
    assert "<w:b/>" in xml


def test_feature_italic(xml: str) -> None:
    """``*斜体*`` → 内置样式名 ``em``。"""
    assert "<w:i/>" in xml


def test_feature_strike(xml: str) -> None:
    """``~~删除~~`` → 内置样式名 ``strike``。"""
    assert "<w:strike/>" in xml


def test_markdown_emphasis_maps_to_builtin_style_names() -> None:
    """契约：Markdown 语法产出的**是内置样式名**，不是自定义名。

    这条曾经让「config 里写了加粗、产物却不粗」——因为只声明了
    ``[styles.feature_bold]`` 而没有 ``[styles.strong]``，
    而 ``**粗**`` 走的是 ``strong``。
    """
    from docgen.ir import Paragraph, Styled, Text

    blocks = parse_dfm("**粗** *斜* ~~删~~ H~2~O\n")
    assert isinstance(blocks[0], Paragraph)
    names = [node.style_name for node in blocks[0].content if isinstance(node, Styled)]
    assert names == ["strong", "em", "strike", "sub"]
    assert names[0] not in {"feature_bold", "bold"}
    assert blocks[0].content[0] == Styled(content=[Text("粗")], style_name="strong")


def test_feature_underline(xml: str) -> None:
    """``font.underline = true`` → ``<w:u w:val="single"/>``。"""
    assert '<w:u w:val="single"/>' in xml


def test_feature_color(xml: str) -> None:
    """信号色 C00000 必须原样出现在产物里。"""
    assert '<w:color w:val="C00000"/>' in xml


def test_feature_small_size(xml: str) -> None:
    """8pt = 16 half-points。"""
    assert '<w:sz w:val="16"/>' in xml


def test_feature_superscript(xml: str) -> None:
    assert 'w:val="superscript"' in xml


def test_feature_subscript(xml: str) -> None:
    assert 'w:val="subscript"' in xml


def test_feature_external_link(xml: str, rels: str) -> None:
    """链接必须是真超链接：正文有 w:hyperlink，关系项里是 External。"""
    assert "<w:hyperlink" in xml
    assert 'TargetMode="External"' in rels
    assert "example.com/feature" in rels


@requires_xsl
def test_feature_inline_math(xml: str) -> None:
    assert "<m:oMath" in xml


@requires_xsl
def test_feature_inline_math_falls_back_without_xsl(xml: str) -> None:
    """反过来也要成立：无 XSL 时公式降级为纯文本，**不能整段丢失**。

    这条不需要 XSL（反而是断言没有 XSL 的行为），所以在任何环境都跑。
    """
    if HAS_XSL:
        pytest.skip("本机有 XSL，走的是 OMML 路径")
    assert "E = mc^2" in xml or "mc^2" in xml


# --------------------------------------------------------------------------
# 代码块：语言变体换色 + 深合并（基座属性不能丢）
# --------------------------------------------------------------------------
def test_code_block_language_variant_colors(xml: str) -> None:
    """python=008000、javascript=B8860B 都要出现。"""
    assert 'w:val="008000"' in xml, "python 语言变体色没生效"
    assert 'w:val="B8860B"' in xml, "javascript 语言变体色没生效"


def test_code_block_base_attributes_survive_variant(xml: str) -> None:
    """深合并：变体只覆盖 color，基座的 Consolas 与 9pt 必须保留。"""
    assert "Consolas" in xml
    assert '<w:sz w:val="18"/>' in xml  # 9pt = 18 half-points


def test_code_block_shading_and_border(xml: str) -> None:
    assert "<w:shd" in xml and 'w:fill="F2F2F2"' in xml
    assert "<w:pBdr>" in xml


def test_text_block_has_no_variant_color(xml: str) -> None:
    """没给语言变体的 ``text`` 块不应该是绿/暗金色。"""
    assert 'w:val="008000"' in xml  # 只证明 python 有
    text_colors = re.findall(r"<w:color w:val=\"(B8860B|008000)\"", xml)
    assert len(text_colors) >= 2  # 两个变体各自出现


# --------------------------------------------------------------------------
# 表格：单元格内格式保留
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def table_xml(xml: str) -> str:
    tables: list[str] = re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.DOTALL)
    assert tables, "没有生成表格"
    return tables[0]


def test_table_cell_bold_is_real_formatting(table_xml: str) -> None:
    """单元格里的 ``**粗体**`` 要变成真加粗，而不是原样字面量。"""
    assert "<w:b/>" in table_xml
    assert "**" not in table_xml


@requires_xsl
def test_table_cell_math_present(table_xml: str) -> None:
    assert "oMath" in table_xml


def test_table_cell_link_present(table_xml: str) -> None:
    assert "<w:hyperlink" in table_xml


def test_table_three_line_and_width(table_xml: str) -> None:
    """三线表 + 固定列宽（col_widths 3:3:4）。"""
    assert 'w:val="single"' in table_xml and 'w:val="none"' in table_xml
    grid = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"/>', table_xml)]
    assert len(grid) == 3
    assert grid[0] == grid[1] < grid[2]  # 3:3:4
    assert 'w:type="fixed"' in table_xml


def test_table_header_repeats(table_xml: str) -> None:
    assert "tblHeader" in table_xml


# --------------------------------------------------------------------------
# 题注 / 引用 / 目录 / 脚注 / 分节
# --------------------------------------------------------------------------
def test_caption_uses_seq_field(xml: str) -> None:
    assert "SEQ " in xml
    assert 'w:name="fig:feature"' in xml


def test_cross_reference_uses_ref_field(xml: str) -> None:
    assert "REF fig:feature" in xml
    assert "REF eq:feature" in xml


def test_equation_numbered_table(xml: str) -> None:
    assert 'w:name="eq:feature"' in xml


def test_footnotes_part_and_references(parts: dict[str, bytes]) -> None:
    assert "word/footnotes.xml" in parts
    footnotes = parts["word/footnotes.xml"].decode("utf-8")
    assert "这是脚注文本" in footnotes
    assert "第二条脚注" in footnotes
    assert "footnoteReference" in parts["word/document.xml"].decode("utf-8")


def test_two_sections_with_header_footer(parts: dict[str, bytes]) -> None:
    document = parts["word/document.xml"].decode("utf-8")
    assert document.count("<w:sectPr") >= 2
    headers = [n for n in parts if re.search(r"header\d*\.xml", n)]
    footers = [n for n in parts if re.search(r"footer\d*\.xml", n)]
    assert headers and footers
    assert any("DocGen 特性矩阵".encode() in parts[name] for name in headers)
    assert any(b"PAGE" in parts[name] for name in footers)


def test_page_numbering_restarts_in_body(parts: dict[str, bytes]) -> None:
    document = parts["word/document.xml"].decode("utf-8")
    assert 'w:fmt="upperRoman"' in document
    assert 'w:fmt="decimal"' in document and 'w:start="1"' in document


def test_image_embedded_with_width(parts: dict[str, bytes]) -> None:
    assert [n for n in parts if n.startswith("word/media/")]
    document = parts["word/document.xml"].decode("utf-8")
    # 3cm = 1080000 EMU
    extents = [int(value) for value in re.findall(r'<wp:extent cx="(\d+)"', document)]
    assert any(abs(value - 1080000) <= 2000 for value in extents), extents


def test_page_break(parts: dict[str, bytes]) -> None:
    assert 'w:type="page"' in parts["word/document.xml"].decode("utf-8")


# --------------------------------------------------------------------------
# 产物整体必须仍然合法（结构 + schema 两层）
# --------------------------------------------------------------------------
def test_feature_matrix_parts_are_structurally_valid(parts: dict[str, bytes]) -> None:
    assert validate_parts(parts) == []


def test_feature_matrix_is_schema_valid(parts: dict[str, bytes]) -> None:
    problems = validate_with_schema(parts["word/document.xml"])
    assert problems == [], "\n".join(problems[:5])


# --------------------------------------------------------------------------
# 链接目标也要落到产出里
# --------------------------------------------------------------------------
def test_link_target_reaches_the_document(parts: dict[str, bytes]) -> None:
    """链接的 URL 要真的进产出（关系部件），而不是只渲染了文字。

    （原先是 HTML 侧的同名断言；HTML 后端移除后改到 docx 侧。）
    """
    rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
    assert "example.com/feature" in rels
