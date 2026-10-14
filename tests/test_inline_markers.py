"""上下标语法契约（完整版手册 §6.2.3）。

Pandoc 风格单字符标记：``H~2~O`` 下标、``E=mc^2^`` 上标；
同时支持属性写法 ``[上标]{.sup}`` / ``[下标]{.sub}``（渲染层按样式名处理）。
"""

from docgen.ir import Code, Paragraph, Styled, Text
from docgen.parser.dfm import parse_dfm


def test_subscript_single_character() -> None:
    assert parse_dfm("H~2~O\n") == [
        Paragraph(
            content=[Text("H"), Styled(content=[Text("2")], style_name="sub"), Text("O")],
            source_line=1,
        )
    ]


def test_superscript_single_character() -> None:
    assert parse_dfm("E=mc^2^\n") == [
        Paragraph(
            content=[
                Text("E=mc"),
                Styled(content=[Text("2")], style_name="sup"),
            ],
            source_line=1,
        )
    ]


def test_superscript_with_longer_content() -> None:
    assert parse_dfm("x^10^\n") == [
        Paragraph(
            content=[Text("x"), Styled(content=[Text("10")], style_name="sup")],
            source_line=1,
        )
    ]


def test_attribute_superscript_marker() -> None:
    assert parse_dfm("[上标]{.sup}\n") == [
        Paragraph(content=[Styled(content=[Text("上标")], style_name="sup")], source_line=1)
    ]


def test_attribute_subscript_marker() -> None:
    assert parse_dfm("[下标]{.sub}\n") == [
        Paragraph(content=[Styled(content=[Text("下标")], style_name="sub")], source_line=1)
    ]


def test_tilde_not_followed_by_closing_tilde_is_text() -> None:
    assert parse_dfm("3 ~ 5 大约是 2\n") == [
        Paragraph(content=[Text("3 ~ 5 大约是 2")], source_line=1)
    ]


def test_caret_alone_is_text() -> None:
    assert parse_dfm("a ^ b\n") == [Paragraph(content=[Text("a ^ b")], source_line=1)]


def test_strikethrough_still_works() -> None:
    """``~~删除~~`` 必须仍然解析成 strike，不能被上下标规则抢走。"""
    assert parse_dfm("~~删除~~\n") == [
        Paragraph(content=[Styled(content=[Text("删除")], style_name="strike")], source_line=1)
    ]


def test_subscript_inside_code_is_literal() -> None:
    assert parse_dfm("`a~b~c`\n") == [Paragraph(content=[Code("a~b~c")], source_line=1)]


def test_subscript_does_not_cross_lines() -> None:
    """跨行的 ``~`` 不是下标：内容不允许含换行，于是退化为普通文本。"""
    assert parse_dfm("a~\nb\n") == [
        Paragraph(content=[Text("a~"), Text(" "), Text("b")], source_line=1)
    ]


def test_unmatched_tilde_in_text() -> None:
    assert parse_dfm("大约 3 ~ 5 人\n") == [
        Paragraph(content=[Text("大约 3 ~ 5 人")], source_line=1)
    ]
