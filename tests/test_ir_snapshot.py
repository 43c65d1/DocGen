"""IR 快照：DFM -> IR 的结构契约（手册 §9：只断言关键结构）。

期望值全部是手写契约，不由实现推导。
"""

from pathlib import Path

from docgen.ir import (
    BlockNode,
    BlockQuote,
    Code,
    CodeBlock,
    Formula,
    Heading,
    ImageBlock,
    Link,
    ListBlock,
    ListItem,
    Math,
    PageBreak,
    Paragraph,
    Styled,
    Table,
    Text,
    ThematicBreak,
)
from docgen.parser.dfm import parse_dfm

FIXTURES = Path(__file__).parent / "fixtures"


def _minimal() -> str:
    return (FIXTURES / "minimal.md").read_text(encoding="utf-8")


def _full() -> str:
    return (FIXTURES / "full.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 最小快照（第 1 周）
# --------------------------------------------------------------------------
def test_minimal_ir() -> None:
    assert parse_dfm(_minimal()) == [
        Heading(level=1, content=[Text("Hello")], source_line=1),
        Paragraph(content=[Text("World")], source_line=3),
    ]


def test_empty_document_yields_no_blocks() -> None:
    assert parse_dfm("") == []
    assert parse_dfm("\n\n") == []


# --------------------------------------------------------------------------
# 行内节点（第 3 周）
# --------------------------------------------------------------------------
def test_inline_nodes() -> None:
    paragraph = _full_blocks()[1]
    assert isinstance(paragraph, Paragraph)

    content = paragraph.content
    styled = [node for node in content if isinstance(node, Styled)]
    assert [node.style_name for node in styled] == ["strong", "em", "strike"]
    assert [node.content for node in styled] == [[Text("粗体")], [Text("斜体")], [Text("删除")]]
    assert Code("inline code") in content
    assert Link(url="https://example.com", content=[Text("链接")]) in content


def test_inline_math_stays_inline() -> None:
    paragraph = _full_blocks()[9]
    assert isinstance(paragraph, Paragraph)
    assert paragraph.content == [
        Text("行内数学 "),
        Math(latex="x^2 + y^2 = z^2", display=False),
        Text(" 结束。"),
    ]


def test_styled_reference_marker() -> None:
    paragraph = _full_blocks()[11]
    assert isinstance(paragraph, Paragraph)
    assert paragraph.content == [
        Text("带样式 "),
        Styled(content=[Text("关键字")], style_name="keyword"),
        Text(" 与 "),
        Styled(content=[Text("样式引用")], style_name="caption"),
        Text("。"),
    ]


# --------------------------------------------------------------------------
# 块级节点（第 3 周）
# --------------------------------------------------------------------------
def test_headings_keep_level_and_line() -> None:
    blocks = _full_blocks()
    assert blocks[0] == Heading(level=1, content=[Text("标题一")], source_line=1)
    assert blocks[2] == Heading(level=2, content=[Text("标题二")], source_line=5)


def test_unordered_list_with_nested_list() -> None:
    assert _full_blocks()[3] == ListBlock(
        source_line=7,
        ordered=False,
        items=[
            ListItem(source_line=7, content=[Paragraph(content=[Text("无序项一")], source_line=7)]),
            ListItem(
                source_line=8,
                content=[
                    Paragraph(content=[Text("无序项二")], source_line=8),
                    ListBlock(
                        source_line=9,
                        ordered=False,
                        items=[
                            ListItem(
                                source_line=9,
                                content=[Paragraph(content=[Text("嵌套项")], source_line=9)],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )


def test_ordered_list() -> None:
    assert _full_blocks()[4] == ListBlock(
        source_line=11,
        ordered=True,
        items=[
            ListItem(
                source_line=11, content=[Paragraph(content=[Text("有序项一")], source_line=11)]
            ),
            ListItem(
                source_line=12, content=[Paragraph(content=[Text("有序项二")], source_line=12)]
            ),
        ],
    )


def test_block_quote_holds_blocks() -> None:
    assert _full_blocks()[5] == BlockQuote(
        source_line=14,
        content=[
            Paragraph(content=[Text("引用第一段")], source_line=14),
            Paragraph(content=[Text("引用第二段")], source_line=16),
        ],
    )


def test_fenced_code_block_with_language() -> None:
    assert _full_blocks()[6] == CodeBlock(
        source_line=18, language="python", content='print("hello")\n'
    )


def test_thematic_break() -> None:
    assert _full_blocks()[7] == ThematicBreak(source_line=22)


def test_table_rows() -> None:
    assert _full_blocks()[8] == Table(source_line=24, rows=[["列 A", "列 B"], ["a1", "b1"]])


def test_block_math_becomes_formula() -> None:
    assert _block_at_line(_full_blocks(), 30) == Formula(
        latex="\n\\int_0^1 x \\, dx = \\frac{1}{2}\n",
        source_line=30,
    )


def test_standalone_image_becomes_image_block() -> None:
    assert _block_at_line(_full_blocks(), 36) == ImageBlock(
        source_line=36, src="pics/photo.png", alt=""
    )


def test_standalone_pagebreak_becomes_block() -> None:
    assert _block_at_line(_full_blocks(), 38) == PageBreak(source_line=38)


def test_trailing_paragraph_after_markers() -> None:
    assert _full_blocks()[-1] == Paragraph(content=[Text("结尾段落。")], source_line=40)


def test_fixture_covers_every_block_kind() -> None:
    """full.md 是「所有节点都在里面」的样例，防止快照悄悄漏掉一整类节点。"""
    kinds = {type(block) for block in _full_blocks()}
    assert kinds == {
        Heading,
        Paragraph,
        ListBlock,
        BlockQuote,
        CodeBlock,
        ThematicBreak,
        PageBreak,
        Table,
        Formula,
        ImageBlock,
    }


# --------------------------------------------------------------------------
# 冲突规则（手册 5.1）
# --------------------------------------------------------------------------
def test_markup_inside_code_block_is_not_parsed() -> None:
    text = "```markdown\n**粗体** [链接](x) [[img:a.png]]\n```\n"
    assert parse_dfm(text) == [
        CodeBlock(
            source_line=1,
            language="markdown",
            content="**粗体** [链接](x) [[img:a.png]]\n",
        )
    ]


def test_inline_code_keeps_markup_literal() -> None:
    assert parse_dfm("`**a**`\n") == [Paragraph(content=[Code("**a**")], source_line=1)]


def test_markdown_not_parsed_inside_math() -> None:
    assert parse_dfm("$a **b** c$\n") == [
        Paragraph(content=[Math(latex="a **b** c", display=False)], source_line=1)
    ]


def test_backslash_escapes_one_character() -> None:
    assert parse_dfm("\\*不是斜体\\*\n") == [Paragraph(content=[Text("*不是斜体*")], source_line=1)]


def _full_blocks() -> list[BlockNode]:
    return parse_dfm(_full())


def _block_at_line(blocks: list[BlockNode], source_line: int) -> BlockNode:
    """按源行号定位块级节点：比硬编码下标更稳，且能证明行号正确。"""
    matches = [block for block in blocks if block.source_line == source_line]
    assert matches, f"没有 source_line={source_line} 的块级节点"
    return matches[0]
