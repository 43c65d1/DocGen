"""解析边界与标记冲突：不完整的标记退化为字面文本，而不是崩溃。

剪枝版约定：未闭合的 ``[[`` / ``[..]{`` / ``$`` 保持原样输出（内容不丢），
这样 ``docgen check`` 才能在未来把它们报成 E3001，而不必先解析成功。
"""

from docgen.ir import Break, CodeBlock, Image, Math, PageBreak, Paragraph, Styled, Text
from docgen.parser.dfm import parse_dfm


def test_unclosed_wiki_marker_stays_literal() -> None:
    assert parse_dfm("[[img:a.png\n") == [Paragraph(content=[Text("[[img:a.png")], source_line=1)]


def test_unknown_wiki_marker_stays_literal() -> None:
    assert parse_dfm("[[unknown]]\n") == [Paragraph(content=[Text("[[unknown]]")], source_line=1)]


def test_unclosed_style_attribute_stays_literal() -> None:
    assert parse_dfm("[文字]{.caption\n") == [
        Paragraph(content=[Text("[文字]{.caption")], source_line=1)
    ]


def test_unclosed_math_stays_literal() -> None:
    assert parse_dfm("价格是 $5 元\n") == [Paragraph(content=[Text("价格是 $5 元")], source_line=1)]


def test_empty_math_is_literal() -> None:
    assert parse_dfm("空 $ $ 白\n") == [Paragraph(content=[Text("空 $ $ 白")], source_line=1)]


def test_inline_image_marker() -> None:
    assert parse_dfm("前 [[img:a.png]] 后\n") == [
        Paragraph(
            content=[Text("前 "), Image(src="a.png", alt=""), Text(" 后")],
            source_line=1,
        )
    ]


def test_code_fence_without_language() -> None:
    assert parse_dfm("```\nplain\n```\n") == [
        CodeBlock(source_line=1, language="", content="plain\n")
    ]


def test_unknown_language_is_recorded_not_rejected() -> None:
    assert parse_dfm("```rust\nfn main() {}\n```\n") == [
        CodeBlock(source_line=1, language="rust", content="fn main() {}\n")
    ]


def test_inline_styled_marker_with_markdown_inside() -> None:
    assert parse_dfm("[**粗** 体]{.keyword}\n") == [
        Paragraph(
            content=[
                Styled(
                    content=[Styled(content=[Text("粗")], style_name="strong"), Text(" 体")],
                    style_name="keyword",
                )
            ],
            source_line=1,
        )
    ]


def test_inline_math_with_escapes_keeps_backslashes() -> None:
    assert parse_dfm("$\\frac{1}{2}$\n") == [
        Paragraph(content=[Math(latex="\\frac{1}{2}", display=False)], source_line=1)
    ]


def test_pagebreak_inside_paragraph_stays_inline_break() -> None:
    """只有独立成段的 [[pagebreak]] 才是分页块；夹在文字里就是硬换行。"""
    assert parse_dfm("前 [[pagebreak]] 后\n") == [
        Paragraph(content=[Text("前 "), Break(), Text(" 后")], source_line=1)
    ]


def test_standalone_pagebreak_is_block() -> None:
    assert parse_dfm("[[pagebreak]]\n") == [PageBreak(source_line=1)]
