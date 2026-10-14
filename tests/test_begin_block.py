"""双语法与命名块契约（完整版手册 §6.2.5 / §6.2.6）。

``\\begin{code:lang} ... \\end{code:lang}`` 用于「内部含终止符 / 需要嵌套」的场景；
``\\begin{名字 属性} ... \\end{名字}`` 是命名块（题注、公式、摘要等容器）。

错误码：``E3002`` 首尾名字不一致，``E3001`` 未闭合，``E4001`` 语法错误。
"""

import pytest

from docgen import errors
from docgen.ir import CodeBlock, NamedBlock, Paragraph, Text
from docgen.parser.dfm import parse_dfm


# --------------------------------------------------------------------------
# 代码块：fence 与 \begin 等价
# --------------------------------------------------------------------------
def test_begin_code_block_is_equivalent_to_fence() -> None:
    fenced = parse_dfm("```python\nprint(1)\n```\n")
    begun = parse_dfm("\\begin{code:python}\nprint(1)\n\\end{code:python}\n")
    assert begun == fenced == [CodeBlock(language="python", content="print(1)\n", source_line=1)]


def test_begin_code_block_without_language() -> None:
    assert parse_dfm("\\begin{code}\nx\n\\end{code}\n") == [
        CodeBlock(language="", content="x\n", source_line=1)
    ]


def test_begin_code_block_keeps_fence_markers_literal() -> None:
    """内部含 ``` 时 fence 会提前终止，正是 \\begin 存在的理由。"""
    text = "\\begin{code:markdown}\n```python\nprint(1)\n```\n\\end{code:markdown}\n"
    assert parse_dfm(text) == [
        CodeBlock(
            language="markdown",
            content="```python\nprint(1)\n```\n",
            source_line=1,
        )
    ]


def test_begin_code_block_keeps_dfm_markers_literal() -> None:
    text = "\\begin{code:text}\n[[img:a.png]] [x]{.y} $z$\n\\end{code:text}\n"
    assert parse_dfm(text) == [
        CodeBlock(language="text", content="[[img:a.png]] [x]{.y} $z$\n", source_line=1)
    ]


def test_begin_names_must_match() -> None:
    with pytest.raises(errors.DocGenError) as caught:
        parse_dfm("\\begin{code:python}\nx\n\\end{code:py}\n")
    assert caught.value.code == errors.E_BEGIN_MISMATCH


def test_unclosed_begin_block_is_reported() -> None:
    with pytest.raises(errors.DocGenError) as caught:
        parse_dfm("\\begin{code:python}\nx\n")
    assert caught.value.code == errors.E_UNCLOSED_MARKER


def test_inline_begin_is_text() -> None:
    """``\\begin{...}`` 必须独占一行；行内出现时是普通文本。"""
    assert parse_dfm("文本 \\begin{code} 不是块\n") == [
        Paragraph(content=[Text("文本 \\begin{code} 不是块")], source_line=1)
    ]


def test_escaped_begin_is_text() -> None:
    assert parse_dfm("\\\\begin{code}\n") == [
        Paragraph(content=[Text("\\begin{code}")], source_line=1)
    ]


# --------------------------------------------------------------------------
# 命名块
# --------------------------------------------------------------------------
def test_named_block_with_content() -> None:
    blocks = parse_dfm("\\begin{caption}\n图 1 系统架构\n\\end{caption}\n")
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert block.name == "caption"
    assert block.attributes == {}
    assert isinstance(block.content[0], Paragraph)
    assert block.content[0].content == [Text("图 1 系统架构")]


def test_named_block_with_pandoc_attributes() -> None:
    blocks = parse_dfm("\\begin{equation #eq:main .numbered}\n$$ E = mc^2 $$\n\\end{equation}\n")
    block = blocks[0]
    assert isinstance(block, NamedBlock)
    assert block.name == "equation"
    assert block.attributes["id"] == "eq:main"
    assert block.attributes["classes"] == "numbered"


def test_named_block_keeps_source_line() -> None:
    blocks = parse_dfm("段落\n\n\\begin{abstract}\n摘要\n\\end{abstract}\n")
    assert blocks[0] == Paragraph(content=[Text("段落")], source_line=1)
    abstract = blocks[1]
    assert isinstance(abstract, NamedBlock)
    assert abstract.source_line == 3


def test_nested_named_blocks() -> None:
    """``\\begin`` 必须独占一行：前面留空行，内层才会成为独立块。"""
    text = "\\begin{outer}\n内层开始\n\n\\begin{inner}\n深层\n\\end{inner}\n\\end{outer}\n"
    blocks = parse_dfm(text)
    outer = blocks[0]
    assert isinstance(outer, NamedBlock) and outer.name == "outer"
    inner = next(child for child in outer.content if isinstance(child, NamedBlock))
    assert inner.name == "inner"
    nested = inner.content[0]
    assert isinstance(nested, Paragraph)
    assert nested.content == [Text("深层")]


def test_mid_paragraph_begin_is_syntax_error() -> None:
    """``\\begin`` 必须独占一行：夹在段落中间要报 E4001，而不是静默错位。"""
    with pytest.raises(errors.DocGenError) as caught:
        parse_dfm("\\begin{outer}\n前一行\n\\begin{inner}\n\\end{inner}\n\\end{outer}\n")
    assert caught.value.code == errors.E_SYNTAX
    assert "独占一行" in caught.value.message


def test_line_numbers_after_begin_block_are_preserved() -> None:
    text = "\\begin{code:python}\nprint(1)\n\\end{code:python}\n\n结尾段落\n"
    blocks = parse_dfm(text)
    assert blocks[0] == CodeBlock(language="python", content="print(1)\n", source_line=1)
    assert blocks[1] == Paragraph(content=[Text("结尾段落")], source_line=5)


def test_named_block_names_must_match() -> None:
    with pytest.raises(errors.DocGenError) as caught:
        parse_dfm("\\begin{caption}\nx\n\\end{abstract}\n")
    assert caught.value.code == errors.E_BEGIN_MISMATCH
